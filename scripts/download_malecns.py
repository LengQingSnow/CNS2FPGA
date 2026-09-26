"""Download the pinned MaleCNS v1.0 inputs into an untracked support directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "support" / "data_sources.json"


def sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def matches(path: Path, item: dict) -> bool:
    size, digest = sha256(path)
    return size == item["bytes"] and digest == item["sha256"]


def download(item: dict) -> None:
    dest = ROOT / "support" / item["name"]
    part = dest.with_name("." + dest.name + ".part")
    if dest.exists():
        if not matches(dest, item):
            raise RuntimeError(f"Existing file has wrong size/hash; refusing overwrite: {dest}")
        print(f"verified: {dest.name}")
        return
    if part.exists():
        raise RuntimeError(f"Partial file exists; inspect/remove it before retrying: {part}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(item["url"], timeout=120) as response, part.open("xb") as output:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                output.write(block)
        if not matches(part, item):
            raise RuntimeError(f"Downloaded size/hash mismatch: {part}")
        os.replace(part, dest)
        print(f"downloaded and verified: {dest.name}")
    except Exception:
        # Keep a partial file for inspection; never publish it as a verified input.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="check local files without downloading")
    parser.add_argument("--file", action="append", help="download/check only this manifest filename; repeatable")
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = [item for item in data["files"] if not args.file or item["name"] in args.file]
    if args.file and len(selected) != len(set(args.file)):
        parser.error("--file contains an unknown or duplicated manifest filename")
    for item in selected:
        if args.verify_only:
            dest = ROOT / "support" / item["name"]
            if not dest.is_file() or not matches(dest, item):
                raise RuntimeError(f"missing or mismatched: {dest}")
            print(f"verified: {dest.name}")
        else:
            download(item)


if __name__ == "__main__":
    main()
