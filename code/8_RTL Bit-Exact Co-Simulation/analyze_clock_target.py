"""Check whether a proposed clock target covers the observed timestep budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_relative(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def analyze(config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    metadata_path = load_relative(config_path, config["source_run_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    configured_cycles = int(config["observed_maximum_cycles_per_timestep"])
    measured_cycles = int(metadata["maximum_cycles_per_timestep"])
    if configured_cycles != measured_cycles:
        raise ValueError(
            f"cycle budget is stale: config={configured_cycles}, measured={measured_cycles}"
        )

    target_mhz = float(config["target_clock_mhz"])
    deadline_us = float(config["biological_timestep_us"])
    elapsed_us = measured_cycles / target_mhz
    slack_us = deadline_us - elapsed_us
    result = {
        "target_clock_mhz": target_mhz,
        "clock_period_ns": 1000.0 / target_mhz,
        "maximum_cycles_per_timestep": measured_cycles,
        "observed_worst_case_time_us": elapsed_us,
        "deadline_us": deadline_us,
        "deadline_slack_us": slack_us,
        "deadline_utilization_percent": elapsed_us / deadline_us * 100.0,
        "minimum_clock_mhz": measured_cycles / deadline_us,
        "observed_budget_pass": slack_us >= 0.0,
        "timing_closure_claimed": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "clock_target_250mhz_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "clock_target_250mhz_v1" / "assessment.json",
    )
    args = parser.parse_args()
    result = analyze(args.config.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
