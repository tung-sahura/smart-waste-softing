"""统一创建视频文件和实时摄像头输入源。"""

from abc import ABC, abstractmethod
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from vedio.video_module import VideoFileSource


DEFAULT_VIDEO = "assets/assessment_demo.mp4"


class FrameSource(ABC):
    kind = "unknown"
    display_name = "未知图像源"

    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        raise NotImplementedError

    @abstractmethod
    def restart(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def release(self) -> None:
        raise NotImplementedError


class CameraFrameSource(FrameSource):
    kind = "camera"

    def __init__(self, camera_index: int) -> None:
        self.source = camera_index
        self.display_name = "摄像头 {}".format(camera_index)
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头：{}".format(camera_index))
        self.frame_count = 0
        self.source_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self._reconnect_interval = 2.0
        self._next_reconnect_at = 0.0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        ok, frame = self.cap.read()
        if ok and frame is not None:
            return True, frame
        now = time.monotonic()
        if now >= self._next_reconnect_at:
            self._next_reconnect_at = now + self._reconnect_interval
            self._reconnect()
        return False, None

    def _reconnect(self) -> bool:
        self.cap.release()
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            self.cap.release()
            return False
        self.source_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        return True

    def restart(self) -> bool:
        return self._reconnect()

    def release(self) -> None:
        self.cap.release()


class NetworkCameraSource(FrameSource):
    """OpenCV video source backed by a camera stream on the host machine."""

    kind = "camera"

    def __init__(self, url: str) -> None:
        if "://" not in url:
            raise ValueError("摄像头流地址必须包含协议，例如 tcp:// 或 rtsp://")
        self.url = url
        self.display_name = "摄像头流 {}".format(url)
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            raise RuntimeError("无法连接摄像头流：{}".format(url))
        self.frame_count = 0
        self.source_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        if self.source_fps <= 1.0:
            self.source_fps = 0.0
        self._reconnect_interval = 2.0
        self._next_reconnect_at = 0.0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        ok, frame = self.cap.read()
        if ok and frame is not None:
            return True, frame
        now = time.monotonic()
        if now >= self._next_reconnect_at:
            self._next_reconnect_at = now + self._reconnect_interval
            self._reconnect()
        return False, None

    def _reconnect(self) -> bool:
        self.cap.release()
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            self.cap.release()
            return False
        self.source_fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        if self.source_fps <= 1.0:
            self.source_fps = 0.0
        return True

    def restart(self) -> bool:
        return self._reconnect()

    def release(self) -> None:
        self.cap.release()


def create_frame_source(kind: str, value: str = "") -> FrameSource:
    if kind == "video":
        return VideoFileSource(value or DEFAULT_VIDEO)
    if kind == "camera":
        if "://" in value:
            return NetworkCameraSource(value)
        try:
            camera_index = int(value or 0)
        except ValueError as exc:
            raise ValueError("摄像头编号必须是整数") from exc
        return CameraFrameSource(camera_index)
    raise ValueError("未知图像源：{}；只允许 video 或 camera".format(kind))
