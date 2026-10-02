"""Make a numbered thumbnail sheet for visual QA of all rendered PDF pages."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pages", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
paths = sorted([*args.pages.glob("page-*.jpg"), *args.pages.glob("page-*.png")])
if not paths:
    raise ValueError(f"No page images in {args.pages}")
columns, tw, th, label_h = 4, 340, 445, 40
rows = (len(paths) + columns - 1) // columns
sheet = Image.new("RGB", (columns * tw, rows * (th + label_h)), "#E5E9EB")
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)
for index, path in enumerate(paths):
    page = Image.open(path).convert("RGB")
    page.thumbnail((tw - 10, th - 10))
    x = (index % columns) * tw + (tw - page.width) // 2
    y = (index // columns) * (th + label_h) + 5
    sheet.paste(page, (x, y))
    draw.text(((index % columns) * tw + 12, y + th - 3), path.stem,
              fill="#263F5B", font=font)
args.output.parent.mkdir(parents=True, exist_ok=True)
sheet.save(args.output, quality=90)
print(f"CONTACT_SHEET {len(paths)} pages {args.output}")
