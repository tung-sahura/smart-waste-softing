import unittest

from app.protocol import HEADER, MAX_BODY_LENGTH, Command, Packet, StreamParser


class ProtocolTests(unittest.TestCase):
    def test_packet_encoding_uses_documented_length_and_checksum(self):
        packet = Packet(Command.WASTE_RESULT, b"\x11\x03")
        self.assertEqual(
            packet.encode(),
            HEADER + b"\x03\x01\x11\x03\x18",
        )

    def test_packet_encoding_accepts_maximum_payload_and_rejects_larger(self):
        payload = bytes(range(MAX_BODY_LENGTH - 1))
        encoded = Packet(Command.WASTE_RESULT, payload).encode()
        self.assertEqual(encoded[2], MAX_BODY_LENGTH)
        self.assertEqual(encoded[3:-1], b"\x01" + payload)

        with self.assertRaises(ValueError):
            Packet(Command.WASTE_RESULT, payload + b"\x00").encode()

    def test_packet_requires_bytes_like_payload(self):
        with self.assertRaises(TypeError):
            Packet(Command.HEARTBEAT, 3).encode()

    def test_packet_requires_a_single_byte_integer_command(self):
        for command in (256, -1, "1", True):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    Packet(command).encode()

    def test_packet_can_arrive_one_byte_at_a_time(self):
        packet = Packet(Command.WASTE_RESULT, b"\x11\x03")
        parser = StreamParser()
        output = []
        for byte in packet.encode():
            output.extend(parser.feed(bytes((byte,))))
        self.assertEqual(output, [packet])

    def test_noise_bad_checksum_and_sticky_packets_are_recovered(self):
        first = Packet(Command.ACK, b"\x01\x11")
        second = Packet(Command.ACTION_DONE, b"\x11")
        damaged = bytearray(first.encode())
        damaged[-1] ^= 0xFF
        parser = StreamParser()
        output = parser.feed(b"noise" + bytes(damaged) + first.encode() + second.encode())
        self.assertEqual(output, [first, second])
        self.assertGreaterEqual(parser.error_count, 1)

    def test_bad_checksum_does_not_skip_a_nested_valid_frame(self):
        valid = Packet(Command.ACK, b"\x01\x11")
        # A false header advertises a length that encloses the valid frame.
        # Resynchronization must find AA 55 at offset 5 after checksum failure.
        damaged = HEADER + b"\x08\x00\x00" + valid.encode()
        parser = StreamParser()
        output = parser.feed(damaged)
        self.assertEqual(output, [valid])
        self.assertGreaterEqual(parser.error_count, 1)

    def test_invalid_length_and_unknown_command_can_resynchronize(self):
        valid = Packet(Command.ACTION_DONE, b"\x22")
        invalid_length = HEADER + b"\x00"
        unknown_command = HEADER + b"\x01\x66\x67"
        parser = StreamParser()
        output = parser.feed(invalid_length + unknown_command + valid.encode())
        self.assertEqual(output, [valid])
        self.assertGreaterEqual(parser.error_count, 2)

    def test_empty_and_invalid_feed_input(self):
        parser = StreamParser()
        self.assertEqual(parser.feed(b""), [])
        with self.assertRaises(TypeError):
            parser.feed(3)


if __name__ == "__main__":
    unittest.main()
