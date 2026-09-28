"""Read-only Ethernet connectivity probe for the AXKU115 runtime loader.

Sends only the CNSE STATUS command (opcode 4). It does not begin an upload,
write graph data, program the FPGA, or modify runtime image memory.
"""

from __future__ import annotations

import argparse
import socket
import struct
import time


REQUEST = struct.Struct("<4sBBHII")
RESPONSE = struct.Struct("<4sBBBBII")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ip", default="192.168.1.10")
    parser.add_argument("--board-ip", default="192.168.1.128")
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--sequence", type=int, default=1,
                        help="next expected sequence after earlier commands; default 1 for a fresh board")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.timeout <= 0 or args.attempts < 1 or not 1 <= args.sequence <= 0xFFFFFFFF:
        parser.error("port, timeout, attempts, and sequence must be in range")

    target = (args.board_ip, args.port)
    packet = REQUEST.pack(b"CNSE", 4, 0, 0, args.sequence, 0)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((args.source_ip, 0))
            sock.settimeout(args.timeout)
            for attempt in range(1, args.attempts + 1):
                start = time.perf_counter()
                sock.sendto(packet, target)
                try:
                    while True:
                        reply, peer = sock.recvfrom(2048)
                        if peer != target or len(reply) != RESPONSE.size:
                            continue
                        magic, status, opcode, region, reserved, sequence, image_status = RESPONSE.unpack(reply)
                        if (magic, opcode, region, reserved, sequence) != (b"CNSA", 4, 0, 0, args.sequence):
                            continue
                        if status not in (0, 4):
                            raise RuntimeError(
                                f"Board responded with protocol error status={status}, "
                                f"image_status=0x{image_status:08X}"
                            )
                        elapsed_ms = (time.perf_counter() - start) * 1000
                        print(
                            f"ETHERNET_STATUS_PASS peer={peer[0]}:{peer[1]} "
                            f"ack_status={status} image_status=0x{image_status:08X} "
                            f"attempt={attempt} rtt_ms={elapsed_ms:.2f}"
                        )
                        return
                except socket.timeout:
                    print(f"ETHERNET_STATUS_TIMEOUT attempt={attempt}/{args.attempts}", flush=True)
    except OSError as exc:
        raise SystemExit(f"Network socket failed: {exc}") from exc
    raise SystemExit("ETHERNET_STATUS_FAIL: no valid read-only STATUS reply")


if __name__ == "__main__":
    main()
