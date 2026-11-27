import unittest

from app.protocol import StreamParser
from simulator.lower_simulator import LowerComputerSimulator
from simulator.protocol_reference import Command, Packet, WasteType


class FakeSocket:
    def __init__(self):
        self.data = bytearray()

    def sendall(self, data):
        self.data.extend(data)

    def take_packets(self):
        output = StreamParser().feed(bytes(self.data))
        self.data.clear()
        return output


class LowerSimulatorTests(unittest.TestCase):
    def test_each_bin_becomes_full_after_three_sorts_of_its_category(self):
        simulator = LowerComputerSimulator(action_delay=0)
        client = FakeSocket()
        completed = set()
        sequence = 0

        for round_number in range(1, 4):
            for waste_type in WasteType:
                sequence += 1
                simulator._handle_packet(
                    client,
                    Packet(
                        Command.WASTE_RESULT,
                        bytes((sequence, int(waste_type))),
                    ),
                    completed,
                )
                packets = client.take_packets()
                full_events = [
                    packet for packet in packets if packet.command == Command.BIN_FULL
                ]
                if round_number < 3:
                    self.assertEqual(full_events, [])
                else:
                    self.assertEqual(len(full_events), 1)
                    self.assertEqual(full_events[0].payload, bytes((int(waste_type),)))

        self.assertEqual(simulator.sort_counts, {item: 3 for item in WasteType})
        self.assertEqual(simulator.full_bins, set(WasteType))


if __name__ == "__main__":
    unittest.main()
