"""供 YOLO 逐帧处理的视频文件输入模块。

原比赛代码使用 QMediaPlayer 直接播放视频，画面无法可靠地逐帧交给 YOLO。
本考核保留原 ``vedio`` 目录名，但统一使用 OpenCV 输出 BGR 帧。
"""

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


class VideoFileSource:
    """视频文件输入源。

    负责打开文件、逐帧读取、跳转、重新播放及释放 OpenCV 资源。
    """

    kind = "video"

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError("视频文件不存在：{}".format(self.path))
        self.display_name = str(self.path)
        self.cap = cv2.VideoCapture(str(self.path))
        if not self.cap.isOpened():
            raise RuntimeError("无法打开视频：{}".format(self.path))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.source_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self.duration_seconds = (
            self.frame_count / self.source_fps if self.source_fps > 0 else 0.0
        )

    @property
    def current_frame(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """读取下一帧；成功返回 BGR 帧，结尾或解码失败返回 ``False, None``。"""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return False, None
        return True, frame

    def seek_frame(self, frame_index: int) -> bool:
        """跳转到指定帧；帧号非法、资源失效或跳转失败时返回 ``False``。"""
        if isinstance(frame_index, bool) or not isinstance(frame_index, int):
            return False
        if frame_index < 0:
            return False
        if self.frame_count > 0 and frame_index >= self.frame_count:
            return False
        if not self.cap.isOpened():
            return False
        if not self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
            return False
        # 某些后端会接受 set() 但忽略实际位置，因此再核对当前帧号。
        return abs(self.current_frame - frame_index) <= 1

    def restart(self) -> bool:
        """从第 0 帧重新播放。"""
        return self.seek_frame(0)

    def release(self) -> None:
        self.cap.release()
