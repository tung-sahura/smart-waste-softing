"""Background playback for the standalone waste-sorting promo video."""

import threading
import time
from pathlib import Path

import cv2
from PyQt5 import QtCore, QtGui

from vedio.video_module import VideoFileSource


class PromotionalVideoPlayer(QtCore.QThread):
    """Decode video frames without blocking the Qt main thread."""

    video_ready = QtCore.pyqtSignal(int, float)
    frame_ready = QtCore.pyqtSignal(QtGui.QImage, int, int)
    playback_finished = QtCore.pyqtSignal(int, int)
    playback_failed = QtCore.pyqtSignal(str)

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self._lock = threading.Lock()
        self._play_event = threading.Event()
        self._stop_event = threading.Event()
        self._seek_request = None
        self._at_end = False

    def play(self) -> None:
        with self._lock:
            if self._at_end:
                self._seek_request = 0
                self._at_end = False
        self._play_event.set()

    def pause(self) -> None:
        self._play_event.clear()

    def request_seek(self, frame_index: int) -> None:
        with self._lock:
            self._seek_request = frame_index
            self._at_end = False

    def request_restart(self) -> None:
        self.request_seek(0)

    def stop(self) -> None:
        self._stop_event.set()
        self._play_event.set()

    @staticmethod
    def _to_qimage(frame) -> QtGui.QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        return QtGui.QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QtGui.QImage.Format_RGB888,
        ).copy()

    def run(self) -> None:
        source = None
        try:
            source = VideoFileSource(str(self.path))
            if source.frame_count <= 0:
                raise RuntimeError("宣传视频不包含可播放画面")
            self.video_ready.emit(source.frame_count, source.source_fps)

            while not self._stop_event.is_set():
                with self._lock:
                    seek_request = self._seek_request
                    self._seek_request = None
                    at_end = self._at_end

                if seek_request is not None:
                    if not source.seek_frame(seek_request):
                        self.playback_failed.emit(
                            "无法跳转到第 {} 帧".format(seek_request + 1)
                        )
                        return
                    at_end = False

                if at_end:
                    self._play_event.clear()
                    self.msleep(20)
                    continue

                if not self._play_event.wait(0.02):
                    continue

                started = time.monotonic()
                ok, frame = source.read()
                if not ok or frame is None:
                    with self._lock:
                        self._at_end = True
                    current = max(0, source.frame_count - 1)
                    self.playback_finished.emit(current, source.frame_count)
                    continue

                current = max(0, source.current_frame - 1)
                self.frame_ready.emit(
                    self._to_qimage(frame),
                    current,
                    source.frame_count,
                )

                frame_delay = (
                    1.0 / source.source_fps if source.source_fps > 0 else 0.033
                )
                remaining = frame_delay - (time.monotonic() - started)
                if remaining > 0:
                    self.msleep(int(remaining * 1000))
        except Exception as exc:
            self.playback_failed.emit(str(exc))
        finally:
            if source is not None:
                source.release()
