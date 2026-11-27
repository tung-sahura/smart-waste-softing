"""Offscreen smoke tests for the operator UI wiring."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtGui, QtWidgets

from app.detectors import Detection
from app.protocol import WASTE_NAMES, WasteType
from app.ui import MainWindow


class SmokeWorker(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.source_requests = []

    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    state_changed = QtCore.pyqtSignal(str)
    counts_changed = QtCore.pyqtSignal(object)
    bins_changed = QtCore.pyqtSignal(object)
    detection_changed = QtCore.pyqtSignal(object)
    model_changed = QtCore.pyqtSignal(str)
    source_changed = QtCore.pyqtSignal(str)
    source_finished = QtCore.pyqtSignal()
    log_message = QtCore.pyqtSignal(str)
    connection_changed = QtCore.pyqtSignal(bool)
    fps_changed = QtCore.pyqtSignal(float)
    frame_progress = QtCore.pyqtSignal(int, int)
    source_failed = QtCore.pyqtSignal(str)
    frame_unavailable = QtCore.pyqtSignal(str)

    def prepare_model(self):
        return None

    def start(self):
        return None

    def stop(self):
        return None

    def wait(self, _timeout):
        return True

    def request_reset(self):
        return None

    def request_source(self, kind, value):
        self.source_requests.append((kind, value))

    def request_seek(self, _frame_index):
        return None

    def start_processing(self):
        return None

    def pause_processing(self):
        return None


class MainWindowSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = MainWindow(SmokeWorker())
        self.window.resize(980, 680)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_operator_console_keeps_required_controls(self):
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertTrue(self.window.video_button.isEnabled())
        self.assertTrue(self.window.camera_button.isEnabled())
        self.assertTrue(self.window.promo_button.isEnabled())
        self.assertEqual(self.window.promo_button.text(), "宣传视频")
        self.assertEqual(self.window.camera_label.minimumWidth(), 420)
        self.assertEqual(self.window.camera_label.minimumHeight(), 280)

    def test_camera_button_toggles_open_and_close(self):
        self.assertEqual(self.window.camera_button.text(), "打开摄像头")

        self.window.toggle_camera()
        self.assertEqual(self.window.worker.source_requests[-1][0], "camera")

        self.window.on_source_changed("摄像头流 rtsp://camera-stream:8554/camera")
        self.assertEqual(self.window.camera_button.text(), "关闭摄像头")
        self.assertTrue(self.window._camera_active)

        self.window.toggle_camera()
        self.assertEqual(self.window.worker.source_requests[-1], (
            "video",
            "assets/assessment_demo.mp4",
        ))
        self.assertFalse(self.window._processing)

        self.window.on_source_changed("assets/assessment_demo.mp4")
        self.assertEqual(self.window.camera_button.text(), "打开摄像头")
        self.assertFalse(self.window._camera_active)

    def test_idle_source_prompts_for_manual_input(self):
        self.window.on_source_changed("未选择输入源")

        self.assertEqual(self.window.source_mode_label.text(), "等待输入")
        self.assertIn("导入视频", self.window.camera_label.text())
        self.assertEqual(self.window.camera_button.text(), "打开摄像头")
        self.assertIn("等待输入源", self.window.state_label.text())

    def test_detection_and_bin_state_update_visual_properties(self):
        detection = Detection(
            waste_type=WasteType.HAZARDOUS,
            class_name="drug",
            confidence=0.954,
            box=(10, 10, 20, 20),
        )
        self.window.update_detection(detection)
        self.assertEqual(self.window.waste_label.text(), WASTE_NAMES[WasteType.HAZARDOUS])
        self.assertEqual(self.window.waste_label.property("category"), "hazardous")
        self.assertEqual(self.window.confidence_bar.value(), 954)

        name = WASTE_NAMES[WasteType.HAZARDOUS]
        self.window.update_bins({name: True})
        self.assertEqual(self.window.bin_labels[name].text(), "满载")
        self.assertEqual(self.window.bin_labels[name].property("tone"), "error")

    def test_log_formats_tx_and_rx_without_losing_payload(self):
        self.window.append_log("TX  WASTE_RESULT  AA 55 03 01 01 03 08")
        self.window.append_log("RX  ACK  AA 55 03 02 01 01 07")
        self.window.append_log("RX  ACTION_DONE  AA 55 02 03 01 06")
        log_text = self.window.log_browser.toPlainText()
        self.assertIn("[TX]", log_text)
        self.assertIn("[RX]", log_text)
        self.assertIn("WASTE_RESULT", log_text)
        self.assertIn("ACK", log_text)
        self.assertIn("ACTION_DONE", log_text)
        self.assertIn("AA 55 03 01 01 03 08", log_text)
        self.assertEqual(self.window.log_count_label.text(), "3 条")

    def test_processing_and_video_finish_have_explicit_feedback(self):
        self.window._set_processing(True)
        self.assertIn("视频识别中", self.window.state_label.text())
        self.assertEqual(self.window.start_button.text(), "暂停识别")

        self.window.on_source_finished()
        self.assertEqual(self.window.start_button.text(), "重新播放")
        self.assertIn("视频播放完成", self.window.camera_label.text())


if __name__ == "__main__":
    unittest.main()
