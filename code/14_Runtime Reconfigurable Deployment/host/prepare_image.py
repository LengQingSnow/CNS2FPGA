"""Validate a safe_wf24 compiler image for the runtime AXKU115 firmware.

The output JSON is a small transport manifest; the original .mem files remain
the source of truth and are streamed by the Vivado Tcl loader on the board.
"""

import argparse
import hashlib
import json
from pathlib import Path

MAX_NEURONS = 6279
MAX_SYNAPSES = 350185
REGIONS = (
    ("neuron_param", 128, 4),
    ("synapse", 64, 2),
    ("offset", 32, 1),
    ("type_sign", 16, 1),
)
REQUIRED_FIELDS = {
    "neuron_param": {"threshold": (0, 34), "reset": (34, 34),
                     "decay": (68, 32), "refractory_steps": (100, 8)},
    "synapse": {"post_index": (0, 13), "weight": (13, 30)},
    "offset": {"edge_start": (0, 19), "edge_count": (19, 10)},
    "type_sign": {"is_input": (2, 1), "is_aPN1": (5, 1),
                  "is_vPN1": (6, 1), "is_pC1": (7, 1),
                  "is_pIP10": (8, 1), "is_pMP2": (9, 1)},
}
MASK32 = 0xFFFFFFFF


def read_records(path: Path, width: int, count: int):
    digest = hashlib.sha256()
    seen = 0
    with path.open("rb") as source:
        for raw in source:
            digest.update(raw)
            line = raw.strip()
            if not line or len(line) != width // 4:
                raise ValueError(f"{path}:{seen + 1}: expected {width // 4} hex digits")
            try:
                value = int(line, 16)
            except ValueError as exc:
                raise ValueError(f"{path}:{seen + 1}: invalid hexadecimal") from exc
            if value >= (1 << width):
                raise ValueError(f"{path}:{seen + 1}: width overflow")
            seen += 1
            yield value, digest
    if seen != count:
        raise ValueError(f"{path}: expected {count} records, found {seen}")


def validate(image_dir: Path) -> dict:
    manifest_path = image_dir / "compiler_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "cns2fpga.hardware_ir" or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported hardware IR schema")
    if manifest.get("fixed_format_name") != "safe_wf24":
        raise ValueError("Firmware supports safe_wf24 only")
    required_format = dict(state_bits=34, state_frac=24, weight_bits=30,
                           weight_frac=24, decay_bits=32, decay_frac=30,
                           accumulator_bits=35)
    for name, expected in required_format.items():
        if manifest.get("fixed_format", {}).get(name) != expected:
            raise ValueError(f"Incompatible fixed-point field: {name}")
    neurons = manifest["counts"]["neurons"]
    synapses = manifest["counts"]["synapses"]
    if not (1 <= neurons <= MAX_NEURONS and 0 <= synapses <= MAX_SYNAPSES):
        raise ValueError(f"Image exceeds physical capacity: {neurons} neurons, {synapses} synapses")
    files = {entry["file"]: entry for entry in manifest["files"]}
    checksum = 0
    hashes = {}
    words = {}
    next_edge = 0
    for region, (name, width, lanes) in enumerate(REGIONS):
        filename = f"{name}.mem"
        expected_records = synapses if name == "synapse" else neurons
        layout = manifest.get("layouts", {}).get(name, {})
        entry = files.get(filename, {})
        if layout.get("record_bits") != width or entry.get("records") != expected_records:
            raise ValueError(f"Manifest layout/count mismatch for {filename}")
        if entry.get("record_bits") != width:
            raise ValueError(f"Manifest record width mismatch for {filename}")
        fields = {field["name"]: (field["lsb"], field["width"])
                  for field in layout.get("fields", [])}
        for field_name, expected in REQUIRED_FIELDS[name].items():
            if fields.get(field_name) != expected:
                raise ValueError(f"Incompatible {name} field: {field_name}")
        seen = 0
        digest = None
        for value, digest in read_records(image_dir / filename, width, expected_records):
            if name == "synapse" and (value & 0x1FFF) >= neurons:
                raise ValueError(f"synapse.mem:{seen + 1}: post index outside image")
            if name == "offset":
                start = value & 0x7FFFF
                count = (value >> 19) & 0x3FF
                if value >> 29 or start != next_edge or start + count > synapses:
                    raise ValueError(f"offset.mem:{seen + 1}: invalid CSR range")
                next_edge += count
            for lane in range(lanes):
                word = (value >> (32 * lane)) & MASK32
                checksum = (((checksum << 1) | (checksum >> 31)) & MASK32) ^ word ^ region
            seen += 1
        hashes[filename] = digest.hexdigest() if digest else hashlib.sha256(b"").hexdigest()
        words[name] = seen * lanes
    if next_edge != synapses:
        raise ValueError(f"CSR offsets end at {next_edge}, not {synapses}")
    return {
        "schema": "cns2fpga.runtime_image",
        "schema_version": 1,
        "name": manifest["name"],
        "source_manifest": str(manifest_path.resolve()),
        "neurons": neurons,
        "synapses": synapses,
        "word_counts": words,
        "checksum_hex": f"{checksum:08X}",
        "sha256": hashes,
        "region_order": [name for name, _, _ in REGIONS],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("--output", type=Path, help="Write a transport manifest JSON")
    args = parser.parse_args()
    result = validate(args.image_dir.resolve())
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
