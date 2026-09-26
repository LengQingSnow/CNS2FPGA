"""Check that the curated, offline GitHub package matches its source hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "repository_manifest.json"
FORBIDDEN_PARTS = {".Xil", "build", "qa_render"}
LOCAL_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ALLOWED_LOGS = {
    "code/7_Minimum FPGA Architecture/sim/transcript.log",
    "code/7_Minimum FPGA Architecture/sim/full_image_load.log",
    "code/8_RTL Bit-Exact Co-Simulation/sim/bit_exact_transcript.log",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema"] != "cns2fpga.public_repo.v1":
        raise RuntimeError("Unknown manifest schema")
    records = manifest["files"]
    expected = {item["path"] for item in records}
    if len(expected) != len(records):
        raise RuntimeError("Duplicate path in manifest")
    for item in records:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Unsafe manifest path: {relative}")
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"Missing or changed: {relative}")
    present = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and not LOCAL_PARTS.intersection(path.relative_to(ROOT).parts)
    }
    extra = present - expected - {"docs/repository_manifest.json"}
    missing = expected - present
    if extra or missing:
        raise RuntimeError(f"Unexpected/missing files: extra={sorted(extra)[:10]}, missing={sorted(missing)[:10]}")
    for relative in present:
        path = Path(relative)
        if path.name == "transcript" or FORBIDDEN_PARTS.intersection(path.parts) or path.suffix.lower() in {".feather", ".dcp", ".jou"} or (path.suffix.lower() == ".log" and relative not in ALLOWED_LOGS):
            raise RuntimeError(f"Generated/raw file in package: {relative}")
    print(f"validated {len(records)} files; {sum(item['bytes'] for item in records):,} bytes")


if __name__ == "__main__":
    main()
