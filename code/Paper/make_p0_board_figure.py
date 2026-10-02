"""Draw the audited repeated-board evidence using bundled Pillow only."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
CODE = HERE.parent
REPORT = CODE / "15_Ethernet_Runtime_Deployment" / "reports" / "p0_board_audit_v1.json"
CAPTURES = CODE / "15_Ethernet_Runtime_Deployment" / "build" / "p0_ethernet_20260930_detached"
REFERENCE = CODE / "12_Visual-to-Steering Circuit" / "outputs" / "visual_left_board_v0" / "trial" / "expected_counts.csv"
OUT = HERE / "figures" / "figure8_p0_repeated_board_validation.png"


def counts(folder: Path) -> list[int]:
    words = [int(x, 16) for x in (folder / "summary_words.hex").read_text(encoding="ascii").splitlines() if x]
    assert len(words) == 2000
    return [words[i * 8 + 2] & 0xFFFF for i in range(250)]


evidence = json.loads(REPORT.read_text(encoding="utf-8"))
assert evidence["status"] == "PASS" and len(evidence["ethernet_sessions"]) == 2
sessions = evidence["ethernet_sessions"]
with REFERENCE.open(newline="", encoding="utf-8") as stream:
    cpu = [int(row["total"]) for row in csv.DictReader(stream)]
assert cpu == counts(CAPTURES / "session_1" / "visual_250")
assert cpu == counts(CAPTURES / "session_2" / "visual_250")

W, H = 2400, 1660
im = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(im)
fonts = Path("C:/Windows/Fonts")


def f(size: int, bold: bool = False):
    return ImageFont.truetype(str(fonts / ("arialbd.ttf" if bold else "arial.ttf")), size)


def put(x, y, value, size=26, color="#263F5B", bold=False, anchor=None):
    d.text((x, y), value, font=f(size, bold), fill=color, anchor=anchor)


navy, teal, rust, gray, grid = "#263F5B", "#008577", "#B3573F", "#586873", "#DFE7EB"
put(90, 50, "Repeated runtime image deployment on AXKU115", 53, navy, True)
put(90, 115, "Two independently programmed board sessions; one fixed bitstream per session", 27, gray)

# A. Show the complete CPU visual trace. Every board count is checked above;
# sparsely sampled markers keep the perfectly overlapping series legible.
d.rounded_rectangle((70, 210, 1480, 810), radius=25, outline=grid, width=3)
put(105, 245, "A  Visual: 250 steps, 560 ordered events per session", 35, navy, True)
x0, x1, y0, y1 = 180, 1410, 355, 720
for tick in (0, 50, 100):
    y = y1 - tick / 120 * (y1 - y0)
    d.line((x0, y, x1, y), fill=grid, width=2)
    put(x0 - 18, y, str(tick), 23, gray, anchor="rm")
trace = [(x0 + step / 249 * (x1-x0), y1 - value / 120 * (y1-y0))
         for step, value in enumerate(cpu)]
d.line(trace, fill=navy, width=4, joint="curve")
for step in range(0, 250, 6):
    x, y = trace[step]
    d.ellipse((x-7, y-7, x+7, y+7), fill="white", outline=teal, width=3)
for step in range(3, 250, 6):
    x, y = trace[step]
    d.line((x-7, y-7, x+7, y+7), fill=rust, width=3)
    d.line((x-7, y+7, x+7, y-7), fill=rust, width=3)
for step in (0, 50, 100, 150, 200, 249):
    put(x0 + step / 249 * (x1-x0), y1 + 13, str(step), 21, gray, anchor="mt")
put(680, 768, "Model step (1 ms)", 24, gray, anchor="mm")
put(180, 315, "CPU line  ·  session 1 circles  ·  session 2 crosses", 22, gray)

# B. These stopwatch values include the host uploader, not JTAG trial time.
d.rounded_rectangle((1510, 210, 2330, 810), radius=25, outline=grid, width=3)
put(1545, 245, "B  Host-inclusive upload", 34, navy, True)
put(1545, 296, "Seconds, from campaign Stopwatch", 23, gray)
bar_x, bar_scale = 1760, 230
upload = [("Visual S1", sessions[0]["visual_upload_seconds"], teal),
          ("Visual S2", sessions[1]["visual_upload_seconds"], teal),
          ("Courtship S1", sessions[0]["courtship_upload_seconds"], rust),
          ("Courtship S2", sessions[1]["courtship_upload_seconds"], rust)]
for row, (name, seconds, color) in enumerate(upload):
    y = 380 + row * 90
    put(1545, y + 17, name, 25, navy, anchor="lm")
    d.rounded_rectangle((bar_x, y, bar_x + seconds * bar_scale, y + 38), radius=7, fill=color)
    put(bar_x + seconds * bar_scale + 10, y + 20, f"{seconds:.3f} s", 22,
        color, True, anchor="lm")
put(1545, 747, "Visual 4,816; courtship 738,044 words", 21, gray)

# C. Each group has its own vertical scale; CPU bars and both FPGA markers
# overlap exactly. Display all three 4,308-step input conditions.
d.rounded_rectangle((70, 845, 2330, 1550), radius=25, outline=grid, width=3)
put(105, 880, "C  Courtship response-window population counts", 35, navy, True)
put(105, 930, "Both sessions match fixed CPU; 34,464 non-cycle fields per long trial match the dedicated board", 25, gray)
groups = ("vPN1", "pC1", "pIP10", "pMP2")
colors = ("#2A759E", rust, "#6B9B53", "#8A6BAB")
for index, (group, color) in enumerate(zip(groups, colors)):
    left = 125 + index * 550
    values = [sessions[0]["long_courtship"][str(ipi)]["fixed_cpu_response_window_groups"][group]
              for ipi in (15, 35, 65)]
    for session in sessions:
        assert values == [session["long_courtship"][str(ipi)]["board_response_window_groups"][group]
                          for ipi in (15, 35, 65)]
    put(left + 10, 1010, group, 30, color, True)
    bottom = 1435
    d.line((left + 50, bottom, left + 485, bottom), fill=gray, width=2)
    for j, (ipi, value) in enumerate(zip((15, 35, 65), values)):
        x = left + 110 + j * 125
        y = bottom - value / (max(values) * 1.18) * 330
        d.rounded_rectangle((x-26, y, x+26, bottom), radius=6, fill=color)
        d.ellipse((x-10, y-10, x+10, y+10), fill="white", outline=navy, width=3)
        d.line((x-6, y-6, x+6, y+6), fill=navy, width=2)
        d.line((x-6, y+6, x+6, y-6), fill=navy, width=2)
        put(x, y-17, str(value), 24, navy, True, anchor="mb")
        put(x, bottom+13, str(ipi), 23, gray, anchor="mt")
    put(left + 265, 1506, "IPI (ms)", 22, gray, anchor="mm")
put(105, 1595, "Bars: fixed CPU   ·   circles/crosses: FPGA sessions 1/2   ·   zero deadline misses and fault flags", 25, gray)
OUT.parent.mkdir(parents=True, exist_ok=True)
im.save(OUT, dpi=(220, 220), optimize=True)
print(OUT)
