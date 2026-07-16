# -*- coding: utf-8 -*-
"""Generate the Capiflow user guide PDF (simple, with screenshots).

Screenshots live in ./img/01.png .. 06.png
Run:  python3 generate_user_guide.py
Output: Capiflow_User_Guide.pdf (next to this script)
"""
import os

from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    Image, KeepTogether, PageBreak,
)

BRAND = colors.HexColor('#2163A0')
BRAND_LIGHT = colors.HexColor('#BDD7EE')
GREY = colors.HexColor('#595959')
LATE = colors.HexColor('#C00000')
RESID = colors.HexColor('#ED7D31')
PAID = colors.HexColor('#548235')
CONTRACT = colors.HexColor('#2E75B6')

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, 'img')
OUT = os.path.join(HERE, 'Capiflow_User_Guide.pdf')
CONTENT_W = 164 * mm

styles = getSampleStyleSheet()
styles.add(ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=34,
                          textColor=BRAND, spaceAfter=6, leading=38))
styles.add(ParagraphStyle('CoverSub', parent=styles['Normal'], fontSize=14,
                          textColor=GREY, alignment=TA_CENTER, spaceAfter=4))
styles.add(ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16,
                          textColor=BRAND, spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle('Body', parent=styles['Normal'], fontSize=11,
                          leading=16, spaceAfter=4, alignment=TA_LEFT))
styles.add(ParagraphStyle('CellH', parent=styles['Normal'], fontSize=10,
                          textColor=colors.white, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('Cell', parent=styles['Normal'], fontSize=10, leading=14))
styles.add(ParagraphStyle('CellB', parent=styles['Normal'], fontSize=10,
                          leading=14, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                          textColor=GREY, alignment=TA_CENTER))

story = []


def h1(text):
    story.append(Paragraph(text, styles['H1']))
    story.append(HRFlowable(width='100%', thickness=1, color=BRAND_LIGHT,
                            spaceBefore=2, spaceAfter=8))


def body(text):
    story.append(Paragraph(text, styles['Body']))


def picture(filename, width=CONTENT_W):
    """Embed a screenshot scaled to width, wrapped in a thin border."""
    path = os.path.join(IMG, filename)
    iw, ih = PILImage.open(path).size
    height = width * ih / iw
    img = Image(path, width=width, height=height)
    t = Table([[img]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#C7D2DC')),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))


def section(title, lines, images):
    flow = [Paragraph(title, styles['H1']),
            HRFlowable(width='100%', thickness=1, color=BRAND_LIGHT,
                       spaceBefore=2, spaceAfter=8)]
    for ln in lines:
        flow.append(Paragraph(ln, styles['Body']))
    story.append(KeepTogether(flow))
    story.append(Spacer(1, 4))
    for im in images:
        picture(im)


# ----------------------------------------------------------------- COVER
story.append(Spacer(1, 55 * mm))
story.append(Paragraph('Capiflow', styles['CoverTitle']))
story.append(Paragraph('Invoice Bundles &mdash; User Guide', styles['CoverSub']))
story.append(Spacer(1, 4))
story.append(Paragraph('A simple guide to grouping invoices, '
                       'reviewing their numbers, and exporting them to Excel.',
                       styles['CoverSub']))
story.append(Spacer(1, 16))
story.append(HRFlowable(width='40%', thickness=2, color=BRAND))
story.append(Spacer(1, 60 * mm))
story.append(Paragraph('Prepared by MountSol', styles['Footer']))
story.append(PageBreak())

# ----------------------------------------------------------------- 1. WHERE
section('1. Where to find Capiflow',
        ['Open the <b>Capiflow</b> app from the main apps screen.'],
        ['01.png'])
section('',
        ['Click <b>Bundles</b> to see all your bundles, then <b>New</b> to create one.'],
        ['02.png'])

# ----------------------------------------------------------------- 2. FORM
section('2. The Bundle screen',
        ['Give the bundle a name and add invoices in the <b>Invoices</b> tab '
         '(manually, or with <b>Load Invoices</b>).',
         'The totals and the <b>Financials</b> tab update automatically.'],
        ['03.png'])

# ----------------------------------------------------------------- 3. BUTTONS
h1('3. The buttons')
btn = [
    ['Button', 'What it does'],
    ['Load Invoices', 'Adds many matching invoices at once using filters (Draft only).'],
    ['Confirm', 'Locks the bundle and turns on the Export button (Draft only).'],
    ['Set to Draft', 'Unlocks a confirmed bundle so you can edit it again.'],
    ['Export to Excel', 'Downloads the bundle as an Excel file (after Confirm).'],
]
bdata = [[Paragraph(btn[0][0], styles['CellH']), Paragraph(btn[0][1], styles['CellH'])]]
for name, desc in btn[1:]:
    bdata.append([Paragraph(name, styles['CellB']), Paragraph(desc, styles['Cell'])])
bt = Table(bdata, colWidths=[40 * mm, 124 * mm], repeatRows=1)
bt.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), BRAND),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 7),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D9D9D9')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F6FB')]),
]))
story.append(bt)
story.append(Spacer(1, 14))

# ----------------------------------------------------------------- 4. LOAD
section('4. Load Invoices',
        ['Choose any filters (customer, payment term, date range) and click '
         '<b>Load</b> to pull all matching invoices in at once.'],
        ['04.png'])

# ----------------------------------------------------------------- 5. CONFIRM
section('5. Confirm &amp; Export',
        ['After <b>Confirm</b>, the bundle locks and the <b>Export to Excel</b> '
         'button appears. Use <b>Set to Draft</b> if you need to edit again.'],
        ['05.png'])

# ----------------------------------------------------------------- 6. EXCEL
section('6. The Excel file',
        ['Two sheets: <b>Bundle</b> (summary, invoices, financials) and '
         '<b>Schedule</b> (the installment timeline).',
         'The four top boxes are colour-coded &mdash; '
         '<font color="#C00000"><b>Late</b></font>, '
         '<font color="#ED7D31"><b>Residul</b></font>, '
         '<font color="#548235"><b>Paid</b></font>, '
         '<font color="#2E75B6"><b>Contract value</b></font>.'],
        ['06.png'])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GREY)
    if doc.page > 1:
        canvas.drawCentredString(A4[0] / 2, 12 * mm,
                                 'Capiflow User Guide  •  MountSol  •  Page %d' % doc.page)
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=22 * mm, rightMargin=22 * mm,
                        topMargin=20 * mm, bottomMargin=20 * mm,
                        title='Capiflow User Guide', author='MountSol')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('Wrote', OUT)
