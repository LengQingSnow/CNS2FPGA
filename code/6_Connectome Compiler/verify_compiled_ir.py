"""Read-only integrity and shape verification for a compiled CNS2FPGA image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_compiler import read_mem


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(image_dir: Path) -> dict:
    image_dir = image_dir.resolve()
    manifest = json.loads((image_dir / "compiler_manifest.json").read_text(encoding="utf-8"))
    hashes = json.loads((image_dir / "artifact_sha256.json").read_text(encoding="utf-8"))
    mismatches = [name for name, expected in hashes.items()
                  if not (image_dir / name).exists() or sha256(image_dir / name) != expected]
    shape_errors = []
    for entry in manifest["files"]:
        path = image_dir / entry["file"]
        actual = len(read_mem(path, int(entry["record_bits"])))
        if actual != int(entry["records"]):
            shape_errors.append(f"{entry['file']}: {actual} != {entry['records']}")
    magic = read_mem(image_dir / "global_config.mem", 64)[0]
    if magic != int.from_bytes(b"CNS2FPGA", "big"):
        shape_errors.append("global_config.mem magic mismatch")
    checks = pd.read_csv(image_dir / "verification.csv")
    failed_checks = checks.loc[~checks.status.eq("PASS"), "check"].tolist()
    protocol_hash = sha256(image_dir / "protocol_lock.json")
    protocol_ok = protocol_hash == manifest["protocol_lock_sha256"]
    passed = not mismatches and not shape_errors and not failed_checks and protocol_ok
    return {"verdict": "PASS" if passed else "FAIL", "image_dir": str(image_dir),
            "artifact_hash_mismatches": mismatches, "shape_errors": shape_errors,
            "failed_compile_checks": failed_checks, "protocol_lock_match": protocol_ok,
            "files_hashed": len(hashes), "memory_files_checked": len(manifest["files"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", nargs="?", type=Path,
                        default=ROOT / "outputs" / "courtship_song_hw_ir_v1")
    result = verify(parser.parse_args().image_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
