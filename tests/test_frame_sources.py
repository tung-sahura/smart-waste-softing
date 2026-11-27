import unittest
from unittest.mock import patch

import numpy as np

from app.frame_sources import NetworkCameraSource, create_frame_source


class _FakeCapture:
    def __init__(self, frame=None):
        self.frame = frame
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        if self.frame is None:
            return False, None
        return True, self.frame

    def get(self, property_id):
        return 15.0

    def release(self):
        self.released = True


class NetworkCameraSourceTests(unittest.TestCase):
    def test_read_failure_reopens_network_stream(self):
        failed_capture = _FakeCapture()
        recovered_frame = np.zeros((48, 64, 3), dtype=np.uint8)
        recovered_capture = _FakeCapture(recovered_frame)

        with patch(
            "app.frame_sources.cv2.VideoCapture",
            side_effect=[failed_capture, recovered_capture],
        ) as capture_factory:
            source = NetworkCameraSource("rtsp://camera-stream:8554/camera")
            self.assertEqual(source.read(), (False, None))
            ok, frame = source.read()

        self.assertTrue(ok)
        self.assertIs(frame, recovered_frame)
        self.assertTrue(failed_capture.released)
        self.assertEqual(capture_factory.call_count, 2)


class IdleFrameSourceTests(unittest.TestCase):
    def test_idle_source_waits_for_user_selection(self):
        source = create_frame_source("none")
        try:
            self.assertEqual(source.kind, "idle")
            self.assertEqual(source.display_name, "未选择输入源")
            self.assertEqual(source.read(), (False, None))
        finally:
            source.release()


if __name__ == "__main__":
    unittest.main()
