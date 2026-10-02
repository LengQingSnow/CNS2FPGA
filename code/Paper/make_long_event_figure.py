"""Plot the audited full-event AXKU115 courtship runs (Pillow, no interpolation)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
STEP15 = HERE.parent / "15_Ethernet_Runtime_Deployment"
AUDIT = STEP15 / "reports" / "long_event_board_audit_v1.json"
RAW = STEP15 / "reports" / "long_event_board_20260930"
OUT = HERE / "figures" / "figure9_long_ordered_events.png"


def read_counts(path: Path) -> list[int]:
    with path.open(newline="", encoding="ascii") as stream:
        return [int(row["total"]) for row in csv.DictReader(stream)]


def read_events(path: Path):
    with path.open(newline="", encoding="ascii") as stream:
        for row in csv.DictReader(stream):
            yield int(row["timestep"]), int(row["neuron_index"])


evidence = json.loads(AUDIT.read_text(encoding="utf-8"))
assert evidence["status"] == "PASS"
W, H = 2500, 1750
image = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(image)
fonts = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(fonts / ("arialbd.ttf" if bold else "arial.ttf")), size)


def label(x, y, value, size=25, color="#263F5B", bold=False, anchor=None):
    draw.text((x, y), value, font=font(size, bold), fill=color, anchor=anchor)


navy, teal, rust, gray, grid = "#263F5B", "#008577", "#B3573F", "#586873", "#D9E4EA"
label(82, 48, "Complete ordered events in long courtship trials", 52, navy, True)
label(82, 112, "One 200-MHz AXKU115 image, three 4,308-step trials, exact fixed-CPU event identity", 27, gray)

for panel, ipi in enumerate((15, 35, 65)):
    top = 194 + panel * 510
    bottom = top + 460
    draw.rounded_rectangle((65, top, 2435, bottom), radius=24, outline=grid, width=3)
    run = evidence["new_bit_conditions"][str(ipi)]
    count = run["ordered_events_compared"]
    label(95, top + 25, f"IPI {ipi} ms", 36, navy, True)
    label(420, top + 28, f"{count:,} ordered events  |  0 mismatches  |  0 overflow", 29, teal, True)

    # A binned raster is a display reduction only; all events were checked
    # unbinned in the machine-readable audit and ordered event files.
    rx0, ry0, rx1, ry1 = 150, top + 112, 1315, top + 363
    draw.rectangle((rx0, ry0, rx1, ry1), fill="#F8FAFB", outline=grid, width=2)
    bins_x, bins_y = 580, 126
    occupancy = bytearray(bins_x * bins_y)
    seen = 0
    for step, neuron in read_events(RAW / f"ipi_{ipi}" / "cpu" / "expected_events.csv"):
        bx = min(bins_x - 1, step * bins_x // 4308)
        by = min(bins_y - 1, neuron * bins_y // 6279)
        occupancy[(bins_y - 1 - by) * bins_x + bx] = 1
        seen += 1
    assert seen == count
    raster = Image.new("RGB", (bins_x, bins_y), "#F8FAFB")
    raster_pixels = raster.load()
    for y in range(bins_y):
        for x in range(bins_x):
            if occupancy[y * bins_x + x]:
                raster_pixels[x, y] = (0, 133, 119)
    image.paste(raster.resize((rx1 - rx0 - 1, ry1 - ry0 - 1), Image.Resampling.NEAREST), (rx0 + 1, ry0 + 1))
    label(rx0, ry0 - 13, "A  Neuron-by-time event raster (display bins)", 23, gray, anchor="lb")
    label(rx0 - 10, ry0, "6279", 19, gray, anchor="rm")
    label(rx0 - 10, ry1, "0", 19, gray, anchor="rm")
    for tick in (0, 1000, 2000, 3000, 4308):
        x = rx0 + tick / 4308 * (rx1 - rx0)
        label(x, ry1 + 9, str(tick), 18, gray, anchor="mt")
    label((rx0 + rx1) / 2, ry1 + 41, "Model timestep (1 ms)", 22, gray, anchor="mm")

    cx0, cy0, cx1, cy1 = 1515, top + 112, 2310, top + 363
    label(cx0, cy0 - 13, "B  Cumulative event count", 23, gray, anchor="lb")
    cpu = read_counts(RAW / f"ipi_{ipi}" / "cpu" / "expected_counts.csv")
    assert len(cpu) == 4308 and sum(cpu) == count
    board_words = [int(value, 16) for value in (RAW / f"ipi_{ipi}" / "board" / "summary_words.hex").read_text(encoding="ascii").splitlines() if value]
    assert [board_words[step * 8 + 2] & 0xFFFF for step in range(4308)] == cpu
    cumulative = [0]
    for value in cpu:
        cumulative.append(cumulative[-1] + value)
    max_y = 110000
    for tick in (0, 50000, 100000):
        y = cy1 - tick / max_y * (cy1 - cy0)
        draw.line((cx0, y, cx1, y), fill=grid, width=2)
        label(cx0 - 10, y, f"{tick // 1000}k", 19, gray, anchor="rm")
    threshold_y = cy1 - 65536 / max_y * (cy1 - cy0)
    for x in range(cx0, cx1, 20):
        draw.line((x, threshold_y, min(x + 11, cx1), threshold_y), fill=rust, width=2)
    points = [(cx0 + step / 4308 * (cx1 - cx0), cy1 - value / max_y * (cy1 - cy0))
              for step, value in enumerate(cumulative)]
    draw.line(points, fill=navy, width=4)
    for tick in (0, 1000, 2000, 3000, 4308):
        x = cx0 + tick / 4308 * (cx1 - cx0)
        label(x, cy1 + 9, str(tick), 18, gray, anchor="mt")
    label(cx0 + 13, threshold_y - 9, "Old 65,536-event limit", 18, rust, anchor="lb")
    label((cx0 + cx1) / 2, cy1 + 41, "Model timestep (1 ms)", 22, gray, anchor="mm")
    label(95, bottom - 32, f"CPU vs FPGA: exact ordered (timestep, neuron ID) equality; max core latency {run['max_latency_cycles']:,}/200,000 cycles", 23, gray)

label(82, H - 50, "Raster pixels are display bins; the audit compares all 214,982 raw events without binning.", 25, gray)
OUT.parent.mkdir(parents=True, exist_ok=True)
image.save(OUT, dpi=(220, 220), optimize=True)
print(OUT)
