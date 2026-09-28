"""Draw the verified single-bitstream, two-image board result with Pillow."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent / "15_Ethernet_Runtime_Deployment" / "reports" / "deployment_evidence_v1.json"
data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
assert data["fpga_reprogramming_between_images"] is False
assert data["courtship_trial"]["ordered_event_mismatches"] == 0

W, H = 2200, 1510
im = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(im)
font_dir = Path("C:/Windows/Fonts")
def font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(font_dir / name), size)

navy, teal, rust, gray = "#345995", "#008577", "#B04B3C", "#53616B"
d.text((120, 65), "A   Runtime graph replacement over UDP", fill="#172734", font=font(48, True))

def center_text(x0: int, x1: int, y: int, value: str, size: int, color: str, bold=False):
    face = font(size, bold)
    width = d.textbbox((0, 0), value, font=face)[2]
    d.text((x0 + (x1-x0-width)//2, y), value, fill=color, font=face)

def box(x0: int, x1: int, title: str, line1: str, line2: str, color: str):
    d.rounded_rectangle((x0, 165, x1, 505), radius=32, outline=color, width=6, fill="white")
    center_text(x0, x1, 223, title, 37, color, True)
    center_text(x0, x1, 325, line1, 29, "#25313A")
    center_text(x0, x1, 398, line2, 29, "#25313A")

box(100, 700, "One AXKU115 bitstream", "200 MHz; SHA-256 pinned", "No FPGA reprogramming", navy)
box(805, 1405, "Visual image", "226 neurons; 1,730 edges", "UDP COMMIT + STATUS", teal)
box(1510, 2110, "Courtship image", "6,279 neurons; 350,185 edges", "UDP COMMIT + STATUS", rust)
for x0, x1 in ((715, 790), (1420, 1495)):
    d.line((x0, 335, x1, 335), fill=gray, width=7)
    d.polygon([(x1, 335), (x1-24, 320), (x1-24, 350)], fill=gray)

d.line((100, 605, 2110, 605), fill="#D7DEE3", width=3)
d.text((120, 655), "B   Courtship smoke8: fixed CPU and FPGA match at every step", fill="#172734", font=font(47, True))

trial = data["courtship_trial"]
rows = trial["step_counts"]
left, right, top, bottom = 220, 2050, 805, 1200
scale = (bottom - top) / 700
for tick in (0, 200, 400, 600):
    y = bottom - int(tick * scale)
    d.line((left, y, right, y), fill="#D8E0E5", width=2)
    d.text((135, y-18), str(tick), fill=gray, font=font(28))
for row in rows:
    step, cpu, fpga = row["step"], row["cpu_fixed"], row["fpga"]
    assert cpu == fpga
    x = left + (step + .5) * (right - left) / len(rows)
    y = bottom - int(cpu * scale)
    d.rectangle((x-54, y, x+54, bottom), fill="#BED5DB", outline="#57717C", width=3)
    d.polygon([(x, y-17), (x+17, y), (x, y+17), (x-17, y)], fill="#C44234")
    center_text(int(x-50), int(x+50), 1222, str(step), 31, "#25313A")
d.line((left, bottom, right, bottom), fill="#5D6972", width=3)
d.text((890, 1294), "Model timestep (1 ms)", fill="#25313A", font=font(30))
d.text((245, 748), "Spike events", fill="#25313A", font=font(27))
d.rectangle((1210, 731, 1265, 766), fill="#BED5DB", outline="#57717C", width=2)
d.text((1280, 732), "Fixed-point CPU", fill="#25313A", font=font(27))
d.polygon([(1620, 748), (1640, 728), (1660, 748), (1640, 768)], fill="#C44234")
d.text((1675, 732), "FPGA after UDP load", fill="#25313A", font=font(27))
d.line((100, 1360, 2110, 1360), fill="#D7DEE3", width=3)
d.text((145, 1390), "2,475 ordered events; 0 mismatches    |    Max step: 199,699 / 200,000 cycles    |    Upload link: 100 Mbps",
       fill="#25313A", font=font(28))

out = HERE / "figures" / "figure7_ethernet_reconfiguration.png"
im.save(out, dpi=(220, 220), optimize=True)
print(out)
