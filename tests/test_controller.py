import unittest

from app.controller import SortingController, SystemState
from app.detectors import Detection
from app.protocol import Command, Packet, WasteType
from app.transport import MemoryTransport


class FakeClock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.transport = MemoryTransport()
        self.transport.connect()
        self.clock = FakeClock()
        self.events = []
        self.controller = SortingController(
            self.transport,
            lambda name, data: self.events.append((name, data)),
            clock=self.clock,
        )
        self.detection = Detection(WasteType.RECYCLABLE, "blue-token", 0.9, (1, 2, 3, 4))

    def test_stable_detection_drives_one_complete_sort_cycle(self):
        for _ in range(3):
            self.controller.process_detection(self.detection)
        self.assertEqual(self.controller.state, SystemState.WAIT_ACK)
        self.assertEqual(len(self.transport.sent), 1)
        sent = self.transport.sent[0]
        self.assertEqual(sent.command, Command.WASTE_RESULT)
        self.assertEqual(sent.payload[1], WasteType.RECYCLABLE)
        sequence = sent.payload[0]

        self.transport.feed(Packet(Command.ACK, bytes((Command.WASTE_RESULT, sequence))))
        self.controller.poll()
        self.assertEqual(self.controller.state, SystemState.EXECUTING)

        self.transport.feed(Packet(Command.ACTION_DONE, bytes((sequence,))))
        self.controller.poll()
        self.assertEqual(self.controller.counts[WasteType.RECYCLABLE], 1)
        self.assertEqual(self.controller.state, SystemState.COOLDOWN)
        command_events = [
            (name, data["command"])
            for name, data in self.events
            if name in ("tx", "rx")
        ]
        self.assertEqual(
            command_events,
            [
                ("tx", "WASTE_RESULT"),
                ("rx", "ACK"),
                ("rx", "ACTION_DONE"),
            ],
        )

    def test_timeout_retries_then_enters_error(self):
        for _ in range(3):
            self.controller.process_detection(self.detection)
        original_sequence = self.controller._active_sequence
        for _ in range(3):
            self.clock.advance(2.1)
            self.controller.poll()
        self.assertEqual(self.controller.state, SystemState.ERROR)
        self.assertEqual(len(self.transport.sent), 3)
        self.assertEqual(
            {packet.payload[0] for packet in self.transport.sent},
            {original_sequence},
        )

    def test_full_bin_prevents_sending_that_category(self):
        self.controller.handle_packet(Packet(Command.BIN_FULL, bytes((WasteType.RECYCLABLE,))))
        for _ in range(3):
            self.controller.process_detection(self.detection)
        self.assertEqual(self.transport.sent, [])
        self.assertEqual(self.controller.state, SystemState.COOLDOWN)

    def test_stable_frames_must_be_consecutive(self):
        for _ in range(2):
            self.controller.process_detection(self.detection)
        self.controller.process_detection(None)
        self.controller.process_detection(self.detection)
        self.assertEqual(self.controller.state, SystemState.IDLE)
        self.assertEqual(self.transport.sent, [])

    def test_cooldown_prevents_duplicate_until_object_leaves(self):
        for _ in range(3):
            self.controller.process_detection(self.detection)
        sent = self.transport.sent[0]
        sequence = sent.payload[0]
        self.transport.feed(Packet(Command.ACK, bytes((Command.WASTE_RESULT, sequence))))
        self.controller.poll()
        self.transport.feed(Packet(Command.ACTION_DONE, bytes((sequence,))))
        self.controller.poll()

        for _ in range(3):
            self.controller.process_detection(self.detection)
        self.assertEqual(len(self.transport.sent), 1)
        self.assertEqual(self.controller.state, SystemState.COOLDOWN)

        self.controller.process_detection(None)
        self.assertEqual(self.controller.state, SystemState.IDLE)

    def test_mismatched_replies_do_not_change_count_or_sequence(self):
        for _ in range(3):
            self.controller.process_detection(self.detection)
        sequence = self.transport.sent[0].payload[0]
        wrong_sequence = (sequence + 1) & 0xFF

        self.transport.feed(
            Packet(Command.ACK, bytes((Command.WASTE_RESULT, wrong_sequence)))
        )
        self.controller.poll()
        self.assertEqual(self.controller.state, SystemState.WAIT_ACK)

        self.transport.feed(Packet(Command.ACK, bytes((Command.WASTE_RESULT, sequence))))
        self.controller.poll()
        self.assertEqual(self.controller.state, SystemState.EXECUTING)
        self.assertEqual(self.controller.counts[WasteType.RECYCLABLE], 0)

        self.transport.feed(Packet(Command.ACTION_DONE, bytes((wrong_sequence,))))
        self.controller.poll()
        self.assertEqual(self.controller.counts[WasteType.RECYCLABLE], 0)

    def test_threshold_sends_compression_once_without_changing_count(self):
        controller = SortingController(
            self.transport,
            lambda name, data: self.events.append((name, data)),
            compress_after=2,
            clock=self.clock,
        )

        for _ in range(2):
            if controller.state is SystemState.COOLDOWN:
                controller.process_detection(None)
            for _ in range(3):
                controller.process_detection(self.detection)

            packet = self.transport.sent[-1]
            sequence = packet.payload[0]
            self.transport.feed(
                Packet(Command.ACK, bytes((Command.WASTE_RESULT, sequence)))
            )
            controller.poll()
            self.transport.feed(Packet(Command.ACTION_DONE, bytes((sequence,))))
            controller.poll()

        compression = self.transport.sent[-1]
        self.assertEqual(compression.command, Command.START_COMPRESS)
        self.assertEqual(controller.state, SystemState.WAIT_ACK)
        self.assertEqual(controller.counts[WasteType.RECYCLABLE], 2)

        sequence = compression.payload[0]
        self.transport.feed(
            Packet(Command.ACK, bytes((Command.START_COMPRESS, sequence)))
        )
        controller.poll()
        self.assertEqual(controller.state, SystemState.COMPRESSING)
        self.transport.feed(Packet(Command.ACTION_DONE, bytes((sequence,))))
        controller.poll()
        self.assertEqual(controller.state, SystemState.COOLDOWN)
        self.assertEqual(controller.counts[WasteType.RECYCLABLE], 2)
        self.assertEqual(
            [packet.command for packet in self.transport.sent].count(
                Command.START_COMPRESS
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
