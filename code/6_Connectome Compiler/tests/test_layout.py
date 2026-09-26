from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_compiler import Field, RecordLayout, read_mem, write_mem


def test_signed_roundtrip_and_hex_file(tmp_path):
    layout = RecordLayout("example", 16, [Field("index", 0, 5), Field("weight", 5, 8, True)])
    records = [layout.pack({"index": 17, "weight": -7}), layout.pack({"index": 3, "weight": 12})]
    assert layout.unpack(records[0]) == {"index": 17, "weight": -7}
    path = tmp_path / "example.mem"
    assert write_mem(path, records, 16) == 2
    assert path.read_text(encoding="ascii").splitlines() == [f"{records[0]:04X}", f"{records[1]:04X}"]
    assert read_mem(path, 16) == records


def test_layout_rejects_overlap_and_overflow():
    with pytest.raises(ValueError):
        RecordLayout("bad", 16, [Field("a", 0, 8), Field("b", 7, 4)])
    layout = RecordLayout("small", 8, [Field("signed", 0, 4, True)])
    with pytest.raises(OverflowError):
        layout.pack({"signed": 8})
    with pytest.raises(KeyError):
        layout.pack({"missing": 1})
