"""Render the canonical manuscript Markdown as a print-readable PDF.

This independent PDF route is used when the bundled DOCX renderer has no
LibreOffice executable.  The DOCX and PDF consume the same Markdown and PNGs.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "manuscript_full_v2.md"
OUTPUT = HERE / "qa_render" / "manuscript_full_v2.pdf"
OUTPUT.parent.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic")

body = ParagraphStyle("body", fontName="Arial", fontSize=9.4, leading=13.1,
                      spaceAfter=7, textColor=colors.HexColor("#17242D"))
title = ParagraphStyle("title", parent=body, fontName="Arial-Bold", fontSize=17.2,
                       leading=21.5, spaceAfter=14, textColor=colors.black)
h1 = ParagraphStyle("h1", parent=body, fontName="Arial-Bold", fontSize=13,
                    leading=17, spaceBefore=14, spaceAfter=6, keepWithNext=True)
h2 = ParagraphStyle("h2", parent=body, fontName="Arial-Bold", fontSize=10.8,
                    leading=14, spaceBefore=10, spaceAfter=4, keepWithNext=True)
caption = ParagraphStyle("caption", parent=body, fontSize=8.5, leading=11.7,
                         spaceBefore=3, spaceAfter=10)
table_head = ParagraphStyle("tablehead", parent=body, fontName="Arial-Bold",
                            fontSize=7.8, leading=10)
table_cell = ParagraphStyle("tablecell", parent=body, fontSize=7.6, leading=10)

def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^]]+)\]\((https?://[^)]+)\)",
                  r'<link href="\2" color="#1E64A4">\1</link>', text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text

def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#687780"))
    canvas.drawString(0.78*inch, 0.48*inch, "CNS2FPGA  |  28 September 2026")
    canvas.drawRightString(7.73*inch, 0.48*inch, str(doc.page))
    canvas.restoreState()

lines = SOURCE.read_text(encoding="utf-8").splitlines()
story = []
i = 0
last_table_label = ""
while i < len(lines):
    line = lines[i].strip()
    if not line:
        i += 1
        continue
    if line.startswith("# "):
        story.append(Paragraph(inline(line[2:]), title))
    elif line.startswith("## "):
        story.append(Paragraph(inline(line[3:]), h1))
    elif line.startswith("### "):
        story.append(Paragraph(inline(line[4:]), h2))
    elif line.startswith("!["):
        match = re.match(r"!\[[^]]*\]\(([^)]+)\)", line)
        if not match:
            raise ValueError(line)
        path = HERE / match.group(1)
        with PILImage.open(path) as source_image:
            aspect = source_image.height / source_image.width
        width = (6.1 if "figure2_" in path.name else 6.75) * inch
        figure = Image(str(path), width=width, height=width*aspect)
        caption_index = i + 1
        while caption_index < len(lines) and not lines[caption_index].strip():
            caption_index += 1
        if (caption_index < len(lines)
                and lines[caption_index].strip().startswith("*Figure ")):
            figure_caption = Paragraph(
                inline(lines[caption_index].strip().strip("*")), caption
            )
            story.append(KeepTogether([figure, figure_caption]))
            i = caption_index
        else:
            story.append(figure)
    elif line.startswith("*Figure "):
        story.append(Paragraph(inline(line.strip("*")), caption))
    elif line.startswith("Table ") and ". " in line:
        last_table_label = line
        story.append(Paragraph(inline(line), caption))
    elif line.startswith("| "):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            values = [part.strip() for part in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", part) for part in values):
                style = table_head if not rows else table_cell
                rows.append([Paragraph(inline(value), style) for value in values])
            i += 1
        count = len(rows[0])
        if count == 4:
            widths = [1.55*inch, 1.44*inch, 1.44*inch, 2.30*inch]
        elif count == 5:
            widths = [1.35*inch, 1.25*inch, 1.25*inch, 1.25*inch, 1.62*inch]
        elif count == 3:
            widths = [2.15*inch, 2.35*inch, 2.23*inch]
        elif count == 2:
            widths = [1.85*inch, 4.88*inch]
        else:
            widths = [6.73*inch/count] * count
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5ECEF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#81949D")),
            ("LINEBELOW", (0, -1), (-1, -1), .35, colors.HexColor("#B9C7CC")),
        ]))
        if last_table_label.startswith(("Table 3.", "Table 5.")):
            story.append(KeepTogether([story.pop(), table, Spacer(1, 8)]))
        else:
            story.extend((table, Spacer(1, 8)))
        last_table_label = ""
        continue
    else:
        paragraph = Paragraph(inline(line), body)
        if re.match(r"^\d+\.\s", line):
            story.append(KeepTogether([paragraph]))
        else:
            story.append(paragraph)
    i += 1

document = SimpleDocTemplate(
    str(OUTPUT), pagesize=letter, rightMargin=.78*inch, leftMargin=.78*inch,
    topMargin=.69*inch, bottomMargin=.72*inch,
    title="CNS2FPGA Runtime Image Deployment", author="CNS2FPGA project"
)
document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
print(OUTPUT)
