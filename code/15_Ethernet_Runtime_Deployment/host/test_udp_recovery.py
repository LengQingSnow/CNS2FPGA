"""Physical UDP negative test, in two host processes, for a live CNS2FPGA board.

Run ``interrupt`` then ``reject`` with no FPGA reprogramming in between. The
second phase leaves the image invalid; a normal, fully preflighted upload must
then recover it. Use only on an isolated lab link and never concurrently with
JTAG access. This tool intentionally changes the loaded graph state.
"""

from __future__ import annotations

import argparse
import socket
import struct
import time


REQUEST = struct.Struct("<4sBBHII")
RESPONSE = struct.Struct("<4sBBBBII")


def exchange(sock: socket.socket, target: tuple[str, int], opcode: int,
             region: int, count: int, sequence: int, value: int = 0,
             words: tuple[int, ...] = ()) -> tuple[int, int]:
    packet = REQUEST.pack(b"CNSE", opcode, region, count, sequence, value)
    packet += struct.pack(f"<{len(words)}I", *words)
    for _ in range(5):
        sock.sendto(packet, target)
        deadline = time.monotonic() + sock.gettimeout()
        while time.monotonic() < deadline:
            try:
                reply, peer = sock.recvfrom(2048)
            except socket.timeout:
                break
            if peer != target or len(reply) != RESPONSE.size:
                continue
            magic, status, ack_opcode, ack_region, reserved, ack_sequence, image_status = RESPONSE.unpack(reply)
            if (magic, ack_opcode, ack_region, reserved, ack_sequence) != (
                b"CNSA", opcode, region, 0, sequence
            ):
                continue
            return status, image_status
    raise TimeoutError(f"No valid ACK for opcode={opcode} sequence={sequence}")


def require(actual: tuple[int, int], expected: tuple[int, int], label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: ACK={actual} != {expected}")
    print(f"{label}_PASS ack_status={actual[0]} image_status=0x{actual[1]:08X}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("interrupt", "reject"))
    parser.add_argument("--source-ip", default="192.168.1.10")
    parser.add_argument("--board-ip", default="192.168.1.128")
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()
    if args.timeout <= 0 or not 1 <= args.port <= 65535:
        parser.error("Invalid port or timeout")
    target = (args.board_ip, args.port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.source_ip, 0))
        sock.settimeout(args.timeout)
        if args.phase == "interrupt":
            # BEGIN always starts a new sequence and invalidates the old graph.
            require(exchange(sock, target, 1, 0, 226, 1, 1730), (0, 2), "P0_UDP_BEGIN")
            require(exchange(sock, target, 2, 0, 1, 2, words=(0,)),
                    (0, 2), "P0_UDP_PARTIAL_DATA")
            print("P0_UDP_HOST_INTERRUPTED_PASS; close socket before COMMIT", flush=True)
        else:
            # This process proves partial load state survives a host reconnect.
            require(exchange(sock, target, 4, 0, 0, 3), (0, 2),
                    "P0_UDP_PARTIAL_STATE")
            require(exchange(sock, target, 3, 0, 0, 4, 0), (3, 0x16),
                    "P0_UDP_INCOMPLETE_REJECT")
            require(exchange(sock, target, 1, 0, 226, 1, 1730), (0, 2),
                    "P0_UDP_RESTART_BEGIN")
            # Low synapse lane holds the post index. 226 is outside [0,225].
            require(exchange(sock, target, 2, 1, 1, 2, words=(226,)),
                    (3, 0x66), "P0_UDP_BAD_POST_REJECT")
            print("P0_UDP_RECOVERY_REQUIRED: upload a valid image with the normal uploader", flush=True)


if __name__ == "__main__":
    main()
