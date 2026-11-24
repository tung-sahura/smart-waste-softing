"""YOLO 权重加载、推理与检测结果适配。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .protocol import WasteType


@dataclass
class Detection:
    waste_type: WasteType
    class_name: str
    confidence: float
    box: Tuple[int, int, int, int]


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        raise NotImplementedError


class YoloDetector(Detector):
    """加载指定权重，并把模型原始类别映射到四类垃圾。"""

    DEFAULT_CLASS_MAP = {
        "bottolad": WasteType.RECYCLABLE,
        "plasticbottle": WasteType.RECYCLABLE,
        "box": WasteType.RECYCLABLE,
        "can": WasteType.RECYCLABLE,
        "papercup": WasteType.RECYCLABLE,
        "yangleduo": WasteType.RECYCLABLE,
        "potato": WasteType.KITCHEN,
        "carrot": WasteType.KITCHEN,
        "qincarrot": WasteType.KITCHEN,
        "redcarrot": WasteType.KITCHEN,
        "whitcarrot": WasteType.KITCHEN,
        "battery": WasteType.HAZARDOUS,
        "drug": WasteType.HAZARDOUS,
        "cobblestone": WasteType.OTHER,
        "porcelain": WasteType.OTHER,
    }

    def __init__(
        self,
        weights: Optional[str] = None,
        model=None,
        confidence: float = 0.65,
        device: Optional[str] = None,
    ) -> None:
        if not 0.0 < confidence <= 1.0:
            raise ValueError("置信度阈值必须在 (0, 1] 范围内")
        if model is None:
            if not weights:
                raise ValueError("必须指定 YOLO 权重文件")
            weight_path = Path(weights)
            if not weight_path.is_file():
                raise FileNotFoundError("YOLO 权重不存在：{}".format(weight_path))
            try:
                import torch
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError("未安装 YOLO 运行环境") from exc
            self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
            self.model = YOLO(str(weight_path))
        else:
            self.model = model
            self.device = device or "cpu"

        self.confidence = confidence
        model_names = getattr(self.model, "names", {})
        if isinstance(model_names, dict):
            class_names = model_names.values()
        elif isinstance(model_names, (list, tuple)):
            class_names = model_names
        else:
            raise ValueError("YOLO 模型必须提供类别名称表")
        unknown = sorted(set(class_names) - set(self.DEFAULT_CLASS_MAP))
        if unknown:
            raise ValueError("权重中存在未配置类别：{}".format(", ".join(unknown)))

    @staticmethod
    def _to_array(value):
        """把 PyTorch Tensor 或测试替身转换成 NumPy 数组。"""
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        return np.asarray(value)

    @classmethod
    def _flat_values(cls, value) -> np.ndarray:
        array = cls._to_array(value)
        if array.dtype == object:
            items = []
            for item in array.reshape(-1):
                if hasattr(item, "item") and not isinstance(item, np.ndarray):
                    item = item.item()
                item_array = cls._to_array(item).reshape(-1)
                if item_array.size != 1:
                    raise ValueError("YOLO 标量字段包含非标量数据")
                items.append(item_array[0])
            array = np.asarray(items, dtype=np.float32)
        return array.reshape(-1)

    @classmethod
    def _coordinate_values(cls, boxes) -> np.ndarray:
        raw = getattr(boxes, "xyxy", None)
        if raw is None:
            return np.empty((0, 4), dtype=np.float32)
        if isinstance(raw, (list, tuple)):
            array = np.asarray(
                [cls._to_array(item).reshape(-1) for item in raw],
                dtype=np.float32,
            )
        else:
            array = cls._to_array(raw)
            if array.dtype == object:
                array = np.asarray(
                    [cls._to_array(item).reshape(-1) for item in array.reshape(-1)],
                    dtype=np.float32,
                )
        if array.size == 0:
            return np.empty((0, 4), dtype=np.float32)
        try:
            return array.reshape(-1, 4)
        except ValueError as exc:
            raise ValueError("YOLO 检测框坐标不是有效的四点格式") from exc

    @staticmethod
    def _class_name_for_id(names, class_id: int) -> str:
        if isinstance(names, dict):
            class_name = names.get(class_id, names.get(str(class_id)))
        elif isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            class_name = names[class_id]
        else:
            class_name = None
        if class_name is None:
            raise ValueError("YOLO 结果中缺少类别编号 {} 的名称".format(class_id))
        return str(class_name)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """对单帧执行 YOLO 推理，返回按置信度降序排列的检测结果。"""
        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )
        if results is None:
            return []
        if not isinstance(results, (list, tuple)):
            results = [results]

        detections = []
        fallback_names = getattr(self.model, "names", {})
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names = getattr(result, "names", None) or fallback_names
            # 真实 Ultralytics 返回一个批量 Boxes 对象；部分测试替身使用
            # “每个目标一个 Box”的列表，两种形式都在这里统一处理。
            box_groups = boxes if isinstance(boxes, (list, tuple)) else [boxes]
            for box_group in box_groups:
                coordinates = self._coordinate_values(box_group)
                if coordinates.shape[0] == 0:
                    continue
                confidence_values = self._flat_values(
                    getattr(box_group, "conf", None)
                )
                class_values = self._flat_values(getattr(box_group, "cls", None))
                box_count = coordinates.shape[0]
                if (
                    len(confidence_values) != box_count
                    or len(class_values) != box_count
                ):
                    raise ValueError("YOLO 检测框、置信度和类别数量不一致")

                for index in range(box_count):
                    x1, y1, x2, y2 = coordinates[index].tolist()
                    class_id = int(class_values[index])
                    confidence = float(confidence_values[index])
                    if confidence < self.confidence:
                        continue
                    class_name = self._class_name_for_id(names, class_id)
                    waste_type = self.DEFAULT_CLASS_MAP.get(class_name)
                    if waste_type is None:
                        raise ValueError(
                            "YOLO 结果中存在未配置类别：{}".format(class_name)
                        )
                    detections.append(
                        Detection(
                            waste_type=waste_type,
                            class_name=class_name,
                            confidence=confidence,
                            box=(int(x1), int(y1), int(x2), int(y2)),
                        )
                    )

        detections.sort(key=lambda detection: detection.confidence, reverse=True)
        return detections
