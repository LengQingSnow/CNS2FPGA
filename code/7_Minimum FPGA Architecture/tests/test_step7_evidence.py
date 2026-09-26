from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modelsim_logs_have_clean_passes():
    smoke = (ROOT / "sim" / "transcript.log").read_text(encoding="utf-8", errors="replace")
    full = (ROOT / "sim" / "full_image_load.log").read_text(encoding="utf-8", errors="replace")
    assert "PASS two-neuron one-cycle propagation" in smoke
    assert "PASS full image load neurons=6279 synapses=350185 inputs=93 pC1=112" in full
    assert "Errors: 0, Warnings: 0" in smoke
    assert "Errors: 0, Warnings: 0" in full


def test_architecture_explicitly_has_no_ddr_and_keeps_two_phases():
    rtl = (ROOT / "rtl" / "cns2fpga_core.sv").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "architecture_v1.md").read_text(encoding="utf-8")
    assert "ST_UPDATE" in rtl and "ST_EDGE" in rtl
    assert "不使用 DDR" in doc
    assert "t+1" in doc
