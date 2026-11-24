"""Tests for the standalone promotional video player."""

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtGui, QtWidgets

from app.promo_player import PromotionalVideoPlayer
from app.ui import PROMOTIONAL_VIDEO


class PromotionalVideoPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_promo_video_decodes_frames_in_worker_thread(self):
        self.assertTrue(PROMOTIONAL_VIDEO.is_file())
        ready = []
        frames = []
        errors = []
        player = PromotionalVideoPlayer(str(PROMOTIONAL_VIDEO))
        player.video_ready.connect(
            lambda frame_count, fps: ready.append((frame_count, fps))
        )
        player.frame_ready.connect(
            lambda image, current, total: frames.append((image, current, total))
        )
        player.playback_failed.connect(errors.append)

        player.start()
        player.play()
        deadline = time.monotonic() + 3.0
        while not frames and not errors and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)

        player.stop()
        self.assertTrue(player.wait(3000))
        self.app.processEvents()

        self.assertEqual(errors, [])
        self.assertTrue(ready)
        self.assertTrue(frames)
        image, current, total = frames[0]
        self.assertIsInstance(image, QtGui.QImage)
        self.assertGreaterEqual(current, 0)
        self.assertGreater(total, 1000)


if __name__ == "__main__":
    unittest.main()
