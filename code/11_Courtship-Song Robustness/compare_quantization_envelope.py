"""Place the 35-ms Step 11 replay beside Step 5's locked nine-IPI envelope."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "5_Fixed-Point Quantization Analysis" / "outputs" / "courtship_song_fixed_point_v6_final"
OUTPUT = ROOT / "outputs" / "courtship_song_robustness_v2"


def main():
    source = SOURCE / "format_summary.csv"
    hashes = json.loads((SOURCE / "artifact_sha256.json").read_text(encoding="utf-8"))
    if hashlib.sha256(source.read_bytes()).hexdigest() != hashes["format_summary.csv"]:
        raise RuntimeError("Step 5 locked format summary checksum mismatch")
    broad = pd.read_csv(source)[["format_name", "max_key_response_error_percent", "state_saturation_events", "acceptance_pass"]]
    local = pd.read_csv(OUTPUT / "quantization_sensitivity.csv")[["format_name", "pC1_error_pct", "exact_events"]]
    frame = broad.merge(local, on="format_name", validate="one_to_one")
    frame.to_csv(OUTPUT / "quantization_envelope.csv", index=False)
    x = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - .2, frame.pC1_error_pct, width=.4, label="35-ms pC1 response")
    ax.bar(x + .2, frame.max_key_response_error_percent, width=.4,
           label="Worst key-group error over nine IPIs")
    ax.axhline(5, color="#b00020", linestyle="--", linewidth=1, label="Step 5 tolerance: 5%")
    ax.set_xticks(x, frame.format_name, rotation=20, ha="right")
    ax.set_ylabel("Absolute response error vs float (%)")
    ax.set_title("Quantization sensitivity: one trial and the locked IPI envelope")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT / "quantization_envelope.png", dpi=190)
    plt.close(fig)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
