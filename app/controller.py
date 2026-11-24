"""与 UI 无关的分拣状态机骨架。"""

import time
from enum import Enum
from typing import Callable, Dict, Optional

from .detectors import Detection
from .protocol import Command, Packet, WasteType, WASTE_NAMES
from .transport import Transport, TransportError


class SystemState(Enum):
    IDLE = "等待识别"
    WAIT_ACK = "等待下位机确认"
    EXECUTING = "下位机执行中"
    COOLDOWN = "等待物体离开"
    COMPRESSING = "压缩中"
    PAUSED = "已暂停"
    ERROR = "通信异常"


EventCallback = Callable[[str, dict], None]


class SortingController:
    def __init__(
        self,
        transport: Transport,
        event_callback: Optional[EventCallback] = None,
        stable_frames: int = 3,
        ack_timeout: float = 2.0,
        max_retries: int = 2,
        compress_after: int = 20,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport
        self.event_callback = event_callback or (lambda _name, _data: None)
        self.stable_frames = stable_frames
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        self.compress_after = compress_after
        self.clock = clock
        self.counts = {item: 0 for item in WasteType}
        self.bin_full = {item: False for item in WasteType}
        self.state = SystemState.IDLE
        self.pending = None  # type: Optional[WasteType]
        self._candidate = None  # type: Optional[WasteType]
        self._stable_count = 0
        self._missing_frames = 0
        self._last_packet = None  # type: Optional[Packet]
        self._deadline = 0.0
        self._retry_count = 0
        self._compress_sent = False
        self._sequence = 0
        self._active_sequence = None  # type: Optional[int]

    def _emit(self, name: str, **data) -> None:
        self.event_callback(name, data)

    def _set_state(self, state: SystemState) -> None:
        if state != self.state:
            self.state = state
            self._emit("state", value=state.value)

    def reset(self) -> None:
        self.counts = {item: 0 for item in WasteType}
        self.bin_full = {item: False for item in WasteType}
        self.pending = None
        self._candidate = None
        self._stable_count = 0
        self._missing_frames = 0
        self._last_packet = None
        self._deadline = 0.0
        self._retry_count = 0
        self._compress_sent = False
        self._active_sequence = None
        self._set_state(SystemState.IDLE)
        self._emit("counts", values=self.named_counts())
        self._emit("bins", values=self.named_bins())

    def named_counts(self) -> Dict[str, int]:
        return {WASTE_NAMES[key]: value for key, value in self.counts.items()}

    def named_bins(self) -> Dict[str, bool]:
        return {WASTE_NAMES[key]: value for key, value in self.bin_full.items()}

    def process_detection(self, detection: Optional[Detection]) -> None:
        """用连续稳定帧触发一次分类，并在物体离开前保持冷却。"""
        if self.state is SystemState.COOLDOWN:
            if detection is None:
                self._candidate = None
                self._stable_count = 0
                self._missing_frames += 1
                self._set_state(SystemState.IDLE)
            else:
                self._missing_frames = 0
            return

        if self.state is not SystemState.IDLE:
            return

        if detection is None:
            self._candidate = None
            self._stable_count = 0
            self._missing_frames += 1
            return

        self._missing_frames = 0
        if self._candidate == detection.waste_type:
            self._stable_count += 1
        else:
            self._candidate = detection.waste_type
            self._stable_count = 1

        if self._stable_count < self.stable_frames:
            return

        waste_type = detection.waste_type
        if self.bin_full[waste_type]:
            self._candidate = None
            self._stable_count = 0
            self._set_state(SystemState.COOLDOWN)
            self._emit(
                "log",
                message="{}桶已满，停止发送该类别".format(WASTE_NAMES[waste_type]),
            )
            return

        self._send_classification(waste_type)

    def _enter_error(self, message: str) -> None:
        self.pending = None
        self._candidate = None
        self._stable_count = 0
        self._last_packet = None
        self._active_sequence = None
        self._deadline = 0.0
        self._retry_count = 0
        self._set_state(SystemState.ERROR)
        self._emit("log", message=message)

    def _transmit(self, packet: Packet) -> bool:
        try:
            self.transport.send(packet)
        except TransportError as exc:
            self._enter_error("发送失败：{}".format(exc))
            return False
        command_name = (
            packet.command.name
            if isinstance(packet.command, Command)
            else str(packet.command)
        )
        self._emit(
            "tx",
            packet=packet.encode().hex(" ").upper(),
            command=command_name,
        )
        return True

    def _send_packet(self, packet: Packet, wait_for_reply: bool = True) -> bool:
        if not self._transmit(packet):
            return False
        if wait_for_reply:
            self._last_packet = packet
            self._deadline = self.clock() + self.ack_timeout
            self._retry_count = 0
        return True

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence

    def _send_classification(self, waste_type: WasteType) -> bool:
        """发送分类请求；超时重试时复用当前序号和原 Packet。"""
        if self.bin_full[waste_type]:
            self._set_state(SystemState.COOLDOWN)
            return False

        sequence = self._next_sequence()
        packet = Packet(
            Command.WASTE_RESULT,
            bytes((sequence, int(waste_type))),
        )
        self.pending = waste_type
        self._active_sequence = sequence
        if not self._send_packet(packet):
            self.pending = None
            self._active_sequence = None
            return False

        self._candidate = None
        self._stable_count = 0
        self._set_state(SystemState.WAIT_ACK)
        self._emit(
            "log",
            message="已发送 WASTE_RESULT，序号 {}".format(sequence),
        )
        return True

    def poll(self) -> None:
        """轮询接收，并在 ACK 超时时用原序号重发。"""
        try:
            packets = self.transport.poll()
        except TransportError as exc:
            self._enter_error("接收失败：{}".format(exc))
            return

        for packet in packets:
            command_name = (
                packet.command.name
                if isinstance(packet.command, Command)
                else str(packet.command)
            )
            self._emit(
                "rx",
                packet=packet.encode().hex(" ").upper(),
                command=command_name,
            )
            self.handle_packet(packet)

        if (
            self.state is SystemState.WAIT_ACK
            and self._last_packet is not None
            and self.clock() >= self._deadline
        ):
            if self._retry_count >= self.max_retries:
                self._enter_error(
                    "等待 ACK 超时，重试 {} 次后进入错误状态".format(
                        self._retry_count
                    )
                )
                return

            packet = self._last_packet
            if not self._transmit(packet):
                return
            self._retry_count += 1
            self._deadline = self.clock() + self.ack_timeout
            self._emit(
                "log",
                message="ACK 超时，使用原序号 {} 重发（{}/{}）".format(
                    self._active_sequence,
                    self._retry_count,
                    self.max_retries,
                ),
            )

    def handle_packet(self, packet: Packet) -> None:
        """处理下位机回复，只接受与当前动作匹配的 ACK 和完成消息。"""
        if packet.command == Command.ACK:
            self._handle_ack(packet)
        elif packet.command == Command.ACTION_DONE:
            self._handle_action_done(packet)
        elif packet.command == Command.BIN_FULL:
            self._handle_bin_full(packet)
        elif packet.command == Command.ERROR:
            text = packet.payload.decode("utf-8", errors="replace")
            self._enter_error("下位机错误：{}".format(text or "未知错误"))

    def _handle_ack(self, packet: Packet) -> None:
        if (
            self.state is not SystemState.WAIT_ACK
            or self._last_packet is None
            or self._active_sequence is None
            or len(packet.payload) < 2
        ):
            return

        original_command = packet.payload[0]
        sequence = packet.payload[1]
        if (
            original_command != int(self._last_packet.command)
            or sequence != self._active_sequence
        ):
            self._emit("log", message="忽略不匹配的 ACK")
            return

        self._deadline = 0.0
        self._retry_count = 0
        if self._last_packet.command == Command.WASTE_RESULT:
            self._set_state(SystemState.EXECUTING)
        else:
            self._set_state(SystemState.COMPRESSING)

    def _handle_action_done(self, packet: Packet) -> None:
        if (
            self.state not in (SystemState.EXECUTING, SystemState.COMPRESSING)
            or self._last_packet is None
            or self._active_sequence is None
            or len(packet.payload) < 1
            or packet.payload[0] != self._active_sequence
        ):
            self._emit("log", message="忽略不匹配的 ACTION_DONE")
            return

        command = self._last_packet.command
        if command == Command.WASTE_RESULT and self.pending is not None:
            self.counts[self.pending] += 1
            self._emit("counts", values=self.named_counts())
            self._emit(
                "log",
                message="{}分拣完成，数量 {}".format(
                    WASTE_NAMES[self.pending],
                    self.counts[self.pending],
                ),
            )
        elif command == Command.START_COMPRESS:
            self._compress_sent = True
            self._emit("log", message="压缩动作完成")

        self.pending = None
        self._last_packet = None
        self._active_sequence = None
        self._deadline = 0.0
        self._retry_count = 0
        self._candidate = None
        self._stable_count = 0
        self._set_state(SystemState.COOLDOWN)

        if command == Command.WASTE_RESULT:
            self._maybe_compress()

    def _handle_bin_full(self, packet: Packet) -> None:
        if not packet.payload:
            self._emit("log", message="忽略缺少垃圾类型的 BIN_FULL")
            return
        try:
            waste_type = WasteType(packet.payload[0])
        except ValueError:
            self._emit("log", message="忽略未知垃圾类型的 BIN_FULL")
            return

        self.bin_full[waste_type] = True
        self._emit("bins", values=self.named_bins())
        self._emit(
            "log",
            message="{}桶已满".format(WASTE_NAMES[waste_type]),
        )

    def _maybe_compress(self) -> None:
        """达到完成数量阈值后发送一次压缩动作。"""
        if (
            self._compress_sent
            or self.pending is not None
            or sum(self.counts.values()) < self.compress_after
        ):
            return

        sequence = self._next_sequence()
        packet = Packet(Command.START_COMPRESS, bytes((sequence,)))
        self._active_sequence = sequence
        self._compress_sent = True
        if not self._send_packet(packet):
            self._active_sequence = None
            self._compress_sent = False
            return

        self._set_state(SystemState.WAIT_ACK)
        self._emit(
            "log",
            message="成功分拣数量达到阈值，发送 START_COMPRESS，序号 {}".format(
                sequence
            ),
        )
