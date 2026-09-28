"""Generate the updated print-readable Figure 1 pipeline with Pillow."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


out = Path(__file__).resolve().parent / "figures" / "pipeline_paper.png"
im = Image.new("RGB", (2200, 1080), "white")
d = ImageDraw.Draw(im)
fonts = Path("C:/Windows/Fonts")
def f(size, bold=False):
    return ImageFont.truetype(str(fonts / ("arialbd.ttf" if bold else "arial.ttf")), size)

def centered(x0, x1, y, value, size, color, bold=False):
    face = f(size, bold)
    width = d.textbbox((0, 0), value, font=face)[2]
    d.text((x0 + (x1-x0-width)//2, y), value, font=face, fill=color)

def box(x0, y0, x1, y1, title, detail, color):
    d.rounded_rectangle((x0, y0, x1, y1), radius=26, outline=color, width=5, fill="white")
    centered(x0, x1, y0+62, title, 46, color, True)
    centered(x0, x1, y0+160, detail, 30, "#2E3C43")

def arrow(x0, y0, x1, y1, label=""):
    color = "#455A64"
    d.line((x0, y0, x1, y1), fill=color, width=6)
    d.polygon([(x1, y1), (x1-24, y1-15), (x1-24, y1+15)], fill=color)
    if label:
        centered(x0, x1, y0-60, label, 28, color)

box(80, 105, 680, 385, "MaleCNS v1.0", "Annotations and edge weights", "#00695C")
box(800, 105, 1400, 385, "Graph extraction", "Selectors, paths and sparse IR", "#00695C")
box(1520, 105, 2120, 385, "Memory compiler", "Fixed-point image and hash", "#00695C")
arrow(694, 245, 787, 245)
arrow(1414, 245, 1507, 245)
box(80, 665, 680, 945, "Float CPU", "Model reference", "#1E64A4")
box(800, 665, 1400, 945, "Fixed CPU", "Quantization reference", "#1E64A4")
box(1520, 665, 2120, 945, "FPGA engine", "UDP image; JTAG trial", "#B4232C")
arrow(694, 805, 787, 805, "quantize")
arrow(1414, 805, 1507, 805, "verify")
d.line((1100, 400, 370, 640), fill="#455A64", width=5)
d.line((1820, 400, 1100, 640), fill="#455A64", width=5)
d.line((1820, 400, 1820, 640), fill="#455A64", width=5)
d.polygon([(1820, 640), (1805, 610), (1835, 610)], fill="#455A64")
d.text((190, 1005), "Data and comparison flow; arrows do not represent anatomical connectivity.",
       fill="#52616B", font=f(28))
im.save(out, dpi=(220, 220), optimize=True)
print(out)
