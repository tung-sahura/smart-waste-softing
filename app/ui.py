"""PyQt operator console for the smart waste sorting system."""

import datetime
import html
import os
from pathlib import Path
from typing import Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from .detectors import Detection
from .promo_player import PromotionalVideoPlayer
from .protocol import Command, WASTE_NAMES, WasteType
from .worker import SortingWorker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMOTIONAL_VIDEO = PROJECT_ROOT / "vedio" / "dep.mp4"


class PromotionalVideoDialog(QtWidgets.QDialog):
    """Standalone player for the waste-sorting awareness video."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("垃圾分类宣传视频")
        self.setModal(False)
        self.resize(1040, 700)
        self.setMinimumSize(760, 520)
        self._frame_count = 0
        self._fps = 0.0
        self._dragging = False
        self._playing = False
        self._ended = False
        self._failed = False
        self._build_ui()
        self._connect_signals()
        self.player = PromotionalVideoPlayer(str(PROMOTIONAL_VIDEO), self)
        self.player.video_ready.connect(self.on_video_ready)
        self.player.frame_ready.connect(self.on_frame_ready)
        self.player.playback_finished.connect(self.on_playback_finished)
        self.player.playback_failed.connect(self.on_playback_failed)
        QtCore.QTimer.singleShot(0, self._start_playback)

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(1)
        eyebrow = QtWidgets.QLabel("WASTE SORTING AWARENESS")
        eyebrow.setObjectName("promoEyebrow")
        title = QtWidgets.QLabel("垃圾分类，从我做起")
        title.setObjectName("promoTitle")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        header.addLayout(title_box)
        header.addStretch(1)
        self.status_label = QtWidgets.QLabel("正在准备播放")
        self.status_label.setObjectName("promoStatus")
        header.addWidget(self.status_label)
        root.addLayout(header)

        video_card = QtWidgets.QFrame()
        video_card.setObjectName("promoVideoCard")
        video_layout = QtWidgets.QVBoxLayout(video_card)
        video_layout.setContentsMargins(8, 8, 8, 8)
        self.video_label = QtWidgets.QLabel("正在加载宣传视频…")
        self.video_label.setObjectName("promoVideo")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(680, 380)
        self.video_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        video_layout.addWidget(self.video_label)
        root.addWidget(video_card, 1)

        progress_row = QtWidgets.QHBoxLayout()
        progress_row.setSpacing(10)
        progress_caption = QtWidgets.QLabel("播放进度")
        progress_caption.setObjectName("promoCaption")
        progress_row.addWidget(progress_caption)
        self.progress_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.progress_slider.setObjectName("promoProgress")
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        progress_row.addWidget(self.progress_slider, 1)
        self.time_label = QtWidgets.QLabel("00:00 / 00:00")
        self.time_label.setObjectName("promoTime")
        progress_row.addWidget(self.time_label)
        root.addLayout(progress_row)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)
        self.restart_button = QtWidgets.QPushButton("从头播放")
        self.restart_button.setObjectName("secondaryButton")
        self.play_button = QtWidgets.QPushButton("暂停")
        self.play_button.setObjectName("primaryButton")
        self.close_button = QtWidgets.QPushButton("关闭")
        self.close_button.setObjectName("dangerButton")
        for button in (
            self.restart_button,
            self.play_button,
            self.close_button,
        ):
            button.setCursor(QtCore.Qt.PointingHandCursor)
        controls.addWidget(self.restart_button)
        controls.addStretch(1)
        controls.addWidget(self.play_button)
        controls.addWidget(self.close_button)
        root.addLayout(controls)

        self.setStyleSheet(
            """
            QDialog {
                background: #eef2f7;
            }
            QWidget {
                color: #0f172a;
                font-family: "WenQuanYi Zen Hei", "Microsoft YaHei", sans-serif;
                font-size: 13px;
            }
            QLabel#promoEyebrow, QLabel#promoCaption {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#promoTitle {
                color: #0f172a;
                font-size: 23px;
                font-weight: 700;
            }
            QLabel#promoStatus {
                background: #dcfce7;
                border-radius: 9px;
                color: #15803d;
                font-size: 11px;
                font-weight: 700;
                padding: 5px 10px;
            }
            QFrame#promoVideoCard {
                background: #111827;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }
            QLabel#promoVideo {
                background: #020617;
                border-radius: 9px;
                color: #94a3b8;
                font-size: 14px;
            }
            QLabel#promoTime {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
                min-width: 92px;
            }
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                min-height: 32px;
                min-width: 92px;
                padding: 0 14px;
            }
            QPushButton#secondaryButton {
                background: #ffffff;
                color: #334155;
            }
            QPushButton#secondaryButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#primaryButton {
                background: #2563eb;
                border-color: #2563eb;
                color: #ffffff;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
            }
            QPushButton#dangerButton {
                background: #fff1f2;
                border-color: #fecdd3;
                color: #be123c;
                min-width: 72px;
            }
            QPushButton:disabled {
                background: #f1f5f9;
                border-color: #e2e8f0;
                color: #94a3b8;
            }
            QSlider::groove:horizontal {
                background: #dbe4ef;
                border-radius: 3px;
                height: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #3b82f6;
                border-radius: 7px;
                height: 12px;
                margin: -4px 0;
                width: 12px;
            }
            QSlider::groove:horizontal:disabled {
                background: #e2e8f0;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.play_button.clicked.connect(self.toggle_playback)
        self.restart_button.clicked.connect(self.restart_playback)
        self.close_button.clicked.connect(self.close)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)

    def _start_playback(self) -> None:
        if not PROMOTIONAL_VIDEO.is_file():
            self.on_playback_failed(
                "宣传视频不存在：{}".format(PROMOTIONAL_VIDEO)
            )
            return
        self.player.start()
        self.player.play()
        self._playing = True
        self.play_button.setText("暂停")
        self.status_label.setText("正在播放")

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        return "{:02d}:{:02d}".format(total // 60, total % 60)

    @QtCore.pyqtSlot(int, float)
    def on_video_ready(self, frame_count: int, fps: float) -> None:
        self._frame_count = max(0, frame_count)
        self._fps = max(0.0, fps)
        self.progress_slider.setRange(0, max(0, self._frame_count - 1))
        self.progress_slider.setEnabled(self._frame_count > 1)
        duration = self._frame_count / self._fps if self._fps > 0 else 0.0
        self.time_label.setText(
            "00:00 / {}".format(self._format_time(duration))
        )

    @QtCore.pyqtSlot(QtGui.QImage, int, int)
    def on_frame_ready(
        self,
        image: QtGui.QImage,
        current_frame: int,
        frame_count: int,
    ) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )
        if not self._dragging:
            self.progress_slider.setValue(current_frame)
        current_seconds = current_frame / self._fps if self._fps > 0 else 0.0
        duration = frame_count / self._fps if self._fps > 0 else 0.0
        self.time_label.setText(
            "{} / {}".format(
                self._format_time(current_seconds),
                self._format_time(duration),
            )
        )

    @QtCore.pyqtSlot()
    def toggle_playback(self) -> None:
        if self._failed:
            return
        if self._playing:
            self.player.pause()
            self._playing = False
            self.play_button.setText("播放")
            self.status_label.setText("已暂停")
            return

        if self._ended:
            self.player.request_restart()
            self._ended = False
            self.progress_slider.setValue(0)
        self.player.play()
        self._playing = True
        self.play_button.setText("暂停")
        self.status_label.setText("正在播放")

    @QtCore.pyqtSlot()
    def restart_playback(self) -> None:
        if self._failed:
            return
        self.player.request_restart()
        self.player.play()
        self._ended = False
        self._playing = True
        self.play_button.setText("暂停")
        self.status_label.setText("正在播放")
        self.progress_slider.setValue(0)

    @QtCore.pyqtSlot()
    def on_slider_pressed(self) -> None:
        self._dragging = True
        if self._playing:
            self.player.pause()

    @QtCore.pyqtSlot(int)
    def on_slider_moved(self, value: int) -> None:
        if self._fps <= 0:
            return
        duration = self._frame_count / self._fps
        self.time_label.setText(
            "{} / {}".format(
                self._format_time(value / self._fps),
                self._format_time(duration),
            )
        )

    @QtCore.pyqtSlot()
    def on_slider_released(self) -> None:
        self._dragging = False
        self.player.request_seek(self.progress_slider.value())
        self.player.play()
        self._ended = False
        self._playing = True
        self.play_button.setText("暂停")
        self.status_label.setText("正在播放")

    @QtCore.pyqtSlot(int, int)
    def on_playback_finished(self, current_frame: int, frame_count: int) -> None:
        self._playing = False
        self._ended = True
        self.play_button.setText("重新播放")
        self.status_label.setText("播放完成")
        self.progress_slider.setValue(current_frame)
        duration = frame_count / self._fps if self._fps > 0 else 0.0
        self.time_label.setText(
            "{} / {}".format(
                self._format_time(duration),
                self._format_time(duration),
            )
        )

    @QtCore.pyqtSlot(str)
    def on_playback_failed(self, message: str) -> None:
        self._failed = True
        self._playing = False
        self.play_button.setEnabled(False)
        self.restart_button.setEnabled(False)
        self.progress_slider.setEnabled(False)
        self.status_label.setText("播放失败")
        self.video_label.clear()
        self.video_label.setText("无法播放宣传视频\n{}".format(message))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.player.stop()
        if self.player.isRunning() and not self.player.wait(3000):
            self.status_label.setText("播放器正在退出，请稍后再关闭")
            event.ignore()
            return
        event.accept()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, worker: SortingWorker, auto_start: bool = False) -> None:
        super().__init__()
        self.worker = worker
        self._processing = False
        self._video_frame_count = 0
        self._slider_dragging = False
        self._log_line_count = 0
        self.promotional_dialog = None
        self.count_labels = {}  # type: Dict[str, QtWidgets.QLabel]
        self.bin_labels = {}  # type: Dict[str, QtWidgets.QLabel]
        self._build_ui()
        self._connect_signals()
        self._auto_start = auto_start
        QtCore.QTimer.singleShot(50, self._initialize_worker)

    @QtCore.pyqtSlot()
    def _initialize_worker(self) -> None:
        try:
            self.worker.prepare_model()
        except Exception as exc:
            self.update_model_status("加载失败")
            self.update_system_state("运行异常")
            self.append_log("YOLO 模型加载失败：{}".format(exc))
            self.start_button.setEnabled(False)
            return
        self.worker.start()
        if self._auto_start:
            QtCore.QTimer.singleShot(500, self.toggle_processing)

    @staticmethod
    def _repolish(widget: QtWidgets.QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _set_visual_property(
        self,
        widget: QtWidgets.QWidget,
        name: str,
        value: str,
    ) -> None:
        if widget.property(name) == value:
            return
        widget.setProperty(name, value)
        self._repolish(widget)

    def _make_metric(
        self,
        caption: str,
        value: str,
        object_name: str,
    ):
        box = QtWidgets.QFrame()
        box.setObjectName("metricBox")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(3)
        caption_label = QtWidgets.QLabel(caption)
        caption_label.setObjectName("metricCaption")
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName(object_name)
        value_label.setProperty("tone", "neutral")
        value_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        return box, value_label

    def _make_card(self, title: str):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(7)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("cardTitle")
        header.addWidget(title_label)
        header.addStretch(1)
        layout.addLayout(header)
        return card, layout, header

    def _build_ui(self) -> None:
        self.setWindowTitle("智能垃圾分拣系统 · 招新考核")
        self.setMinimumSize(980, 680)
        self.resize(1240, 800)
        central = QtWidgets.QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        header_card = QtWidgets.QFrame()
        header_card.setObjectName("headerCard")
        header = QtWidgets.QHBoxLayout(header_card)
        header.setContentsMargins(18, 11, 18, 11)
        header.setSpacing(18)

        brand = QtWidgets.QVBoxLayout()
        brand.setSpacing(1)
        eyebrow = QtWidgets.QLabel("SMART WASTE SORTING")
        eyebrow.setObjectName("eyebrow")
        brand.addWidget(eyebrow)
        title = QtWidgets.QLabel("智能垃圾分拣上位机")
        title.setObjectName("titleLabel")
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch(1)

        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(8)
        state_box, self.state_label = self._make_metric(
            "运行状态",
            "●  等待启动",
            "statusBadge",
        )
        connection_box, self.connection_label = self._make_metric(
            "下位机",
            "●  未连接",
            "statusBadge",
        )
        fps_box, self.fps_label = self._make_metric(
            "画面帧率",
            "0 FPS",
            "statusBadge",
        )
        self.state_label.setMinimumWidth(100)
        self.connection_label.setMinimumWidth(82)
        self.fps_label.setMinimumWidth(62)
        metrics.addWidget(state_box)
        metrics.addWidget(connection_box)
        metrics.addWidget(fps_box)
        header.addLayout(metrics)
        root.addWidget(header_card)

        info_strip = QtWidgets.QFrame()
        info_strip.setObjectName("infoStrip")
        status_layout = QtWidgets.QHBoxLayout(info_strip)
        status_layout.setContentsMargins(16, 9, 16, 9)
        status_layout.setSpacing(16)

        source_caption = QtWidgets.QLabel("当前输入")
        source_caption.setObjectName("fieldCaption")
        self.source_label = QtWidgets.QLabel("正在打开默认考核视频…")
        self.source_label.setObjectName("infoValue")
        self.source_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.source_label.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored,
            QtWidgets.QSizePolicy.Preferred,
        )
        source_layout = QtWidgets.QVBoxLayout()
        source_layout.setSpacing(0)
        source_layout.addWidget(source_caption)
        source_layout.addWidget(self.source_label)
        status_layout.addLayout(source_layout, 5)

        divider = QtWidgets.QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QtWidgets.QFrame.VLine)
        status_layout.addWidget(divider)

        model_caption = QtWidgets.QLabel("YOLO 模型")
        model_caption.setObjectName("fieldCaption")
        self.model_label = QtWidgets.QLabel("等待加载…")
        self.model_label.setObjectName("infoValue")
        self.model_label.setProperty("tone", "neutral")
        model_layout = QtWidgets.QVBoxLayout()
        model_layout.setSpacing(0)
        model_layout.addWidget(model_caption)
        model_layout.addWidget(self.model_label)
        status_layout.addLayout(model_layout, 3)
        root.addWidget(info_strip)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        video_card = QtWidgets.QFrame()
        video_card.setObjectName("videoCard")
        vision_layout = QtWidgets.QVBoxLayout(video_card)
        vision_layout.setContentsMargins(15, 12, 15, 12)
        vision_layout.setSpacing(9)

        video_header = QtWidgets.QHBoxLayout()
        video_header.setSpacing(8)
        video_title = QtWidgets.QLabel("实时检测画面")
        video_title.setObjectName("darkTitle")
        video_header.addWidget(video_title)
        self.source_mode_label = QtWidgets.QLabel("视频模式")
        self.source_mode_label.setObjectName("darkBadge")
        video_header.addWidget(self.source_mode_label)
        video_header.addStretch(1)
        inference_label = QtWidgets.QLabel("YOLO 实时推理")
        inference_label.setObjectName("darkHint")
        video_header.addWidget(inference_label)
        vision_layout.addLayout(video_header)

        video_stage = QtWidgets.QFrame()
        video_stage.setObjectName("videoStage")
        stage_layout = QtWidgets.QVBoxLayout(video_stage)
        stage_layout.setContentsMargins(8, 8, 8, 8)
        self.camera_label = QtWidgets.QLabel(
            "导入视频或打开摄像头，然后点击“开始识别”"
        )
        self.camera_label.setObjectName("cameraLabel")
        self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
        self.camera_label.setWordWrap(True)
        self.camera_label.setMinimumSize(420, 280)
        self.camera_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        stage_layout.addWidget(self.camera_label)
        vision_layout.addWidget(video_stage, 1)
        video_hint = QtWidgets.QLabel("检测框、类别与置信度将实时叠加在画面上")
        video_hint.setObjectName("darkHint")
        vision_layout.addWidget(video_hint)
        splitter.addWidget(video_card)

        info_scroll = QtWidgets.QScrollArea()
        info_scroll.setObjectName("infoScroll")
        info_scroll.setWidgetResizable(True)
        info_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        info_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        info_scroll.setMinimumWidth(340)
        information = QtWidgets.QWidget()
        information.setObjectName("infoContent")
        info_layout = QtWidgets.QVBoxLayout(information)
        info_layout.setContentsMargins(0, 0, 3, 0)
        info_layout.setSpacing(8)

        result_group, result_layout, result_header = self._make_card("当前识别结果")
        self.result_state_label = QtWidgets.QLabel("等待目标")
        self.result_state_label.setObjectName("microBadge")
        result_header.addWidget(self.result_state_label)

        class_caption = QtWidgets.QLabel("模型类别")
        class_caption.setObjectName("fieldCaption")
        self.class_label = QtWidgets.QLabel("—")
        self.class_label.setObjectName("modelClass")
        self.class_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        result_layout.addWidget(class_caption)
        result_layout.addWidget(self.class_label)

        waste_caption = QtWidgets.QLabel("垃圾分类")
        waste_caption.setObjectName("fieldCaption")
        self.waste_label = QtWidgets.QLabel("等待识别")
        self.waste_label.setObjectName("categoryValue")
        self.waste_label.setProperty("category", "neutral")
        self.waste_label.setAlignment(QtCore.Qt.AlignCenter)
        self.waste_label.setMinimumHeight(42)
        result_layout.addWidget(waste_caption)
        result_layout.addWidget(self.waste_label)

        confidence_row = QtWidgets.QHBoxLayout()
        confidence_caption = QtWidgets.QLabel("置信度")
        confidence_caption.setObjectName("fieldCaption")
        confidence_row.addWidget(confidence_caption)
        confidence_row.addStretch(1)
        self.confidence_label = QtWidgets.QLabel("—")
        self.confidence_label.setObjectName("confidenceValue")
        confidence_row.addWidget(self.confidence_label)
        result_layout.addLayout(confidence_row)
        self.confidence_bar = QtWidgets.QProgressBar()
        self.confidence_bar.setObjectName("confidenceBar")
        self.confidence_bar.setProperty("category", "neutral")
        self.confidence_bar.setRange(0, 1000)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        result_layout.addWidget(self.confidence_bar)
        info_layout.addWidget(result_group)

        stats_group, stats_layout, stats_header = self._make_card("分类统计")
        stats_badge = QtWidgets.QLabel("ACTION_DONE 后计数")
        stats_badge.setObjectName("microBadge")
        stats_header.addWidget(stats_badge)
        category_colors = {
            WasteType.RECYCLABLE: "recyclable",
            WasteType.KITCHEN: "kitchen",
            WasteType.HAZARDOUS: "hazardous",
            WasteType.OTHER: "other",
        }
        for waste_type in (
            WasteType.RECYCLABLE,
            WasteType.KITCHEN,
            WasteType.HAZARDOUS,
            WasteType.OTHER,
        ):
            name = WASTE_NAMES[waste_type]
            stat_row = QtWidgets.QFrame()
            stat_row.setObjectName("statRow")
            stat_row_layout = QtWidgets.QHBoxLayout(stat_row)
            stat_row_layout.setContentsMargins(9, 5, 9, 5)
            stat_row_layout.setSpacing(8)
            dot = QtWidgets.QLabel("●")
            dot.setObjectName("wasteDot")
            dot.setProperty("category", category_colors[waste_type])
            stat_row_layout.addWidget(dot)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("statName")
            stat_row_layout.addWidget(name_label, 1)
            count = QtWidgets.QLabel("0")
            count.setObjectName("countValue")
            count.setAlignment(QtCore.Qt.AlignCenter)
            count.setMinimumWidth(38)
            status = QtWidgets.QLabel("正常")
            status.setObjectName("binBadge")
            status.setProperty("tone", "ok")
            status.setAlignment(QtCore.Qt.AlignCenter)
            self.count_labels[name] = count
            self.bin_labels[name] = status
            stat_row_layout.addWidget(count)
            stat_row_layout.addWidget(status)
            stats_layout.addWidget(stat_row)
        info_layout.addWidget(stats_group)

        communication_group, communication_layout, log_header = self._make_card(
            "通信日志"
        )
        self.log_count_label = QtWidgets.QLabel("0 条")
        self.log_count_label.setObjectName("microBadge")
        log_header.addWidget(self.log_count_label)
        self.clear_log_button = QtWidgets.QPushButton("清空")
        self.clear_log_button.setObjectName("ghostButton")
        log_header.addWidget(self.clear_log_button)
        self.log_browser = QtWidgets.QTextEdit()
        self.log_browser.setObjectName("logBrowser")
        self.log_browser.setReadOnly(True)
        self.log_browser.setAcceptRichText(True)
        self.log_browser.document().setMaximumBlockCount(500)
        self.log_browser.setMinimumHeight(95)
        communication_layout.addWidget(self.log_browser)
        info_layout.addWidget(communication_group, 1)
        info_scroll.setWidget(information)
        splitter.addWidget(info_scroll)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([810, 350])
        root.addWidget(splitter, 1)

        bottom_bar = QtWidgets.QFrame()
        bottom_bar.setObjectName("bottomBar")
        bottom_layout = QtWidgets.QVBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 9, 16, 10)
        bottom_layout.setSpacing(7)

        progress_layout = QtWidgets.QHBoxLayout()
        progress_layout.setSpacing(10)
        progress_caption = QtWidgets.QLabel("播放进度")
        progress_caption.setObjectName("fieldCaption")
        progress_layout.addWidget(progress_caption)
        self.progress_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        self.progress_label = QtWidgets.QLabel("实时输入")
        self.progress_label.setMinimumWidth(120)
        self.progress_label.setObjectName("progressValue")
        self.progress_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        progress_layout.addWidget(self.progress_slider, 1)
        progress_layout.addWidget(self.progress_label)
        bottom_layout.addLayout(progress_layout)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(8)
        self.video_button = QtWidgets.QPushButton("导入视频")
        self.video_button.setObjectName("secondaryButton")
        self.video_button.setToolTip("选择本地视频文件进行逐帧识别")
        self.camera_button = QtWidgets.QPushButton("打开摄像头")
        self.camera_button.setObjectName("secondaryButton")
        self.camera_button.setToolTip("打开当前配置的摄像头或网络视频流")
        self.promo_button = QtWidgets.QPushButton("宣传视频")
        self.promo_button.setObjectName("promoButton")
        self.promo_button.setToolTip("播放垃圾分类宣传视频 vedio/dep.mp4")
        self.start_button = QtWidgets.QPushButton("开始识别")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setDefault(True)
        self.start_button.setToolTip("开始或暂停 YOLO 逐帧识别")
        self.reset_button = QtWidgets.QPushButton("重置统计")
        self.reset_button.setObjectName("secondaryButton")
        self.reset_button.setToolTip("清空下位机确认后的分类计数")
        self.quit_button = QtWidgets.QPushButton("退出")
        self.quit_button.setObjectName("dangerButton")
        self.quit_button.setToolTip("停止后台线程并退出程序")
        for button in (
            self.video_button,
            self.camera_button,
            self.promo_button,
            self.start_button,
            self.reset_button,
            self.quit_button,
        ):
            button.setCursor(QtCore.Qt.PointingHandCursor)
        controls_layout.addWidget(self.video_button)
        controls_layout.addWidget(self.camera_button)
        controls_layout.addWidget(self.promo_button)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.reset_button)
        controls_layout.addWidget(self.quit_button)
        bottom_layout.addLayout(controls_layout)
        root.addWidget(bottom_bar)

        self.setStyleSheet(
            """
            QMainWindow, QWidget#root {
                background: #eef2f7;
            }
            QWidget {
                color: #0f172a;
                font-family: "WenQuanYi Zen Hei", "Microsoft YaHei", sans-serif;
                font-size: 13px;
            }
            QFrame#headerCard, QFrame#infoStrip, QFrame#card, QFrame#bottomBar {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
            }
            QFrame#metricBox {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QLabel#eyebrow, QLabel#fieldCaption, QLabel#metricCaption {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 23px;
                font-weight: 700;
            }
            QLabel#infoValue {
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#infoValue[tone="ok"] {
                color: #15803d;
            }
            QLabel#infoValue[tone="warning"] {
                color: #b45309;
            }
            QLabel#infoValue[tone="error"] {
                color: #b91c1c;
            }
            QLabel#cardTitle {
                color: #0f172a;
                font-size: 14px;
                font-weight: 700;
            }
            QFrame#divider {
                color: #e2e8f0;
            }
            QLabel#statusBadge {
                background: #e2e8f0;
                border-radius: 9px;
                color: #475569;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 9px;
            }
            QLabel#statusBadge[tone="running"] {
                background: #dbeafe;
                color: #1d4ed8;
            }
            QLabel#statusBadge[tone="ok"] {
                background: #dcfce7;
                color: #15803d;
            }
            QLabel#statusBadge[tone="warning"] {
                background: #fef3c7;
                color: #b45309;
            }
            QLabel#statusBadge[tone="error"] {
                background: #fee2e2;
                color: #b91c1c;
            }
            QLabel#microBadge {
                background: #f1f5f9;
                border-radius: 8px;
                color: #64748b;
                font-size: 10px;
                font-weight: 600;
                padding: 3px 7px;
            }
            QLabel#modelClass {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#categoryValue {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                color: #475569;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#categoryValue[category="recyclable"] {
                background: #eff6ff;
                border-color: #bfdbfe;
                color: #1d4ed8;
            }
            QLabel#categoryValue[category="kitchen"] {
                background: #f0fdf4;
                border-color: #bbf7d0;
                color: #15803d;
            }
            QLabel#categoryValue[category="hazardous"] {
                background: #fef2f2;
                border-color: #fecaca;
                color: #b91c1c;
            }
            QLabel#categoryValue[category="other"] {
                background: #f8fafc;
                border-color: #cbd5e1;
                color: #475569;
            }
            QLabel#confidenceValue {
                color: #334155;
                font-size: 12px;
                font-weight: 700;
            }
            QProgressBar#confidenceBar {
                background: #e2e8f0;
                border: none;
                border-radius: 3px;
                max-height: 7px;
                min-height: 7px;
            }
            QProgressBar#confidenceBar::chunk {
                background: #94a3b8;
                border-radius: 3px;
            }
            QProgressBar#confidenceBar[category="recyclable"]::chunk {
                background: #3b82f6;
            }
            QProgressBar#confidenceBar[category="kitchen"]::chunk {
                background: #22c55e;
            }
            QProgressBar#confidenceBar[category="hazardous"]::chunk {
                background: #ef4444;
            }
            QProgressBar#confidenceBar[category="other"]::chunk {
                background: #64748b;
            }
            QFrame#statRow {
                background: #f8fafc;
                border: 1px solid #eef2f7;
                border-radius: 8px;
            }
            QLabel#wasteDot {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#wasteDot[category="recyclable"] {
                color: #3b82f6;
            }
            QLabel#wasteDot[category="kitchen"] {
                color: #22c55e;
            }
            QLabel#wasteDot[category="hazardous"] {
                color: #ef4444;
            }
            QLabel#wasteDot[category="other"] {
                color: #64748b;
            }
            QLabel#statName {
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#countValue {
                color: #0f172a;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#binBadge {
                background: #dcfce7;
                border-radius: 8px;
                color: #15803d;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 7px;
            }
            QLabel#binBadge[tone="error"] {
                background: #fee2e2;
                color: #b91c1c;
            }
            QFrame#videoCard {
                background: #111827;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }
            QLabel#darkTitle {
                color: #f8fafc;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#darkHint {
                color: #94a3b8;
                font-size: 10px;
            }
            QLabel#darkBadge {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #cbd5e1;
                font-size: 10px;
                font-weight: 600;
                padding: 3px 7px;
            }
            QFrame#videoStage {
                background: #020617;
                border: 1px solid #1e293b;
                border-radius: 10px;
            }
            QLabel#cameraLabel {
                background: transparent;
                color: #64748b;
                font-size: 13px;
            }
            QScrollArea#infoScroll {
                background: transparent;
                border: none;
            }
            QWidget#infoContent {
                background: transparent;
            }
            QTextEdit#logBrowser {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                color: #334155;
                font-family: "DejaVu Sans Mono", "Consolas", monospace;
                font-size: 11px;
                padding: 7px;
                selection-background-color: #dbeafe;
            }
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                min-height: 32px;
                min-width: 92px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background: #e2e8f0;
            }
            QPushButton#secondaryButton {
                background: #ffffff;
                color: #334155;
            }
            QPushButton#promoButton {
                background: #ecfdf5;
                border-color: #a7f3d0;
                color: #047857;
            }
            QPushButton#promoButton:hover {
                background: #d1fae5;
                border-color: #6ee7b7;
            }
            QPushButton#primaryButton {
                background: #2563eb;
                border-color: #2563eb;
                color: #ffffff;
                min-width: 112px;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton#dangerButton {
                background: #fff1f2;
                border-color: #fecdd3;
                color: #be123c;
                min-width: 72px;
            }
            QPushButton#dangerButton:hover {
                background: #ffe4e6;
                border-color: #fda4af;
            }
            QPushButton#ghostButton {
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 10px;
                min-height: 20px;
                min-width: 34px;
                padding: 0 5px;
            }
            QPushButton#ghostButton:hover {
                background: #e2e8f0;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background: #f1f5f9;
                border-color: #e2e8f0;
                color: #94a3b8;
            }
            QSlider::groove:horizontal {
                background: #dbe4ef;
                border-radius: 3px;
                height: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #3b82f6;
                border-radius: 7px;
                height: 12px;
                margin: -4px 0;
                width: 12px;
            }
            QSlider::groove:horizontal:disabled {
                background: #e2e8f0;
            }
            QLabel#progressValue {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
            }
            QScrollBar:vertical {
                background: transparent;
                margin: 2px;
                width: 7px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QToolTip {
                background: #0f172a;
                border: none;
                color: #ffffff;
                padding: 5px;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.video_button.clicked.connect(self.import_video)
        self.camera_button.clicked.connect(self.open_camera)
        self.promo_button.clicked.connect(self.open_promotional_video)
        self.start_button.clicked.connect(self.toggle_processing)
        self.reset_button.clicked.connect(self.reset_statistics)
        self.quit_button.clicked.connect(self.close)
        self.clear_log_button.clicked.connect(self.clear_log)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        self.worker.frame_ready.connect(self.update_frame)
        self.worker.frame_unavailable.connect(self.on_frame_unavailable)
        self.worker.frame_progress.connect(self.update_progress)
        self.worker.state_changed.connect(self.update_system_state)
        self.worker.counts_changed.connect(self.update_counts)
        self.worker.bins_changed.connect(self.update_bins)
        self.worker.detection_changed.connect(self.update_detection)
        self.worker.model_changed.connect(self.update_model_status)
        self.worker.source_changed.connect(self.on_source_changed)
        self.worker.source_finished.connect(self.on_source_finished)
        self.worker.source_failed.connect(self.on_source_failed)
        self.worker.log_message.connect(self.append_log)
        self.worker.connection_changed.connect(self.update_connection)
        self.worker.fps_changed.connect(self.update_fps)

    @QtCore.pyqtSlot(str)
    def update_system_state(self, text: str) -> None:
        self.state_label.setText("●  {}".format(text))
        if any(word in text for word in ("失败", "异常", "不可用")):
            tone = "error"
        elif any(word in text for word in ("识别中", "执行中", "压缩中")):
            tone = "running"
        elif any(word in text for word in ("等待", "重连", "暂停", "完成", "就绪")):
            tone = "warning"
        else:
            tone = "neutral"
        self._set_visual_property(self.state_label, "tone", tone)

    @QtCore.pyqtSlot(str)
    def update_model_status(self, text: str) -> None:
        self.model_label.setText(text)
        self.model_label.setToolTip(text)
        if "失败" in text or "异常" in text:
            tone = "error"
        elif "已加载" in text:
            tone = "ok"
        else:
            tone = "warning"
        self._set_visual_property(self.model_label, "tone", tone)

    @QtCore.pyqtSlot(float)
    def update_fps(self, value: float) -> None:
        self.fps_label.setText("{:.0f} FPS".format(value))
        self._set_visual_property(
            self.fps_label,
            "tone",
            "running" if value > 0 else "neutral",
        )

    @QtCore.pyqtSlot()
    def reset_statistics(self) -> None:
        self.worker.request_reset()
        self.append_log("已请求重置分类统计")

    @QtCore.pyqtSlot()
    def clear_log(self) -> None:
        self.log_browser.clear()
        self._log_line_count = 0
        self.log_count_label.setText("0 条")

    @QtCore.pyqtSlot()
    def import_video(self) -> None:
        """选择一个视频文件并交给后台线程逐步处理。"""
        assets_dir = Path("assets").resolve()
        start_dir = assets_dir if assets_dir.is_dir() else Path.cwd()
        selected, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择要识别的视频",
            str(start_dir),
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.webm *.m4v);;所有文件 (*)",
        )
        if not selected:
            return

        video_path = Path(selected)
        if not video_path.is_file():
            self.append_log("视频文件不存在：{}".format(video_path))
            QtWidgets.QMessageBox.warning(
                self,
                "无法导入视频",
                "所选文件不存在或无法访问：\n{}".format(video_path),
            )
            return

        self.append_log("正在导入视频：{}".format(video_path))
        self.worker.request_source("video", str(video_path))

    @QtCore.pyqtSlot()
    def open_camera(self) -> None:
        """打开本地摄像头编号或配置好的网络摄像头流。"""
        camera_source = os.environ.get("CAMERA_SOURCE_VALUE", "0")
        self.append_log("正在打开摄像头：{}".format(camera_source))
        self.worker.request_source("camera", camera_source)

    @QtCore.pyqtSlot()
    def open_promotional_video(self) -> None:
        if (
            self.promotional_dialog is not None
            and self.promotional_dialog.isVisible()
        ):
            self.promotional_dialog.raise_()
            self.promotional_dialog.activateWindow()
            return

        dialog = PromotionalVideoDialog(self)
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_promotional_dialog(current)
        )
        self.promotional_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self.append_log("正在打开垃圾分类宣传视频")

    def _clear_promotional_dialog(
        self,
        dialog: PromotionalVideoDialog,
    ) -> None:
        if self.promotional_dialog is dialog:
            self.promotional_dialog = None

    def _set_processing(self, enabled: bool) -> None:
        self._processing = enabled
        if enabled:
            self.worker.start_processing()
            self.start_button.setText("暂停识别")
            if self.source_label.text().startswith("摄像头"):
                self.update_system_state("摄像头识别中")
            else:
                self.update_system_state("视频识别中")
        else:
            self.worker.pause_processing()
            self.start_button.setText("开始识别")
            self.update_system_state("已暂停")

    @QtCore.pyqtSlot()
    def toggle_processing(self) -> None:
        self._set_processing(not self._processing)
        self.append_log("视觉识别已{}".format("启动" if self._processing else "暂停"))

    @QtCore.pyqtSlot(str)
    def on_source_changed(self, display_name: str) -> None:
        self.source_label.setText(display_name)
        self.source_label.setToolTip(display_name)
        self.update_fps(0)
        self.camera_label.clear()
        self.update_detection(None)
        if display_name.startswith("摄像头"):
            self.source_mode_label.setText("摄像头模式")
            self.camera_label.setText("摄像头已连接，正在等待画面…")
            self.update_system_state("摄像头识别中")
            if not self._processing:
                self._set_processing(True)
        else:
            self.source_mode_label.setText("视频文件")
            self.camera_label.setText("视频已就绪，正在等待首帧…")
            self.update_system_state("视频已就绪")
            if not self._processing:
                self.start_button.setText("开始识别")

    @QtCore.pyqtSlot()
    def on_source_finished(self) -> None:
        self._processing = False
        self.start_button.setText("重新播放")
        self.camera_label.clear()
        self.camera_label.setText("视频播放完成\n点击“重新播放”从头开始")
        self.update_detection(None)

    @QtCore.pyqtSlot()
    def on_slider_pressed(self) -> None:
        self._slider_dragging = True

    @QtCore.pyqtSlot(int)
    def on_slider_moved(self, value: int) -> None:
        self.progress_label.setText("{0} / {1} 帧".format(value + 1, self._video_frame_count))

    @QtCore.pyqtSlot()
    def on_slider_released(self) -> None:
        self._slider_dragging = False
        frame_index = self.progress_slider.value()
        self.worker.request_seek(frame_index)
        if not self._processing:
            self._set_processing(True)
        self.append_log("请求跳转到第 {} 帧".format(frame_index + 1))

    @QtCore.pyqtSlot(int, int)
    def update_progress(self, current_frame: int, frame_count: int) -> None:
        self._video_frame_count = max(0, frame_count)
        is_video = self._video_frame_count > 0
        self.progress_slider.setEnabled(is_video)
        if not is_video:
            self.progress_slider.setRange(0, 0)
            self.progress_slider.setValue(0)
            self.progress_label.setText("实时输入")
            return

        last_frame = self._video_frame_count - 1
        self.progress_slider.setRange(0, last_frame)
        if self._slider_dragging:
            return
        self.progress_slider.setValue(min(max(0, current_frame), last_frame))
        display_frame = min(max(0, current_frame), last_frame)
        self.progress_label.setText(
            "{0} / {1} 帧".format(display_frame + 1, self._video_frame_count)
        )

    @QtCore.pyqtSlot(QtGui.QImage)
    def update_frame(self, image: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        self.camera_label.setPixmap(
            pixmap.scaled(
                self.camera_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    @QtCore.pyqtSlot(str)
    def on_frame_unavailable(self, message: str) -> None:
        self.camera_label.clear()
        self.camera_label.setText(message)
        self.update_detection(None)
        self.update_system_state("摄像头重连中")

    @QtCore.pyqtSlot(object)
    def update_detection(self, detection: Optional[Detection]) -> None:
        if detection is None:
            self.class_label.setText("—")
            self.waste_label.setText("等待识别")
            self.confidence_label.setText("—")
            self.confidence_bar.setValue(0)
            self.result_state_label.setText("等待目标")
            self._set_visual_property(self.waste_label, "category", "neutral")
            self._set_visual_property(self.confidence_bar, "category", "neutral")
            return

        category = {
            WasteType.RECYCLABLE: "recyclable",
            WasteType.KITCHEN: "kitchen",
            WasteType.HAZARDOUS: "hazardous",
            WasteType.OTHER: "other",
        }[detection.waste_type]
        self.class_label.setText(detection.class_name or "—")
        self.waste_label.setText(WASTE_NAMES[detection.waste_type])
        self.confidence_label.setText("{:.1f}%".format(detection.confidence * 100))
        self.confidence_bar.setValue(
            int(round(min(max(detection.confidence, 0.0), 1.0) * 1000))
        )
        self.result_state_label.setText("已识别")
        self._set_visual_property(self.waste_label, "category", category)
        self._set_visual_property(self.confidence_bar, "category", category)

    @QtCore.pyqtSlot(object)
    def update_counts(self, values: dict) -> None:
        for name, value in values.items():
            if name in self.count_labels:
                self.count_labels[name].setText(str(value))

    @QtCore.pyqtSlot(object)
    def update_bins(self, values: dict) -> None:
        for name, is_full in values.items():
            if name in self.bin_labels:
                label = self.bin_labels[name]
                label.setText("满载" if is_full else "正常")
                self._set_visual_property(
                    label,
                    "tone",
                    "error" if is_full else "ok",
                )

    @QtCore.pyqtSlot(str)
    def append_log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        body = message
        tag = None
        tag_color = "#64748b"
        command_name = None
        packet_text = None
        if message.startswith("TX"):
            tag = "[TX]"
            body = message[2:].strip()
            tag_color = "#2563eb"
        elif message.startswith("RX"):
            tag = "[RX]"
            body = message[2:].strip()
            tag_color = "#15803d"
        if any(word in message for word in ("失败", "异常", "不可用", "超时")):
            tag = tag or "[ERR]"
            tag_color = "#dc2626"

        parts = body.split(None, 1)
        command_names = {command.name for command in Command}
        if len(parts) == 2 and parts[0] in command_names:
            command_name = parts[0]
            packet_text = parts[1]

        row = '<span style="color:#94a3b8;">[{}]</span> '.format(timestamp)
        if tag:
            row += (
                '<span style="color:{}; font-weight:700;">{}</span> '
                "&nbsp;".format(tag_color, tag)
            )
        if command_name is not None:
            command_colors = {
                "WASTE_RESULT": "#1d4ed8",
                "ACK": "#15803d",
                "ACTION_DONE": "#7c3aed",
                "BIN_FULL": "#b45309",
                "START_COMPRESS": "#0891b2",
                "ERROR": "#dc2626",
            }
            row += (
                '<span style="color:{}; font-weight:700;">{}</span> '
                '<span style="color:#64748b;">{}</span>'.format(
                    command_colors.get(command_name, "#334155"),
                    command_name,
                    html.escape(packet_text),
                )
            )
        else:
            row += '<span style="color:#334155;">{}</span>'.format(
                html.escape(body).replace("\n", "<br>")
            )

        cursor = self.log_browser.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        if not self.log_browser.document().isEmpty():
            cursor.insertBlock()
        cursor.insertHtml(row)
        self.log_browser.setTextCursor(cursor)
        self.log_browser.ensureCursorVisible()
        self._log_line_count = min(500, self._log_line_count + 1)
        self.log_count_label.setText("{} 条".format(self._log_line_count))

    @QtCore.pyqtSlot(bool)
    def update_connection(self, connected: bool) -> None:
        self.connection_label.setText(
            "●  已连接" if connected else "●  未连接"
        )
        self._set_visual_property(
            self.connection_label,
            "tone",
            "ok" if connected else "error",
        )

    @QtCore.pyqtSlot(str)
    def on_source_failed(self, message: str) -> None:
        self.update_system_state("输入源不可用")
        self.camera_label.clear()
        self.camera_label.setText("摄像头或视频输入不可用")
        self.update_detection(None)
        QtWidgets.QMessageBox.warning(
            self,
            "无法切换图像源",
            message,
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.promotional_dialog is not None:
            self.promotional_dialog.close()
            self.promotional_dialog = None
        self.worker.stop()
        if not self.worker.wait(5000):
            self.append_log("工作线程未在规定时间内退出")
        event.accept()
