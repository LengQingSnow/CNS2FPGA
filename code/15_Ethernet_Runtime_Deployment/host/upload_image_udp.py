"""Reliably stream a preflighted CNS2FPGA image to the AXKU115 UDP loader.

The board uses stop-and-wait acknowledgements and sequence de-duplication.
No FPGA programming operation occurs in this tool.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import subprocess
import sys
from pathlib import Path


REQUEST = struct.Struct("<4sBBHII")
RESPONSE = struct.Struct("<4sBBBBII")
PORT = 4321
REGIONS = (
    ("neuron_param", 32, 4),
    ("synapse", 16, 2),
    ("offset", 8, 1),
    ("type_sign", 4, 1),
)


def image_manifest(image_dir: Path) -> dict:
    validator = (
        Path(__file__).resolve().parents[2]
        / "14_Runtime Reconfigurable Deployment"
        / "host"
        / "prepare_image.py"
    )
    result = subprocess.run(
        [sys.executable, str(validator), str(image_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def region_words(image_dir: Path, name: str, width: int, lanes: int):
    with (image_dir / f"{name}.mem").open(encoding="ascii") as stream:
        for record in stream:
            record = record.strip()
            if len(record) != width:
                raise ValueError(f"Malformed {name} record")
            if name == "type_sign":
                yield int(record, 16)
            else:
                for lane in range(lanes):
                    start = width - 8 * (lane + 1)
                    yield int(record[start : start + 8], 16)


def send_command(
    sock: socket.socket,
    target: tuple[str, int],
    opcode: int,
    region: int,
    count: int,
    sequence: int,
    value: int,
    words: list[int],
    retries: int,
) -> int:
    packet = REQUEST.pack(b"CNSE", opcode, region, count, sequence, value)
    if words:
        packet += struct.pack(f"<{len(words)}I", *words)
    for attempt in range(retries + 1):
        sock.sendto(packet, target)
        try:
            while True:
                response, peer = sock.recvfrom(2048)
                if peer[0] != target[0] or peer[1] != target[1]:
                    continue
                if len(response) != RESPONSE.size:
                    raise RuntimeError(f"Malformed ACK length: {len(response)}")
                magic, status, ack_opcode, ack_region, _, ack_seq, image_status = RESPONSE.unpack(response)
                if magic != b"CNSA" or ack_opcode != opcode or ack_region != region or ack_seq != sequence:
                    continue
                if status not in (0, 4):
                    raise RuntimeError(
                        f"FPGA rejected seq={sequence} opcode={opcode}: "
                        f"status={status} image_status=0x{image_status:08X}"
                    )
                if status == 0 and opcode in (1, 2) and image_status != 2:
                    raise RuntimeError(f"Unexpected upload state: 0x{image_status:08X}")
                if status == 0 and opcode == 3 and image_status != 1:
                    raise RuntimeError(f"Image COMMIT failed: 0x{image_status:08X}")
                return image_status
        except socket.timeout:
            if attempt == retries:
                raise TimeoutError(f"No ACK for sequence {sequence}") from None
    raise AssertionError("Unreachable retry loop")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("--board-ip", default="192.168.1.128")
    parser.add_argument("--source-ip", default="")
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    image_dir = args.image_dir.resolve(strict=True)
    manifest = image_manifest(image_dir)
    neurons = int(manifest["neurons"])
    synapses = int(manifest["synapses"])
    checksum = int(manifest["checksum_hex"], 16)
    total_words = 0
    packets = 3  # BEGIN, COMMIT and independent STATUS verification
    for name, _, lanes in REGIONS:
        records = synapses if name == "synapse" else neurons
        words = records * lanes
        total_words += words
        packets += (words + 63) // 64
    print(f"PREFLIGHT neurons={neurons} synapses={synapses} words={total_words} "
          f"packets={packets} checksum={checksum:08X}", flush=True)
    if args.dry_run:
        return

    target = (args.board_ip, PORT)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.source_ip, 0))
        sock.settimeout(args.timeout)
        sequence = 1
        send_command(sock, target, 1, 0, neurons, sequence, synapses, [], args.retries)
        sequence += 1
        sent_words = 0
        for region, (name, width, lanes) in enumerate(REGIONS):
            chunk: list[int] = []
            for word in region_words(image_dir, name, width, lanes):
                chunk.append(word)
                if len(chunk) == 64:
                    send_command(sock, target, 2, region, len(chunk), sequence, 0, chunk, args.retries)
                    sequence += 1
                    sent_words += len(chunk)
                    chunk.clear()
                    if sent_words % 8192 == 0:
                        print(f"UPLOAD words={sent_words}/{total_words} region={name}", flush=True)
            if chunk:
                send_command(sock, target, 2, region, len(chunk), sequence, 0, chunk, args.retries)
                sequence += 1
                sent_words += len(chunk)
        if sent_words != total_words:
            raise AssertionError(f"Transferred {sent_words} != {total_words} words")
        send_command(sock, target, 3, 0, 0, sequence, checksum, [], args.retries)
        # A lost COMMIT ACK can be satisfied by a duplicate response. Query the
        # committed engine state separately so that case is verified too.
        sequence += 1
        final_status = send_command(sock, target, 4, 0, 0, sequence, 0, [], args.retries)
        if final_status != 1:
            raise RuntimeError(f"Image not ready after COMMIT: 0x{final_status:08X}")
    print(f"ETHERNET_IMAGE_COMMIT_PASS words={sent_words} checksum={checksum:08X}", flush=True)


if __name__ == "__main__":
    main()
