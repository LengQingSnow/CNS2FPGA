"""Bit-field packing and Xilinx-compatible hexadecimal memory files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Field:
    name: str
    lsb: int
    width: int
    signed: bool = False

    @property
    def msb(self) -> int:
        return self.lsb + self.width - 1


class RecordLayout:
    def __init__(self, name: str, width: int, fields: list[Field]):
        if width <= 0 or width % 4:
            raise ValueError("Record width must be a positive multiple of four")
        self.name, self.width, self.fields = name, width, tuple(fields)
        occupied = set()
        for field in self.fields:
            if field.width <= 0 or field.lsb < 0 or field.msb >= width:
                raise ValueError(f"Invalid field {field.name}")
            bits = set(range(field.lsb, field.msb + 1))
            if occupied & bits:
                raise ValueError(f"Overlapping field {field.name}")
            occupied |= bits
        if len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("Field names must be unique")

    def pack(self, values: dict[str, int]) -> int:
        unknown = set(values) - {field.name for field in self.fields}
        if unknown:
            raise KeyError(f"Unknown fields for {self.name}: {sorted(unknown)}")
        record = 0
        for field in self.fields:
            value = int(values.get(field.name, 0))
            if field.signed:
                low, high = -(1 << (field.width - 1)), (1 << (field.width - 1)) - 1
            else:
                low, high = 0, (1 << field.width) - 1
            if value < low or value > high:
                raise OverflowError(f"{self.name}.{field.name}={value} outside [{low}, {high}]")
            encoded = value & ((1 << field.width) - 1)
            record |= encoded << field.lsb
        return record

    def unpack(self, record: int) -> dict[str, int]:
        if record < 0 or record >= (1 << self.width):
            raise OverflowError(f"Record does not fit {self.width} bits")
        result = {}
        for field in self.fields:
            value = (record >> field.lsb) & ((1 << field.width) - 1)
            if field.signed and value & (1 << (field.width - 1)):
                value -= 1 << field.width
            result[field.name] = value
        return result

    def describe(self) -> dict:
        return {"name": self.name, "record_bits": self.width,
                "fields": [{"name": f.name, "lsb": f.lsb, "msb": f.msb,
                            "width": f.width, "signed": f.signed} for f in self.fields]}


def write_mem(path: Path, records, width: int) -> int:
    digits = (width + 3) // 4
    mask = (1 << width) - 1
    count = 0
    with Path(path).open("w", encoding="ascii", newline="\n") as stream:
        for record in records:
            value = int(record)
            if value < 0 or value > mask:
                raise OverflowError(f"Record {value} does not fit {width} bits")
            stream.write(f"{value:0{digits}X}\n")
            count += 1
    return count


def read_mem(path: Path, width: int) -> list[int]:
    mask = (1 << width) - 1
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="ascii").splitlines(), 1):
        token = line.strip()
        if not token or token.startswith("//"):
            continue
        value = int(token, 16)
        if value > mask:
            raise OverflowError(f"Line {number} does not fit {width} bits")
        records.append(value)
    return records
