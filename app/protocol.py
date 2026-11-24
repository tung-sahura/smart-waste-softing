"""上位机通信协议骨架。

帧格式请阅读仓库根目录的 ``PROTOCOL.md``。本文件中的两个 TODO 是通信
模块的核心考核点：封包和流式拆包。请勿假设一次 ``recv`` 恰好得到一帧。
"""

from dataclasses import dataclass
from enum import IntEnum
import operator
from typing import List


HEADER = b"\xAA\x55"
MAX_BODY_LENGTH = 64


class Command(IntEnum):
    WASTE_RESULT = 0x01
    ACK = 0x02
    ACTION_DONE = 0x03
    BIN_FULL = 0x04
    START_COMPRESS = 0x05
    HEARTBEAT = 0x06
    ERROR = 0x7F


class WasteType(IntEnum):
    HAZARDOUS = 0x01
    OTHER = 0x02
    RECYCLABLE = 0x03
    KITCHEN = 0x04


WASTE_NAMES = {
    WasteType.RECYCLABLE: "可回收垃圾",
    WasteType.KITCHEN: "厨余垃圾",
    WasteType.HAZARDOUS: "有害垃圾",
    WasteType.OTHER: "其他垃圾",
}


@dataclass(frozen=True)
class Packet:
    command: Command
    payload: bytes = b""

    def encode(self) -> bytes:
        """按协议生成完整二进制帧。"""
        try:
            payload = memoryview(self.payload).tobytes()
        except (TypeError, ValueError) as exc:
            raise TypeError("PAYLOAD 必须是 bytes-like 数据") from exc

        length = 1 + len(payload)
        if not 1 <= length <= MAX_BODY_LENGTH:
            raise ValueError(
                "帧体长度必须在 1 到 {} 字节之间".format(MAX_BODY_LENGTH)
            )

        try:
            if isinstance(self.command, bool):
                raise TypeError
            command = operator.index(self.command)
        except TypeError as exc:
            raise ValueError("COMMAND 必须是单字节整数") from exc
        if not 0 <= command <= 0xFF:
            raise ValueError("COMMAND 必须是单字节整数")

        body = bytes((command,)) + payload
        checksum = (length + sum(body)) & 0xFF
        return HEADER + bytes((length,)) + body + bytes((checksum,))


class StreamParser:
    """把任意分片的 TCP/串口字节流增量解析为 Packet。"""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.error_count = 0

    def reset(self) -> None:
        self._buffer.clear()
        self.error_count = 0

    def feed(self, data: bytes) -> List[Packet]:
        """支持半包、粘包、噪声和错误校验后的重新同步。"""
        try:
            chunk = memoryview(data).tobytes()
        except (TypeError, ValueError) as exc:
            raise TypeError("feed 只接受 bytes-like 数据") from exc
        self._buffer.extend(chunk)

        packets = []
        while True:
            header_index = self._buffer.find(HEADER)
            if header_index < 0:
                if self._buffer[-1:] == HEADER[:1]:
                    # The 0xAA may be the first byte of a header split across feeds.
                    if len(self._buffer) > 1:
                        self.error_count += 1
                    del self._buffer[:-1]
                else:
                    if self._buffer:
                        self.error_count += 1
                        self._buffer.clear()
                break

            if header_index > 0:
                self.error_count += 1
                del self._buffer[:header_index]

            # Header and LENGTH are not complete yet.
            if len(self._buffer) < 3:
                break

            length = self._buffer[2]
            if not 1 <= length <= MAX_BODY_LENGTH:
                self.error_count += 1
                # Skip only this false header so another header later can be found.
                del self._buffer[0]
                continue

            frame_length = 2 + 1 + length + 1
            if len(self._buffer) < frame_length:
                break

            body = bytes(self._buffer[3 : 3 + length])
            received_checksum = self._buffer[3 + length]
            expected_checksum = (length + sum(body)) & 0xFF
            if received_checksum != expected_checksum:
                self.error_count += 1
                # The advertised length is untrusted after a checksum failure.
                # Drop only this header and search again so a valid frame nested
                # inside the damaged candidate is not skipped.
                del self._buffer[0]
                continue

            try:
                command = Command(body[0])
            except ValueError:
                self.error_count += 1
                del self._buffer[:frame_length]
                continue

            packets.append(Packet(command, body[1:]))
            del self._buffer[:frame_length]

        return packets
