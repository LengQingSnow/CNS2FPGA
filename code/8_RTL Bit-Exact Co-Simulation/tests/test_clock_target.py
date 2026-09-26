import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_clock_target", ROOT / "analyze_clock_target.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_250mhz_target_covers_observed_peak_with_margin():
    result = MODULE.analyze(ROOT / "configs" / "clock_target_250mhz_v1.json")
    assert result["clock_period_ns"] == 4.0
    assert result["observed_budget_pass"] is True
    assert result["observed_worst_case_time_us"] == 670.672
    assert result["deadline_slack_us"] == 329.328
    assert result["timing_closure_claimed"] is False


def test_xdc_matches_clock_target():
    config = json.loads(
        (ROOT / "configs" / "clock_target_250mhz_v1.json").read_text(encoding="utf-8")
    )
    xdc = (ROOT / "constraints" / "cns2fpga_250mhz.xdc").read_text(encoding="utf-8")
    assert f'-period {config["clock_period_ns"]:.3f}' in xdc
    assert f'set_clock_uncertainty {config["clock_uncertainty_ns"]:.3f}' in xdc
