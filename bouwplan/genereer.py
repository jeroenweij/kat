"""Genereert het bouwplan (PDF) en de lijsten (XLSX) uit model.py en berekening.py.

Gebruik:  python genereer.py   (vereist reportlab, openpyxl, pypdf)
          --lijsten: ook de modeltabbladen in het Excel-bestand bijwerken (Inkoop blijft staan)
          --xlsx:    het hele Excel-bestand opnieuw schrijven (overschrijft eigen invoer)
"""
import datetime
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

import berekening
import model as m

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(HERE, "Kattenchalet_bouwplan.pdf")
OUT_XLSX = os.path.join(HERE, "Kattenchalet_zaag_en_inkooplijst.xlsx")
OUT_STORE = os.path.join(HERE, "Kattenchalet_zaagplannen_bouwmarkt.pdf")
REV = "Rev K"
DATE = "6-11-2026"

FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("D", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DB", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("D", normal="D", bold="DB", italic="D", boldItalic="DB")

C = lambda h: colors.HexColor(h)
INK = C("#1f2a30")
ACC = C("#8a4b14")
FILL = {
    m.MAT["R44"]: C("#ecd9b0"), m.MAT["B69"]: C("#e3c992"), m.MAT["I69"]: C("#a9b78a"), m.MAT["P69"]: C("#8fa073"),
    m.MAT["LP9"]: C("#c79a6e"), m.MAT["BP12"]: C("#a87748"), m.MAT["OSB"]: C("#cfae78"), m.MAT["PIR"]: C("#f4ef9c"),
    m.MAT["LAT"]: C("#d8c7a6"), m.MAT["DG"]: C("#c08a4e"), m.MAT["DM"]: C("#c08a4e"), m.MAT["DK"]: C("#3a3f43"),
}
LEGEND = [("R44", "regel 44x44"), ("B69", "balk 44x69"), ("I69", "geïmpr. balk"), ("LP9", "Lightply 9"), ("BP12", "betonplex 12"),
          ("OSB", "OSB-3 11"), ("PIR", "PIR 70"), ("LAT", "spouwlat"), ("DG", "gevel grenen beits"), ("DK", "hoek/boei/luifel antraciet")]


def nl(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


# --- Tekenprimitieven -------------------------------------------------------
class Sheet:
    """Tekenblad. Elk blad wordt eerst als A3-vorm (420 x 297 mm) getekend en daarna als een of meer
    staande A4-bladen uitgegeven: elk A4-blad toont uitsneden (tegels) van de vorm op ware schaal."""
    FR = 7            # kader, mm uit de papierrand
    BAND = 34         # bovenkant titelstrook

    def __init__(self, c):
        self.c = c
        self.n = 0
        self.cur = None
        self.W, self.H = [v / mm for v in landscape(A3)]

    def new(self, title, scale, pages=None, legend=False, split=False):
        """pages: [(ondertitel, [(x0, y0, x1, y1), ...]), ...] in mm op de A3-vorm, alle bladen uit één vorm.
        split=True: elk A4-blad krijgt een eigen vorm via page(); de uitsnede mag dan vrij schuiven."""
        self.flush()
        self.n += 1
        self.cur = dict(title=title, scale=scale, pages=list(pages or []), legend=legend, form=None)
        if not split:
            self._begin(f"blad{self.n}")

    def _begin(self, name):
        self.c.beginForm(name, 0, 0, self.W * mm, self.H * mm)
        self.cur["form"] = name

    def page(self, sub, tiles):
        """Begin een eigen A4-blad (eigen vorm) binnen dit blad."""
        if self.cur["form"]:
            self.c.endForm()
        name = f"blad{self.n}_{len(self.cur['pages'])}"
        self._begin(name)
        self.cur["pages"].append((sub, tiles, name))

    def pages(self, pages):
        self.cur["pages"] = pages

    def flush(self):
        if not self.cur:
            return
        c, cur = self.c, self.cur
        c.endForm()
        pw, ph = [v / mm for v in A4]
        aw, ah = pw - 2 * self.FR, ph - self.FR - self.BAND
        pages = cur["pages"]
        for k, (sub, tiles, *frm) in enumerate(pages):
            form = frm[0] if frm else cur["form"]
            num = f"T{self.n}" + ("abcdefgh"[k] if len(pages) > 1 else "")
            c.setPageSize(A4)
            gap = 0.8
            hs = [t[3] - t[1] for t in tiles]
            tot = sum(hs) + gap * (len(tiles) - 1)
            ws = [t[2] - t[0] for t in tiles]
            if max(ws) > aw + 0.01 or tot > ah + 0.01:
                sys.exit(f"Blad {num}: tegels {max(ws):.1f} x {tot:.1f} passen niet op A4 ({aw} x {ah})")
            top = ph - self.FR - (ah - tot) / 2
            for (x0, y0, x1, y1), w, h in zip(tiles, ws, hs):
                px, py = (pw - w) / 2, top - h
                c.saveState()
                path = c.beginPath()
                path.rect(px * mm, py * mm, w * mm, h * mm)
                c.clipPath(path, stroke=0, fill=0)
                c.translate((px - x0) * mm, (py - y0) * mm)
                c.doForm(form)
                c.restoreState()
                top = py - gap
            c.setStrokeColor(INK)
            c.setLineWidth(0.6)
            c.rect(self.FR * mm, self.FR * mm, aw * mm, (ph - 2 * self.FR) * mm)
            c.line(self.FR * mm, self.BAND * mm, (pw - self.FR) * mm, self.BAND * mm)
            tx = 82
            c.line(tx * mm, self.FR * mm, tx * mm, self.BAND * mm)
            if cur["legend"]:
                legend(c, self.FR + 3, 26)
            c.setFillColor(INK)
            t, fs = f"Blad {num}: {sub}", 9.5
            while fs > 6 and pdfmetrics.stringWidth(t, "DB", fs) > (pw - self.FR - tx - 4) * mm:
                fs -= 0.25
            c.setFont("DB", fs)
            c.drawString((tx + 2.5) * mm, 27 * mm, t)
            c.setFont("D", 6.5)
            c.drawString((tx + 2.5) * mm, 21.5 * mm, f"Kattenchalet  |  schaal {cur['scale']}  |  {REV}, {DATE}  |  maten in mm")
            c.setFont("D", 6)
            c.drawString((tx + 2.5) * mm, 16 * mm, "Sparingen pas zagen nadat de ramen binnen zijn en ingemeten.")
            c.drawString((tx + 2.5) * mm, 12.5 * mm, "Niet van tekening meten.")
            c.showPage()
        self.cur = None


class View:
    """Rekent modelcoördinaten om naar papier: horizontale as u, verticale as v (mm)."""

    def __init__(self, c, ox, oy, scale, flip=False):
        self.c, self.ox, self.oy, self.s, self.flip = c, ox, oy, scale, flip

    def p(self, u, v):
        if self.flip:
            u = -u
        return (self.ox + u / self.s) * mm, (self.oy + v / self.s) * mm


def rect(view, u0, u1, v0, v1, fill, stroke=INK, lw=0.25):
    c = view.c
    x0, y0 = view.p(u0, v0)
    x1, y1 = view.p(u1, v1)
    c.setLineWidth(lw)
    c.setStrokeColor(stroke)
    if fill is not None:
        c.setFillColor(fill)
    c.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), fill=1 if fill is not None else 0, stroke=1)


def poly(view, pts, fill, lw=0.25, stroke=INK):
    c = view.c
    path = c.beginPath()
    x, y = view.p(*pts[0])
    path.moveTo(x, y)
    for u, v in pts[1:]:
        x, y = view.p(u, v)
        path.lineTo(x, y)
    path.close()
    c.setLineWidth(lw)
    c.setStrokeColor(stroke)
    c.setFillColor(fill)
    c.drawPath(path, fill=1, stroke=1)


def dim(view, u0, v0, u1, v1, off, text=None, size=6.5):
    """Maatlijn tussen twee punten. off in mm papier, loodrecht op de lijn."""
    c = view.c
    x0, y0 = view.p(u0, v0)
    x1, y1 = view.p(u1, v1)
    horiz = abs(y1 - y0) < abs(x1 - x0)
    o = off * mm
    c.setStrokeColor(ACC)
    c.setFillColor(ACC)
    c.setLineWidth(0.25)
    length = abs(u1 - u0) if horiz else abs(v1 - v0)
    label = text if text is not None else f"{round(length)}"
    c.setFont("D", size)
    tw = pdfmetrics.stringWidth(label, "D", size)
    if horiz:
        y = y0 + o
        c.line(x0, y0, x0, y)
        c.line(x1, y1, x1, y)
        c.line(x0, y, x1, y)
        for x in (x0, x1):
            c.line(x - 1.2, y - 1.2, x + 1.2, y + 1.2)
        if abs(x1 - x0) > tw + 3:
            c.drawCentredString((x0 + x1) / 2, y + 1.1, label)
        else:
            c.drawString(max(x0, x1) + 2, y + 1.1, label)
    else:
        x = x0 + o
        c.line(x0, y0, x, y0)
        c.line(x1, y1, x, y1)
        c.line(x, y0, x, y1)
        for y in (y0, y1):
            c.line(x - 1.2, y - 1.2, x + 1.2, y + 1.2)
        c.saveState()
        c.translate(x - 1.3, (y0 + y1) / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, label)
        c.restoreState()


def label(c, x, y, text, size=7, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("DB" if bold else "D", size)
    c.drawString(x * mm, y * mm, text)


def leader(view, u, v, tx, ty, text, size=5.6):
    c = view.c
    x, y = view.p(u, v)
    c.setStrokeColor(INK)
    c.setLineWidth(0.25)
    c.line(x, y, tx * mm, ty * mm)
    c.setFillColor(INK)
    c.setFont("D", size)
    for i, ln in enumerate(text.split("\n")):
        c.drawString((tx + 0.7) * mm, (ty - 0.9 - i * size * 0.42) * mm, ln)


def view_title(c, x, y, text):
    label(c, x, y, text, 9, True)


# --- Projecties uit het model -----------------------------------------------
def geometry(p, axis):
    """Vorm in vlak. axis 'yz' geeft polygon voor schuine delen; anders box."""
    x0, x1, y0, y1, z0, z1 = p.box
    kind = p.extra.get("slope")
    if axis == "yz":
        if kind == "raft":
            return [(y0, z0), (y1, z0), (y1, m.roof_z(y1)), (y0, m.roof_z(y0))]
        if kind == "canopy":
            return [(y0, z0), (y1, z0 + m.CANOPY_DROP), (y1, z1), (y0, z1 - m.CANOPY_DROP)]
        if kind == "deck":
            return [(y0, m.roof_z(y0)), (y1, m.roof_z(y1)), (y1, m.roof_z(y1) + m.OSB_T), (y0, m.roof_z(y0) + m.OSB_T)]
        if p.extra.get("stringer"):
            k = p.extra["stringer"]
            return m.strip_outline() if k == 2 else m.stringer_outline(free=(k == 3))
        if p.extra.get("trim"):
            return [(y0, z0), (y1, z0), (y1, m.roof_z(y1) + m.OSB_T), (y0, m.roof_z(y0) + m.OSB_T)]
    return None


def draw_project(view, select, key, proj, axis=None, cutfn=None):
    """Tekent onderdelen op volgorde van diepte; doorsneden dik omlijnd."""
    items = [p for p in m.parts if select(p)]
    items.sort(key=key)
    for p in items:
        cut = cutfn(p) if cutfn else False
        fill = FILL[p.mat]
        lw = 0.55 if cut else 0.2
        g = geometry(p, axis) if axis else None
        if g:
            if view.flip:
                poly(view, g, fill, lw)
            else:
                poly(view, g, fill, lw)
            continue
        u0, u1, v0, v1 = proj(p)
        rect(view, u0, u1, v0, v1, fill, lw=lw)


def foot(view, axis, xs):
    """Terras en Hettich-stelvoeten onder de poten (schematisch)."""
    u0 = min(a for a, _ in xs) - 250
    u1 = max(b for _, b in xs) + 250
    rect(view, u0, u1, -50, 0, C("#b9b4aa"))
    for a, b in xs:
        mid = (a + b) / 2
        rect(view, mid - m.FOOT_D / 2, mid + m.FOOT_D / 2, 0, m.FOOT_T, C("#8d979c"))
        rect(view, mid - 5, mid + 5, m.FOOT_T, m.Z_POST, C("#8d979c"))
        rect(view, mid - 8, mid + 8, m.Z_POST - 12, m.Z_POST - 4, C("#5a6268"))


def window_front(view, w, sight):
    rect(view, w["x0"], w["x1"], w["z0"], w["z1"] + m.WIN_JOINT, C("#6a7780"))
    rect(view, w["x0"], w["x1"], w["z0"], w["z1"], colors.white)
    rect(view, w["x0"] + sight, w["x1"] - sight, w["z0"] + sight, w["z1"] - sight, C("#bfdcec"))


def front_view(view):
    draw_project(view, lambda p: True, lambda p: -p.box[3],
                 lambda p: (p.box[0], p.box[1], p.box[4], p.box[5]))
    window_front(view, m.WIN_U, m.SIGHT_U)
    window_front(view, m.WIN_L, m.SIGHT_L)
    foot(view, "x", m.LEG_X)


def back_view(view):
    def pr(p):
        return p.box[0], p.box[1], p.box[4], p.box[5]
    draw_project(view, lambda p: True, lambda p: p.box[2], pr)
    foot(view, "x", [(a, b) for a, b in m.LEG_X])
    x0, y0 = view.p(m.VENT["x"], m.VENT["z"])
    view.c.setFillColor(colors.white)
    view.c.setStrokeColor(INK)
    view.c.circle(x0, y0, m.VENT["d"] / 2 / view.s * mm, fill=1, stroke=1)


def side_view(view, side):
    if side == "L":
        sel, key = (lambda p: True), (lambda p: -p.box[1] * -1)
        key = lambda p: -p.box[0]
    else:
        sel, key = (lambda p: True), (lambda p: p.box[1])
    draw_project(view, sel, key, lambda p: (p.box[2], p.box[3], p.box[4], p.box[5]), axis="yz")
    foot(view, "y", m.LEG_Y)


def section_x(view, xc, keep_side=-1):
    """Doorsnede op x = xc, kijkrichting naar lagere x (voorkant links)."""
    sel = lambda p: p.box[0] < xc
    key = lambda p: p.box[1] if p.box[1] < xc else xc + 1
    cut = lambda p: p.box[0] < xc <= p.box[1]
    draw_project(view, sel, key, lambda p: (p.box[2], p.box[3], p.box[4], p.box[5]), axis="yz", cutfn=cut)
    # ramen
    for w, sight in ((m.WIN_U, m.SIGHT_U), (m.WIN_L, m.SIGHT_L)):
        if w["x0"] < xc < w["x1"]:
            rect(view, w["y0"], w["y1"], w["z0"], w["z1"], colors.white, lw=0.5)
            rect(view, -19, 0, w["z0"] + 50, w["z1"] - 50, colors.white, lw=0.3)
            rect(view, w["y0"] - 8, w["y0"] + 16, w["z0"] + sight, w["z1"] - sight, C("#bfdcec"), lw=0.3)
    foot(view, "y", m.LEG_Y)


def section_y(view, yc):
    sel = lambda p: p.box[3] > yc
    key = lambda p: -p.box[2] if p.box[2] > yc else -yc + 1
    cut = lambda p: p.box[2] <= yc < p.box[3]
    draw_project(view, sel, key, lambda p: (p.box[0], p.box[1], p.box[4], p.box[5]), cutfn=cut)
    for w, sight in ((m.WIN_U, m.SIGHT_U), (m.WIN_L, m.SIGHT_L)):
        if w["y0"] < yc < w["y1"]:
            window_front(view, w, sight)
    foot(view, "x", m.LEG_X)


def plan(view, zc, only=None):
    sel = lambda p: p.box[4] < zc and (only is None or only(p))
    key = lambda p: p.box[5] if p.box[5] < zc else zc + 1
    cut = lambda p: p.box[4] < zc <= p.box[5]
    draw_project(view, sel, key, lambda p: (p.box[0], p.box[1], p.box[2], p.box[3]), cutfn=cut)
    for w in (m.WIN_U, m.WIN_L):
        if w["z0"] < zc < w["z1"]:
            rect(view, w["x0"], w["x1"], w["y0"], w["y1"], colors.white, lw=0.5)
            rect(view, w["x0"] + 50, w["x1"] - 50, -19, 0, colors.white, lw=0.3)
            rect(view, w["x0"] + 118, w["x1"] - 118, w["y0"] - 8, w["y0"] + 16, C("#bfdcec"), lw=0.3)


def depth_dims(v, x):
    """Diepte van een frame: rand voor, balk, rand achter, en totaal."""
    ys = [m.F0, m.F1, m.YR, m.YB1]
    for a, b in zip(ys, ys[1:]):
        dim(v, x, a, x, b, 4, size=5.3)
    dim(v, x, m.F0, x, m.YB1, 10, size=6)


def legend(c, x, y):
    label(c, x, y + 4, "Legenda", 7, True)
    for i, (k, t) in enumerate(LEGEND):
        col, row = i // 5, i % 5
        px = x + col * 32
        py = y - row * 4.3
        c.setFillColor(FILL[m.MAT[k]])
        c.setStrokeColor(INK)
        c.setLineWidth(0.25)
        c.rect(px * mm, py * mm, 5 * mm, 3 * mm, fill=1, stroke=1)
        label(c, px + 6, py + 0.5, t, 6.3)


# --- 3D-weergave ------------------------------------------------------------
def iso_order(boxes):
    """Topologische sortering: wat achter/onder ligt eerst (kijkpunt: voor, rechts, boven)."""
    n = len(boxes)
    after = [[] for _ in range(n)]
    indeg = [0] * n
    for i in range(n):
        a = boxes[i][0]
        for j in range(i + 1, n):
            b = boxes[j][0]
            ab = a[2] >= b[3] - .01 or a[1] <= b[0] + .01 or a[5] <= b[4] + .01   # a achter b
            ba = b[2] >= a[3] - .01 or b[1] <= a[0] + .01 or b[5] <= a[4] + .01
            if ab and not ba:
                after[i].append(j)
                indeg[j] += 1
            elif ba and not ab:
                after[j].append(i)
                indeg[i] += 1
    keyf = lambda k: boxes[k][0][3] - boxes[k][0][1] + -boxes[k][0][5]
    ready = sorted([i for i in range(n) if indeg[i] == 0], key=keyf, reverse=True)
    order = []
    done = [False] * n
    while len(order) < n:
        if not ready:
            rest = [i for i in range(n) if not done[i]]
            rest.sort(key=keyf, reverse=True)
            ready = [rest[0]]
        i = ready.pop(0)
        if done[i]:
            continue
        done[i] = True
        order.append(i)
        for j in after[i]:
            indeg[j] -= 1
            if indeg[j] <= 0 and not done[j]:
                ready.append(j)
        ready.sort(key=keyf, reverse=True)
    return order


def shade(col, f):
    return colors.Color(min(col.red * f, 1), min(col.green * f, 1), min(col.blue * f, 1))


def iso_draw(c, boxes, ox, oy, s):
    """boxes: [(box, kleur)]. ox, oy in mm papier; s = mm model per mm papier."""
    ca, sa = 0.866, 0.5

    def Q(x, y, z):
        # kijkpunt voor-rechts-boven: +x naar rechtsonder, +y naar rechtsboven
        return (ox + (x + y) * ca / s) * mm, (oy + (z + (y - x) * sa) / s) * mm

    for i in iso_order(boxes):
        b, col = boxes[i]
        x0, x1, y0, y1, z0, z1 = b
        faces = [
            ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], 0.9),   # voorkant
            ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], 0.72),  # rechterkant
            ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], 1.05),  # bovenkant
        ]
        for pts, f in faces:
            path = c.beginPath()
            u, v = Q(*pts[0])
            path.moveTo(u, v)
            for pt in pts[1:]:
                u, v = Q(*pt)
                path.lineTo(u, v)
            path.close()
            c.setFillColor(shade(col, f))
            c.setStrokeColor(colors.Color(0.1, 0.13, 0.15))
            c.setLineWidth(0.12)
            c.drawPath(path, fill=1, stroke=1)


def visible_outside(p):
    """Delen die van buitenaf te zien zijn; de rest veroorzaakt alleen tekenvolgorde-fouten."""
    if p.group[0] == "Q" or p.group[0] == "A":
        return True
    if p.group[0] == "M":
        return not p.name.startswith(("Spoor", "Zijspoor", "Rijklos", "Onderplaat"))
    if p.mat == m.MAT["LP9"]:
        return p.name in ("Plaat verandazijde", "Onderplaat tussenvloer") or p.group[0] in "CF"
    return False


def iso_boxes(mirror=False, dz=None, skip=()):
    out = []
    t = (lambda b: (m.W - b[1], m.W - b[0], m.D - b[3], m.D - b[2], b[4], b[5])) if mirror else (lambda b: b)
    for p in m.parts:
        if p.group[0] in skip:
            continue
        if not dz and not visible_outside(p):
            continue
        if dz and p.name.startswith("Onderplaat overstek"):
            continue
        b = t(p.box)
        if p.extra.get("slope") == "raft":
            b = b[:5] + (b[4] + 42,)
        if p.extra.get("slope") == "deck":
            b = b[:4] + (m.Z_RAFT + 42, m.Z_RAFT + 60)
        if p.extra.get("slope") == "canopy":
            b = b[:4] + (b[4] + m.CANOPY_DROP / 2, b[5] - m.CANOPY_DROP / 2)
        if p.extra.get("trim"):
            b = b[:5] + (m.Z_RAFT + 60,)
        if p.extra.get("stringer"):
            continue
        d = dz(p) if dz else 0
        out.append(((b[0], b[1], b[2], b[3], b[4] + d, b[5] + d), FILL[p.mat]))
    for w, sight in ((m.WIN_U, m.SIGHT_U), (m.WIN_L, m.SIGHT_L)):
        if dz:
            continue
        if mirror:
            continue
        b = (w["x0"], w["x1"], w["y0"], w["y1"], w["z0"], w["z1"])
        out.append(((b[0], b[1], b[2] + 0.1, b[2] + 40, b[4], b[4] + sight), colors.white))
        out.append(((b[0], b[1], b[2], b[2] + 40, b[5] - sight, b[5]), colors.white))
        out.append(((b[0], b[0] + sight, b[2], b[2] + 40, b[4] + sight, b[5] - sight), colors.white))
        out.append(((b[1] - sight, b[1], b[2], b[2] + 40, b[4] + sight, b[5] - sight), colors.white))
        out.append(((b[0] + sight, b[1] - sight, b[2] + 15, b[2] + 25, b[4] + sight, b[5] - sight), C("#bfdcec")))
    return out


# --- Nesten ------------------------------------------------------------------
class Sheetnest:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.free = [(0, 0, w, h)]
        self.items = []

    def place(self, l, b, name, kerf, rotate):
        best = None
        for fi, (fx, fy, fw, fh) in enumerate(self.free):
            for (pw, ph, rot) in ((l, b, False), (b, l, True)) if rotate else ((l, b, False),):
                if pw <= fw + .001 and ph <= fh + .001:
                    score = min(fw - pw, fh - ph)
                    if best is None or score < best[0]:
                        best = (score, fi, pw, ph, rot)
        if best is None:
            return False
        _, fi, pw, ph, rot = best
        fx, fy, fw, fh = self.free.pop(fi)
        self.items.append((fx, fy, pw, ph, name))
        rw, rh = fw - pw - kerf, fh - ph - kerf
        if fw * rh > rw * fh:
            parts = [(fx + pw + kerf, fy, rw, ph), (fx, fy + ph + kerf, fw, rh)]
        else:
            parts = [(fx + pw + kerf, fy, rw, fh), (fx, fy + ph + kerf, pw, rh)]
        self.free += [r for r in parts if r[2] > 10 and r[3] > 10]
        return True


def nest_once(items, w, h, kerf, rotate):
    sheets = []
    for l, b, name in items:
        for s_ in sheets:
            if s_.place(l, b, name, kerf, rotate):
                break
        else:
            s_ = Sheetnest(w, h)
            if not s_.place(l, b, name, kerf, rotate):
                raise ValueError(f"{name} {l}x{b} past niet op {w}x{h}")
            sheets.append(s_)
    return sheets


def nest(items, w, h, kerf=4, rotate=True, tries=4000):
    """Probeert veel volgordes (vast zaad, dus reproduceerbaar) en houdt de zuinigste indeling."""
    rng = random.Random(1)
    base = sorted(items, key=lambda i: -(i[0] * i[1]))
    best = nest_once(base, w, h, kerf, rotate)
    target = math.ceil(sum(i[0] * i[1] for i in items) / (w * h))
    for _ in range(tries):
        if len(best) <= target:
            break
        trial = sorted(items, key=lambda i: -(max(i[0], i[1]) * rng.uniform(0.6, 1.4)))
        got = nest_once(trial, w, h, kerf, rotate)
        if len(got) < len(best):
            best = got
    return best


# handelslengtes per lat met prijs uit de Inkoop-tab
STOCK = {"R44": {3600: 5.29, 2400: 3.55}, "B69": {3600: 6.49, 2400: 4.30}, "I69": {3600: 6.75},
         "P69": {1800: 6.69}, "LAT": {2500: 5.49}}


def pack_exact(lens, stocks, kerf=4, margin=10, max_nodes=200_000):
    """Exacte indeling van stuklengtes over de gegeven latten, of None. Per lat een combinatie van
    aantallen per lengte; het totale zaagverlies mag het verschil tussen latten en stukken niet overschrijden."""
    types = sorted(Counter(lens).items(), reverse=True)
    need = [l + kerf for l, _ in types]
    left = [n for _, n in types]
    stocks = sorted(stocks, reverse=True)
    caps = [s - margin + kerf for s in stocks]          # som(l) + kerf*(n-1) + margin <= lat
    budget = sum(caps) - sum(q * n for q, n in zip(need, left))
    if budget < 0:
        return None
    plan, nodes = [], [0]

    def patterns(cap, k, upper):
        """Aantallen vanaf lengte k die in cap passen; bij gelijke latten lexicografisch <= de vorige (symmetrie)."""
        if k == len(need):
            yield [], cap
            return
        top = min(left[k], cap // need[k])
        if upper is not None:
            top = min(top, upper[k])
        for n in range(top, -1, -1):
            sub = upper if (upper is not None and n == upper[k]) else None
            for rest, r in patterns(cap - n * need[k], k + 1, sub):
                yield [n] + rest, r

    def go(b, waste):
        if b == len(caps):
            return not any(left)
        nodes[0] += 1
        if nodes[0] > max_nodes:
            raise TimeoutError
        upper = plan[-1] if b and stocks[b] == stocks[b - 1] else None
        for pat, rest in patterns(caps[b], 0, upper):
            if waste + rest > budget:
                continue
            left[:] = [a - n for a, n in zip(left, pat)]
            plan.append(pat)
            if go(b + 1, waste + rest):
                return True
            plan.pop()
            left[:] = [a + n for a, n in zip(left, pat)]
        return False

    try:
        if not go(0, 0):
            return None
    except TimeoutError:
        return None
    return [(s, [l for (l, _), n in zip(types, pat) for _ in range(n)]) for s, pat in zip(stocks, plan)]


def bars(items, stocks, kerf=4, margin=10):
    """Goedkoopste mix van lange en korte latten met een exacte indeling; anders de snelle indeling hieronder.
    margin: tolerantie op de 'ca.'-lengte van Hornbach."""
    if not items:
        return []
    lo, hi = min(stocks), max(stocks)
    need = sum(l + kerf for l, _ in items)
    mixes = sorted(((nl, ns) for nl in range(len(items) + 1) for ns in (range(len(items) + 1) if lo != hi else [0])
                    if nl * (hi - margin + kerf) + ns * (lo - margin + kerf) >= need and (nl or ns)),
                   key=lambda m_: (m_[0] * stocks[hi] + m_[1] * stocks[lo], m_[0] + m_[1]))
    for nl, ns in mixes[:200]:
        got = pack_exact([l for l, _ in items], [hi] * nl + [lo] * ns, kerf, margin)
        if got:
            names = defaultdict(list)
            for l, name in sorted(items, key=lambda i: -i[0]):
                names[l].append(name)
            return [{"cuts": [(l, names[l].pop(0)) for l in cuts], "stock": s,
                     "left": s - sum(cuts) - kerf * (len(cuts) - 1)} for s, cuts in got]
    return bars_greedy(items, stocks, kerf, margin)


def bars_greedy(items, stocks, kerf=4, margin=10, n_fixed=None):
    """Eerst n_long lange latten, daarna korte; houdt de goedkoopste indeling, of n_fixed lange. margin: tolerantie Hornbach."""
    if not items:
        return []
    items = sorted(items, key=lambda i: -i[0])
    lens = sorted(stocks, reverse=True)
    best = None
    for n_long in ([n_fixed] if n_fixed is not None else range(len(items) + 1)):
        out = []
        for l, name in items:
            for bar in out:
                if bar["left"] >= l + kerf + margin:
                    bar["cuts"].append((l, name))
                    bar["left"] -= l + kerf
                    break
            else:
                stock = lens[0] if len(out) < n_long else lens[-1]
                if l + margin > stock:
                    out = None
                    break
                out.append({"cuts": [(l, name)], "left": stock - l, "stock": stock})
        if out:
            cost = sum(stocks[b_["stock"]] for b_ in out)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, out)
    return best[1]


# --- Vaste zaagplannen voor de bouwmarkt (guillotine: elke snede gaat door het hele stuk) ---------
BP_W, BP_H, BP_KERF, BP_MAX_HORNBACH = 2500, 1250, 4, 10
PLATE_INFO = {"BP12": ("Betonplex 12 mm", "12628592", 2500, 1250),
              "LP9": ("LIGHTPLY multiplex ongegrond 9 mm", "12575686", 2440, 1220),
              "OSB": ("OSB-3 11 mm", "10222931", 2440, 1220)}


def P(name, width=None):
    """Stuk dat de bouwmarkt precies op maat zaagt."""
    return ("piece", name, width)


def R(keep=False):
    """Rest; keep: grote restplaat om te bewaren."""
    return ("rest", keep)


def H(*names):
    """Strook die mee naar huis gaat; daar worden deze stukken eruit gezaagd. Een naam mag (naam, breedte) zijn."""
    return ("home", names)


def S(axis, parts, rev=False, trim=False, stack=0):
    """Deel het stuk: axis 'y' = sneden over de lengte (strook boven elkaar), 'x' = dwars. rev: vanaf boven/rechts.
    parts: [(maat, inhoud)], de laatste maat mag None zijn (wat overblijft). trim: ook het laatste stuk op maat
    nazagen, omdat zaagsnede en plaatmaat van de bouwmarkt afwijken; er valt dan alleen een smal strookje af.
    stack: de eerste zoveel delen zijn gelijke stroken die de bouwmarkt op elkaar legt en in één keer verder zaagt."""
    return ("split", axis, parts, rev, trim, stack)


class CutPlan:
    def __init__(self, w, h, pool, kerf=BP_KERF):
        self.s = Sheetnest(w, h)
        self.s.cuts, self.s.home, self.s.rests, self.s.store = [], [], [], []
        self.pool, self.k = pool, kerf
        self.attach = None

    def fail(self, t):
        sys.exit(f"Zaagplan {self.s.w} x {self.s.h} klopt niet meer: {t}. Pas het plan in genereer.py (plate_plans) aan.")

    def take(self, name, width=None):
        cands = [p for p in self.pool.get(name, []) if width is None or p[1] == width]
        if not cands:
            self.fail(f"geen {name}{'' if width is None else f' van {width} breed'} (meer) in het model")
        self.pool[name].remove(cands[0])
        return cands[0]

    def run(self, spec):
        self.node((0, 0, self.s.w, self.s.h), spec)
        return self.s

    def node(self, r, spec):
        x, y, w, h = r
        kind = spec[0]
        if kind == "piece":
            l, b, nm = self.take(spec[1], spec[2])
            if sorted((round(w), round(h))) != sorted((l, b)):
                self.fail(f"{nm} is {l} x {b}, het vak is {round(w)} x {round(h)}")
            self.s.items.append((x, y, w, h, nm))
            self.s.store.append((x, y, w, h, "piece"))
        elif kind == "rest":
            self.s.rests.append((x, y, w, h, spec[1]))
            self.s.store.append((x, y, w, h, "keep" if spec[1] else "rest"))
        elif kind == "home":
            self.s.store.append((x, y, w, h, "home"))
            along = w >= h
            L_, B_ = (w, h) if along else (h, w)
            pos, got = 0, []
            for n_ in spec[1]:
                l, b, nm = self.take(*n_) if isinstance(n_, tuple) else self.take(n_)
                if b > B_ + .5 or pos + l > L_ + .5:
                    self.fail(f"{nm} {l} x {b} past niet in de strook {round(w)} x {round(h)}")
                self.s.items.append((x + pos, y, l, b, nm) if along else (x, y + pos, b, l, nm))
                pos += l + self.k
                got.append((l, b, nm))
            if L_ - pos > 0:
                self.s.rests.append((x + pos, y, L_ - pos, h, False) if along else (x, y + pos, w, L_ - pos, False))
            wb = max(b for _, b, _ in got)
            if B_ - wb > 1:
                self.s.rests.append((x, y + wb, pos - self.k, h - wb, False) if along else (x + wb, y, w - wb, pos - self.k, False))
            names = ", ".join(dict.fromkeys(nm.split(":")[1].lower() for _, _, nm in got))
            rip = f"op de tafelzaag op {wb} breed, dan " if B_ - wb > 1 else ""
            narrow = [f"de {nm.split(':')[1].lower()} van {b} nog {wb - b} smaller" for _, b, nm in got if b < wb]
            tail_n = f", {', '.join(narrow)}" if narrow else ""
            tail = f"rest {round(L_ - pos)} lang" if L_ - pos > 0 else "geen rest: zaag de stukken op maat, het laatste is wat overblijft"
            self.s.home.append(f"Strook {round(L_)} x {round(B_)}: {rip}afkorten op " + " + ".join(str(l) for l, _, _ in got) + f" ({names}){tail_n}; {tail}.")
        else:
            _, axis, parts, rev, trim, stack = spec
            if trim and parts[-1][0] is None:
                self.fail("nazagen kan alleen als ook het laatste stuk een maat heeft")
            total = h if axis == "y" else w
            sizes = [p[0] for p in parts]
            fixed = sum(s_ for s_ in sizes if s_ is not None) + self.k * (len(parts) - 1)
            if sizes[-1] is None:
                sizes[-1] = total - fixed
            if any(s_ < 1 for s_ in sizes) or sum(sizes) + self.k * (len(parts) - 1) > total + .5:
                self.fail(f"de delen {sizes} passen niet in {round(w)} x {round(h)}")
            rects, pos = [], 0
            cur = r
            for i, s_ in enumerate(sizes):
                a = (total - pos - s_) if rev else pos
                rects.append((x, y + a, w, s_) if axis == "y" else (x + a, y, s_, h))
                if i < len(sizes) - 1 or trim:
                    c_ = (pos + s_ + self.k / 2) if not rev else (total - pos - s_ - self.k / 2)
                    c_ = min(max(c_, 1), total - 1)     # nazagen: op de rand tekenen
                    seg = (x, y + c_, x + w, y + c_) if axis == "y" else (x + c_, y, x + c_, y + h)
                    cw, ch = cur[2], cur[3]
                    long_ = (axis == "y") == (cw >= ch)
                    rest_ = (cw, max(0, ch - s_ - self.k)) if axis == "y" else (max(0, cw - s_ - self.k), ch)
                    part_ = (cw, s_) if axis == "y" else (s_, ch)
                    cut = dict(src=(round(cw), round(ch)), dir="in de lengte" if long_ else "dwars", stack=1, more=[],
                               at=round(s_), out=[tuple(round(v) for v in part_), tuple(round(v) for v in rest_)])
                    if self.attach is None:
                        self.s.cuts.append((seg, cut))
                    else:
                        if self.attach >= len(self.s.cuts) or {k_: v_ for k_, v_ in self.s.cuts[self.attach][1].items() if k_ not in ("more", "stack")} != \
                                {k_: v_ for k_, v_ in cut.items() if k_ not in ("more", "stack")}:
                            self.fail("gestapelde stroken zijn niet gelijk ingedeeld")
                        self.s.cuts[self.attach][1]["more"].append(seg)
                        self.attach += 1
                    cur = (0, 0) + rest_
                pos += s_ + self.k
            first = None
            for i, (rr, (_, content)) in enumerate(zip(rects, parts)):
                if stack and i == 0:
                    first = len(self.s.cuts)
                elif stack and i < stack:
                    self.attach = first
                self.node(rr, content)
                if stack and i == 0:
                    for _, ct in self.s.cuts[first:]:
                        ct["stack"] = stack
                elif stack and i < stack:
                    if self.attach != len(self.s.cuts):
                        self.fail("gestapelde stroken zijn niet gelijk ingedeeld")
                    self.attach = None


def out_text(d, n=1):
    return "smal strookje (afval)" if min(d) < 10 else (f"{n} x " if n > 1 else "") + f"{d[0]} x {d[1]}"


def src_text(c_):
    t = ("ca. " if min(c_["out"][1]) < 10 else "") + f"{c_['src'][0]} x {c_['src'][1]}"
    return f"{c_['stack']} stroken {t} op elkaar" if c_["stack"] > 1 else t


def cut_text(c_):
    a, b = c_["out"]
    n = c_["stack"]
    return f"Uit {src_text(c_)}, {c_['dir']} op {c_['at']}: {out_text(a, n)} en {out_text(b, n)}."


def plate_plans(by, short):
    """Per plaat het zaagplan. Betonplex: indeling van de gebruiker (Betonplex_zaagplan_trap.dxf); Lightply:
    plaat 1 lange strook 1140, plaat 2 twee gelijke stroken wandhoogte, samen afgekort (keuze gebruiker); OSB: dwars eerst."""
    K = BP_KERF
    pools = {}
    for key in PLATE_INFO:
        pools[key] = defaultdict(list)
        for r in by[m.MAT[key]]:
            pools[key][short(r)].append((max(r["dims"][:2]), min(r["dims"][:2]), short(r)))
    dims = lambda key, nm: pools[key][nm][0]
    res = {}

    # betonplex
    pb = pools["BP12"]
    fl = dims("BP12", "A:Vloerplaat beneden")
    deep = sorted({b for l, b, _ in pb["N:Trede"] if b > m.TREAD}, reverse=True)
    rows = [("M:Onderplaat overstek voor",), ("M:Onderplaat overstek achter",),
            ("M:Onderplaat overstek links", "M:Onderplaat overstek rechts"), ("N:Trapboom", "N:Trapboom"),
            tuple(("N:Trede", m.TREAD) for _ in range(sum(b == m.TREAD for _, b, _ in pb["N:Trede"])))]
    size = lambda n_: dims("BP12", n_ if isinstance(n_, str) else n_[0]) if isinstance(n_, str) else next(p for p in pb[n_[0]] if p[1] == n_[1])
    hs = [max(size(n_)[1] for n_ in row) for row in rows]
    runs = [sum(size(n_)[0] for n_ in row) + K * (len(row) - 1) for row in rows] + [dims("BP12", "N:Versterkingsstrook trapboom")[0]]
    lr = max(runs)
    spec = S("y", [(fl[1], S("x", [(fl[0], P("A:Vloerplaat beneden")), (fl[0], P("G:Vloerplaat bovenkamer")),
                                   (None, H(*[("N:Trede", b) for b in deep]))])),
                   (None, S("x", [(lr, S("y", [(h_, H(*row)) for h_, row in zip(hs, rows)] + [(None, H("N:Versterkingsstrook trapboom"))], rev=True)),
                                  (None, R(True))]))])
    res["BP12"] = [CutPlan(BP_W, BP_H, pb).run(spec)]

    # Lightply multiplex
    pl = pools["LP9"]
    g_ = dims("LP9", "G:Onderplaat tussenvloer")
    wall = dims("LP9", "C:Binnenplaat")[1]
    s1 = S("y", [(g_[0], S("x", [(g_[1], P("G:Onderplaat tussenvloer")), (g_[1], P("L:Plafondplaat")),
                                 (wall, P("C:Binnenplaat")), (wall, P("I:Binnenplaat"))], trim=True)),
                 (None, H("G:Dagkant trapgat links", "G:Dagkant trapgat voor"))])
    st = lambda names: S("x", [(dims("LP9", n_)[0], P(n_)) for n_ in names] + [(None, R())])
    s2 = S("y", [(wall, st(["E:Plaat verandazijde", "D:Binnenplaat", "E:Plaat trapzijde"])),
                 (wall, st(["F:Binnenplaat", "K:Binnenplaat", "J:Binnenplaat"])),
                 (None, H("E:Versterking kattenluik"))], stack=2)   # twee gelijke stroken, samen afkorten
    res["LP9"] = [CutPlan(2440, 1220, pl).run(s1), CutPlan(2440, 1220, pl).run(s2)]

    # OSB
    po = pools["OSB"]
    dk, ov = dims("OSB", "M:Dakplaat"), dims("OSB", "A:Onderplaat vloer")
    so = S("x", [(dk[0], S("y", [(dk[1], P("M:Dakplaat")), (None, R())])),
                 (ov[1], S("y", [(ov[0], P("A:Onderplaat vloer")), (None, R())])), (None, R(True))])
    res["OSB"] = [CutPlan(2440, 1220, po).run(so)]

    for key, pool in pools.items():
        left = {k: v for k, v in pool.items() if v}
        if left:
            sys.exit(f"Zaagplan {key}: onderdelen zonder plek: {left}")
    n = len(res["BP12"][0].cuts)
    if n > BP_MAX_HORNBACH:
        sys.exit(f"Betonplex: {n} zaagsneden bij de bouwmarkt, maximaal {BP_MAX_HORNBACH}")
    return res


def collect():
    rows = m.cutlist()
    by = defaultdict(list)
    for r in rows:
        for _ in range(r["qty"]):
            by[r["mat"]].append(r)
    res = {}
    short = lambda r: r["group"][0] + ":" + r["name"]
    for key, stocks in STOCK.items():
        res[key] = bars([(r["dims"][0], short(r)) for r in by[m.MAT[key]]], stocks)
    res.update(plate_plans(by, short))
    res["PIR"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in by[m.MAT["PIR"]]], 1200, 600, kerf=2)
    res["DG"] = nest([(r["dims"][0], max(r["dims"][1], 145) if r["dims"][1] >= 100 else r["dims"][1], short(r)) for r in by[m.MAT["DG"]]], 3000, 145, kerf=4, rotate=False)
    # hoek-, boei- en kaderdelen uit dezelfde planken: beitsen gebeurt na het zagen
    res["DK"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in rows if r["mat"] in (m.MAT["DK"], m.MAT["DM"]) for _ in range(r["qty"])], 3000, 145, kerf=4, rotate=False)
    return rows, res


ROWS, NEST = collect()
R = berekening.results()
STAIR_DEG = round(math.degrees(math.atan(m.RISE / m.TREAD)))
TREADS = f"{m.TREAD_D[0]}, {len(m.TREAD_D) - 2} x {m.TREAD} en {m.TREAD_D[-1]}"
SLOPE = round(m.ROOF_L / (m.RAFT_F - m.RAFT_B))
SEC_B = m.mid(m.PART_X1, m.MID_X[3])      # snede B-B: vak naast de scheidingswand
SEC_D = m.mid(m.CAT_Y0, m.CAT_Y1)         # snede D-D: midden doorgang
HOLE = f"{m.HOLE_X1-m.HOLE_X0} x {m.HOLE_Y1-m.HOLE_Y0}"
BAY_MAX = max(b - (a + m.S) for xs in (m.FLOOR_X, m.MID_X) for a, b in zip(xs, xs[1:]))
LEG_DX = [b[0] - a[0] for a, b in zip(m.LEG_X, m.LEG_X[1:])]
LEG_DY = m.LEG_Y[1][0] - m.LEG_Y[0][0]
LP_USE = sum(w * h for s in NEST["LP9"] for _, _, w, h, _ in s.items) / (len(NEST["LP9"]) * 2440 * 1220)


# --- Tekenbladen -------------------------------------------------------------
def walls_page(sh, title, walls):
    """Wanden in twee groepen, elke groep een eigen A4-blad; elke wand horizontaal in het midden van het blad."""
    from reportlab.lib.utils import simpleSplit
    per_col = -(-len(walls) // 2)
    sh.new(title, "1:10", split=True)
    c = sh.c
    row_h = 80
    for i, (grp, axis, u0, u1, name, flip) in enumerate(walls):
        k, r = divmod(i, per_col)
        col = walls[k * per_col:(k + 1) * per_col]
        if r == 0:
            ls = [w[0].split()[0] for w in col]
            sh.page(f"{title} " + (", ".join(ls[:-1]) + " en " + ls[-1] if len(ls) > 1 else ls[0]), [(0, 24, 196, 280)])
            for t, y in (("Regelwerk gezien vanaf de BUITENZIJDE. Plaat en spouwlatten zijn weggelaten.", 30),
                         ("Geel = PIR. Maten van wandbegin tot stijl-randen.", 26.5)):
                label(c, 8, y, t, 6.3)
        cx = 98 - (u1 - u0) / 20                        # 98 = midden van het blad in de vorm
        cy = 157 + ((len(col) - 1) * row_h + 81) / 2 - 69 - r * row_h
        ps = [p for p in m.parts if p.group == grp]
        zmin = min(p.box[4] for p in ps if p.mat in (m.MAT["R44"], m.MAT["B69"], m.MAT["LAT"]))
        view = View(c, cx, cy, 10)
        ax = (0, 1) if axis == "x" else (2, 3)
        frame = [p for p in ps if p.mat in (m.MAT["R44"], m.MAT["B69"], m.MAT["LAT"]) and p.box[ax[0]] >= u0 - 1]
        pir = [p for p in ps if p.mat == m.MAT["PIR"]]
        for p in pir:
            rect(view, p.box[ax[0]] - u0, p.box[ax[1]] - u0, p.box[4] - zmin, p.box[5] - zmin, FILL[p.mat], lw=0.15)
        for p in frame:
            rect(view, p.box[ax[0]] - u0, p.box[ax[1]] - u0, p.box[4] - zmin, p.box[5] - zmin, FILL[p.mat], lw=0.35)
        name, _, sub = name.partition(" | ")
        view_title(c, cx, cy + 66, name)
        for j, ln in enumerate(simpleSplit(sub, "D", 6, (190 - cx) * mm) if sub else []):
            label(c, cx, cy + 62 - j * 2.8, ln, 6)
        stems = sorted({(round(p.box[ax[0]] - u0), round(p.box[ax[1]] - u0)) for p in frame
                        if (p.box[5] - p.box[4]) > 100})
        h = max(p.box[5] for p in frame) - zmin
        edges = [0] + sorted({e for s in stems for e in s}) + [round(u1 - u0)]
        edges = sorted(set(edges))
        for a, b in zip(edges, edges[1:]):
            if b - a >= 30:
                dim(view, a, 0, b, 0, -3.5, size=5.3)
        dim(view, 0, 0, u1 - u0, 0, -8, size=6)
        dim(view, u1 - u0, 0, u1 - u0, h, 3.5, size=6)
        zs = sorted({round(e - zmin) for p in frame if (p.box[5] - p.box[4]) <= 100 for e in (p.box[4], p.box[5])} | {0, round(h)})
        if len(zs) > 2:
            for a, b in zip(zs, zs[1:]):
                dim(view, 0, a, 0, b, -3.5, size=5.3)


def detail_box(c, x, y, w, h, title):
    c.setStrokeColor(C("#aab2b6"))
    c.setLineWidth(0.3)
    c.rect(x * mm, y * mm, w * mm, h * mm)
    label(c, x + 2, y + h - 5, title, 8.5, True)


def details_page(sh):
    box = lambda x, y, w, h: (x - 0.6, y - 0.6, x + w + 0.6, y + h + 0.6)
    sh.new("Details", "1:2 t/m 1:10", [
        ("Details 2, 5 en 7: ramen en ventilatie", [box(148, 188, 130, 94), box(148, 92, 130, 92), box(14, 28, 194, 60)]),
        ("Details 1 en 3: wand en dakrand", [box(14, 188, 130, 94), box(282, 188, 124, 94)]),
        ("Details 4 en 6: fundering en trap", [box(14, 92, 130, 92), box(282, 92, 124, 92)])])
    c = sh.c
    wood, stud, ply, pir, lat, dark, grey = FILL[m.MAT["DG"]], FILL[m.MAT["R44"]], FILL[m.MAT["LP9"]], FILL[m.MAT["PIR"]], FILL[m.MAT["LAT"]], FILL[m.MAT["DK"]], C("#c9c9c9")
    beam, floor18 = FILL[m.MAT["B69"]], FILL[m.MAT["BP12"]]
    alu, foam, tray = C("#9aa5ab"), C("#6a7780"), C("#20262a")

    # 1 wandopbouw horizontaal
    detail_box(c, 14, 188, 130, 94, "1  Wandopbouw bovenkamer, horizontaal (1:2)")
    v = View(c, 18, 214, 2)
    rect(v, 0, 18, 0, 110, wood)
    rect(v, 18, 40, 45, 89, lat)
    rect(v, 40, m.XL1, 0, 44, beam)
    rect(v, 40, m.XL1, 44, 110, pir)
    rect(v, m.XL1, m.IN_X0, 0, 110, ply)
    c.setStrokeColor(C("#2a6fb0"))
    c.setLineWidth(0.8)
    x0, y0 = v.p(40, 0)
    x1, y1 = v.p(40, 110)
    c.line(x0, y0, x1, y1)
    leader(v, 9, 100, 80, 270, "Gevelplank 18 (Douglas, werkende breedte 135)")
    leader(v, 29, 60, 80, 262, "Spouwlat 22x44; spouw onder en boven open met RVS gaas")
    leader(v, 40, 92, 80, 254, "Dampopen waterkerende folie op de regels, overlap 100")
    leader(v, 75, 80, 80, 246, "PIR 70 alu; naden met alu-tape, luchtdicht aan regels")
    leader(v, 75, 20, 80, 238, "Regel 44x69; PIR vult het vak, geen extra dampfolie")
    leader(v, 113, 40, 80, 230, "Lightply 9: gelijmd, geschroefd, blank gelakt")
    dim(v, 0, 0, 18, 0, -5, "18", 5.5)
    dim(v, 18, 0, 40, 0, -5, "22", 5.5)
    dim(v, 40, 0, m.XL1, 0, -5, str(m.J), 5.5)
    dim(v, m.XL1, 0, m.IN_X0, 0, -5, "9", 5.5)
    dim(v, 0, 0, m.IN_X0, 0, -11, str(m.IN_X0), 6)
    label(c, 80, 197, "Dampdicht binnen, dampopen buiten: droogt naar buiten.", 5.8)
    label(c, 80, 193, "Plaat draagt niets, maar schoort wel: schroef om de 100.", 5.8)

    # 2 raam onderaansluiting
    detail_box(c, 148, 188, 130, 94, "2  Raam binnenstebuiten, onderkant op de vloer, verticaal (1:3)")
    v = View(c, 170, 220, 3)
    rect(v, 40, 84, -81, -12, beam)           # rand tussenvloer
    rect(v, 40, 110, -12, 0, floor18)         # vloerplaat
    rect(v, 0, 18, -81, 0, wood)              # band
    rect(v, 18, 40, -44, 0, lat)              # lat, bovenkant gelijk met vloer
    rect(v, -1, 0, -17, 0, alu, lw=0.3)              # lekdorpelprofiel: staande zijde tegen de band
    poly(v, [(-1, -10), (-34, -19), (-34, -21), (-1, -12)], alu, lw=0.3)   # schuine zijde, vorm schematisch
    poly(v, [(-3, 2), (73, 2), (73, 32), (71, 32), (71, 4), (-1, 4), (-1, -9.5), (-11, -12.2), (-11, -9.6), (-3, -7.4)], tray, lw=0.2)   # EPDM met rand, over de band op de dorpel
    rect(v, 0, 71, 4, 130, colors.white, lw=0.5)     # kozijn
    rect(v, -19, 0, 35, 130, colors.white, lw=0.3)   # vleugel, nu buiten
    rect(v, -8, 16, 130, 150, C("#bfdcec"))
    leader(v, -10, 110, 214, 272, "Vleugel 19 naar buiten; draait en kiept naar buiten")
    leader(v, 36, 100, 214, 266, "Kozijn 71 diep, gelijk met gevel. Greep zit nu buiten")
    leader(v, 72, 25, 214, 260, "EPDM 30 omhoog achter kozijn, verlijmd: enige waterkering")
    leader(v, 44, 3, 214, 254, "EPDM onder het kozijn, over de band, tot op de dorpel")
    leader(v, -22, -16, 214, 248, "Alu lekdorpelprofiel 34x17 tegen de band, loopt af naar buiten")
    leader(v, 30, -20, 214, 242, "Lat band: bovenkant gelijk met vloer, kozijn steunt erop")
    label(c, 214, 232, f"Tussen stijlen {m.XR0-m.XL1} x {m.ROOM_H}, beneden {m.PART_X0-m.XL1} x {m.ROOM_H}: {m.WIN_GAP} mm speling per kant.", 6.3, True)
    label(c, 214, 228, "Geen dorpellat, geen houten opstand: kozijn direct op vloer.", 6)
    label(c, 214, 224, "Schroef 7,5x112 zijkant en boven: max. 150 uit hoek,", 6)
    label(c, 214, 220, "max. 600 h.o.h.; onder niet schroeven. Stijlen strak ertegen;", 6)
    label(c, 214, 216, f"kozijn raakt stijl over {m.WIN_D-m.F0} mm: voorboren, stijl recht, niet krom.", 6)
    label(c, 214, 210, "Controleer de afwateringssleuven op het kozijn: na", 6)
    label(c, 214, 206, "omkeren wateren die naar de binnenzijde af, in de goot.", 6)

    # 3 dakrand
    detail_box(c, 282, 188, 124, 94, "3  Dakrand voor, verticaal (1:5)")
    v = View(c, 316, 205, 5)
    ztop = lambda y: m.RAFT_F - (y - m.ROOF_Y0) * (m.RAFT_F - m.RAFT_B) / (m.ROOF_Y1 - m.ROOF_Y0)
    base = m.PLY + m.J
    poly(v, [(-150, base), (250, base), (250, base + ztop(250)), (-150, base + ztop(-150))], beam)
    rect(v, 40, 250, 0, m.PLY, ply)
    rect(v, 40, 84, m.PLY, base, beam)
    rect(v, 84, 250, m.PLY, m.PLY + m.PIR, pir)
    rect(v, 40, 84, -60, 0, stud)
    rect(v, 0, 18, -60, base - m.SOF_T, wood)
    rect(v, 18, 40, -60, base - m.SOF_T, lat)
    poly(v, [(-150, base + ztop(-150)), (250, base + ztop(250)), (250, base + ztop(250) + m.OSB_T), (-150, base + ztop(-150) + m.OSB_T)], FILL[m.MAT["OSB"]])
    rect(v, -132, -15, base - m.SOF_T, base, floor18)
    rect(v, -150, -132, base - 33, base + m.RAFT_F + m.OSB_T, dark)
    leader(v, 100, base + 58, 286, 272, f"EPDM 1,14 op OSB-3 11; afschot 1:{SLOPE} naar achter")
    leader(v, 40, base + 30, 286, 266, "Ventilatieruimte 28-57 tussen sporen, voor en achter open")
    leader(v, -8, base - 3, 286, 260, "Spleet 15 mm met RVS gaas: spouw en dak ventileren hier")
    leader(v, 120, m.PLY + 20, 286, 254, "PIR 70 op plafondplaat; plafond Lightply 9")
    leader(v, -141, base + 50, 286, 248, "Boeiboord en alu daktrim met druiprand")
    dim(v, -150, -5, 0, -5, -5, "150", 5.8)

    # 4 fundering
    detail_box(c, 14, 92, 130, 92, "4  Stelvoet onder de poot (1:4)")
    v = View(c, 50, 106, 4)
    rect(v, -60, 60, -30, 0, C("#b9b4aa"))
    rect(v, -40, 40, -1, 0, C("#3a3a3a"))
    rect(v, -m.FOOT_D / 2, m.FOOT_D / 2, 0, m.FOOT_T, C("#8d979c"))
    rect(v, -5, 5, m.FOOT_T, m.Z_POST + 45, C("#8d979c"))
    rect(v, -8, 8, m.Z_POST - 12, m.Z_POST - 4, C("#5a6268"))
    rect(v, -12, 12, m.Z_POST - 1.5, m.Z_POST, C("#5a6268"))
    rect(v, -34, 34, m.Z_POST, m.Z_LEG, FILL[m.MAT["P69"]])
    rect(v, -6, 6, m.Z_POST, m.Z_POST + 60, colors.white, lw=0.3)
    rect(v, -6, 6, m.Z_POST, m.Z_POST + 13, C("#5a6268"))
    rect(v, -5, 5, m.Z_POST + 13, m.Z_POST + 45, C("#8d979c"))
    rect(v, -60, 60, m.Z_LEG, m.Z_LEG + m.J, FILL[m.MAT["I69"]])
    label(c, 25, 101, "terras", 5.5)
    leader(v, 40, -0.5, 80, 101, "EPDM-rest onder de voet: grip, spaart de tegel")
    leader(v, 30, 4, 80, 107, "Hettich stelvoet M10x75, Ø75, RVS (art. 4297033)")
    leader(v, 8, m.Z_POST - 8, 80, 113, "RVS contramoer M10")
    leader(v, 6, m.Z_POST + 6, 80, 119, "Inslagmoer M10 (art. 3857241), vet + kit")
    leader(v, 6, m.Z_POST + 50, 80, 125, "Gat Ø11, 60 diep: ruimte voor de draad")
    leader(v, 34, m.Z_POST + 75, 80, 131, f"Poot 68x68, {m.Z_LEG - m.Z_POST}; kopse kant verzegeld")
    leader(v, 40, m.Z_LEG + 35, 80, 137, "Vloerframe 44x69 geïmpr.")
    dim(v, -60, 0, -60, m.Z_POST, -4, str(m.Z_POST), 5.8)
    dim(v, -60, 0, -60, m.Z_LEG, -10, str(m.Z_LEG), 5.8)
    label(c, 72, 96, "Los op de tegels; later vast aan de schutting (stap 15).", 6.3, True)

    # 5 raam kop
    detail_box(c, 148, 92, 130, 92, "5  Raam binnenstebuiten, bovenkant beneden, verticaal (1:3)")
    v = View(c, 184, 126, 3)
    jt = m.WIN_JOINT
    rect(v, 40, 84, jt + 9, jt + 78, beam)     # rand tussenvloer
    rect(v, 40, 84, jt, jt + 9, ply)           # onderplaat (bovenkant raam + voeg)
    rect(v, 40, 84, jt + 78, jt + 90, floor18)
    rect(v, 0, 18, jt, jt + 90, wood)          # band
    rect(v, 18, 40, jt + 46, jt + 90, lat)
    rect(v, 0, 71, -90, 0, colors.white, lw=0.5)
    rect(v, -19, 0, -90, -6, colors.white, lw=0.3)
    d = m.CANOPY_DROP
    poly(v, [(-90, jt + 12 - d), (0, jt + 12), (0, jt + 30), (-90, jt + 30 - d)], dark)   # luifel
    poly(v, [(-96, jt + 30 - d * 96 / 90), (0, jt + 30), (0, jt + 32), (-96, jt + 32 - d * 96 / 90)], tray, lw=0.2)   # EPDM
    rect(v, 0, 71, 0, jt, foam, lw=0.2)
    leader(v, -45, 27, 214, 174, "Regenluifel 18x90 antraciet, loopt 12 af; EPDM met druiprand")
    leader(v, 8, 30, 214, 168, "Band tussenvloer; spouwlat bovenin steunt het raam erboven")
    leader(v, 35, 2, 214, 162, f"Kop {m.WIN_JOINT} mm: afkitten, folie omzetten; plafond rust niet op kozijn")
    leader(v, 60, -40, 214, 156, "Kozijn: naad en glaslatten aan buitenzijde afkitten")
    label(c, 214, 148, "Boven beschermt het dakoverstek van 150 het raam. Beneden", 5.6)
    label(c, 214, 144, "staat het raam verder van het dak: daarom de luifel.", 5.6)
    label(c, 214, 138, "Zorg voor ruimte: de vleugel moet onder luifel en", 5.6)
    label(c, 214, 134, "overstek volledig vrij kunnen kiepen en draaien.", 5.6)
    label(c, 214, 128, "Controleer de eerste maanden na regen de goot en de", 5.6)
    label(c, 214, 124, "binnenzijde van het kozijn. Blijft het nat, kit de", 5.6)
    label(c, 214, 120, "buitennaden bij of maak een extra kap boven het raam.", 5.6)

    # 6 trap
    detail_box(c, 282, 92, 124, 92, "6  Trap langs linkerwand, zijaanzicht (1:10)")
    v = View(c, 300, 110, 10)
    depth = m.IN_Y1 - m.IN_Y0
    climb = m.Z_UP - m.Z_DECK
    hole0, hole1 = m.HOLE_Y0 - m.IN_Y0, m.HOLE_Y1 - m.IN_Y0
    rect(v, 0, depth, -12, 0, floor18)
    if hole0 > 0:
        rect(v, 0, hole0, m.ROOM_H, climb, beam)
    if hole1 < depth:
        rect(v, hole1, depth, m.ROOM_H, climb, beam)
    s0, s1 = m.SY2(m.ST_Y0, m.ST_Y1)
    h0, h1 = s0 - m.IN_Y0, s1 - m.IN_Y0
    rect(v, hole0, hole1, m.ROOM_H + 9, climb - 12, None, lw=0.3)            # balk rechts van het trapgat, erachter
    poly(v, [(y - m.IN_Y0, z - m.Z_DECK) for y, z in m.stringer_outline(free=True)], C("#c49a6c"))
    poly(v, [(y - m.IN_Y0, z - m.Z_DECK) for y, z in m.stringer_outline()], floor18)
    leader(v, (m.TAB_Y0 + m.TAB_Y1) / 2 - m.IN_Y0, m.TAB_Z1 - m.Z_DECK - 20, 338, 176,
           f"Lip rechterboom: 2 x RVS 4 x 40 in de balk", 5.2)
    poly(v, [(y - m.IN_Y0, z - m.Z_DECK) for y, z in m.strip_outline()], C("#7f5a34"))
    for i in range(m.N_RISE - 1):
        z = m.RISE * (i + 1)
        ya, yb = (t - m.IN_Y0 for t in m.TREAD_AT[i])
        rect(v, ya, yb, z - 12, z, C("#7f5a34"))
        dim(v, ya, z, yb, z, 3, str(m.TREAD_D[i]), 4.5)
    dim(v, depth, 0, depth, climb, 5, str(climb), 5.5)
    dim(v, h0, -12, h1, -12, -3, str(round(h1 - h0)), 5.5)
    label(c, 290, 97.5, f"{m.N_RISE} optreden van {round(m.RISE)}, treden {TREADS} diep, {m.ST_X1-m.ST_X0} breed, helling {STAIR_DEG}°. Sisal", 6.3)
    label(c, 290, 94.5, "of rubbermat. Donker: versterking rechterboom, licht: lip. Trap vóór de tussenvloer plaatsen.", 6.3)

    # 7 ventilatie
    detail_box(c, 14, 28, 194, 60, "7  Ventilatie (natuurlijke trek)")
    label(c, 18, 78, f"Afvoer: PVC Ø100 door de achterwand, hart z = {m.VENT['z']} ({m.Z_U_TOP-m.VENT['z']} onder het plafond), x = {m.VENT['x']}.", 6.5)
    label(c, 18, 74, "Binnen: afsluitbaar rooster Ø100. Buiten: rooster Ø100, buis licht aflopend naar buiten; RVS-gaas ca. 1 mm erachter, jaarlijks nakijken.", 6.5)
    label(c, 18, 70, f"Aanvoer: open voorkant -> veranda -> lage inlaat {m.VENT_W} x {m.VENT_H} onder het kattenluik -> trapkamer -> trapgat {m.HOLE_X1-m.HOLE_X0} x {m.HOLE_Y1-m.HOLE_Y0}.", 6.5)
    label(c, 18, 66, "Trapgat linksvoor, afvoer rechtsachter: boven loopt de lucht schuin door de kamer, dus de mand rechts van het trapgat, uit die lijn.", 6.5)
    label(c, 18, 60, "Stand rooster: vorst bijna dicht (circa 2 m³/h volstaat), 0-5 °C half open, boven 5 °C helemaal open.", 6.5, True)
    label(c, 18, 56, "Hygrometer in de bovenkamer. Blijft de luchtvochtigheid langdurig boven 75-80 %: rooster verder open.", 6.5)



def nest_page(sh):
    sh.new("Zaagplan platen", "1:20")
    c = sh.c
    COLS, CW, YTOP, YMIN = (16, 220), 188, 272, 44     # twee kolommen, elk een A4-blad
    col, x, y, row_h = 0, COLS[0], YTOP, 0
    names, colmax = [[], []], [0, 0]
    for key, name, sw, sh_ in (("BP12", "Betonplex 12 mm, 2500x1250", 2500, 1250), ("OSB", "OSB-3 11 mm, 2440x1220", 2440, 1220), ("LP9", "Lightply multiplex 9 mm, 2440x1220", 2440, 1220), ("PIR", "PIR 70 mm, 1200x600", 1200, 600)):
        for i, s in enumerate(NEST[key]):
            sc = 20
            pw, ph = sw / sc, sh_ / sc
            if x + pw > COLS[col] + CW:          # nieuwe rij
                x, y, row_h = COLS[col], y - row_h - 9, 0
            if y - ph - 4 < YMIN:                # nieuwe kolom
                col += 1
                if col >= len(COLS):
                    sys.exit("Zaagplan platen past niet op twee A4-bladen")
                x, y, row_h = COLS[col], YTOP, 0
            row_h = max(row_h, ph + 4)
            colmax[col] = max(colmax[col], x + pw)
            short_name = name.split()[0]
            if short_name not in names[col]:
                names[col].append(short_name)
            label(c, x, y, f"{name}  plaat {i+1}/{len(NEST[key])}" + ("  (zaagvolgorde: zaagplannen bouwmarkt)" if key == "BP12" else ""), 6.2, True)
            v = View(c, x, y - 2 - ph, sc)
            rect(v, 0, sw, 0, sh_, C("#f4f1ea"), lw=0.4)
            for ix, iy, iw, ih, nm in s.items:
                rect(v, ix, ix + iw, iy, iy + ih, FILL[m.MAT[key]], lw=0.3)
                c.setFillColor(colors.white if key == "BP12" else INK)
                fs = 5
                short = nm.split(":", 1)
                t = f"{short[0]} {round(iw)}x{round(ih)}"
                txt = short[1][:24] if len(short) > 1 else ""
                cx_, cy_ = v.p(ix + iw / 2, iy + ih / 2)
                if iw / sc > 14 and ih / sc > 6:
                    c.setFont("D", fs)
                    c.drawCentredString(cx_, cy_ + 0.5, t)
                    c.drawCentredString(cx_, cy_ - 5, txt)
                elif ih / sc > 14:
                    c.saveState()
                    c.translate(cx_, cy_)
                    c.rotate(90)
                    c.setFont("D", fs)
                    c.drawCentredString(0, -1.5, f"{t}")
                    c.restoreState()
                elif iw / sc > 9 and ih / sc >= 1.4:
                    c.setFont("D", 3.6)
                    c.drawCentredString(cx_, cy_ - 1.2, t)
                elif ih / sc > 9:
                    c.saveState()
                    c.translate(cx_, cy_)
                    c.rotate(90)
                    c.setFont("D", 3.6)
                    c.drawCentredString(0, -1.2, t)
                    c.restoreState()
            x += pw + 4
    for x0 in COLS[:col + 1]:
        label(c, x0, 34, "Zaagsnede 4 mm meegerekend. Letter = bouwdeel (zie zaaglijst).", 6.3)
        label(c, x0, 30.5, "Positie van elk stuk: Excel, tabblad Platen op maat. Zaagopdracht voor de bouwmarkt:", 6.3)
        label(c, x0, 27, "Kattenchalet_zaagplannen_bouwmarkt.pdf. PIR snijd je zelf.", 6.3)
    sh.pages([("Zaagplan platen: " + ", ".join(names[k]), [(round((COLS[k] + colmax[k]) / 2 - 98, 1), 24, round((COLS[k] + colmax[k]) / 2 + 98, 1), 279)])
              for k in range(col + 1)])


def bars_page(sh):
    """Zaagplan voor alle balken, regels, palen en latten: per handelslengte de stukken op schaal."""
    sh.new("Zaagplan balken en latten", "1:25", [("Zaagplan balken en palen", [(1, 24, 195, 279)]),
                                                 ("Zaagplan spouwlatten en toelichting", [(185, 24, 379, 279)])])
    c = sh.c
    sc, bh, pitch = 25, 6.5, 10.2

    def fit(text, font, size, width):   # width in mm
        width *= mm
        if pdfmetrics.stringWidth(text, font, size) <= width:
            return text
        while text and pdfmetrics.stringWidth(text + ".", font, size) > width:
            text = text[:-1]
        return text + "." if len(text) >= 3 else ""

    def block(key, x, y):
        bars_ = NEST[key]
        if not bars_:
            return y
        mix = " + ".join(f"{sum(b_['stock'] == s for b_ in bars_)} x {s}" for s in sorted(STOCK[key], reverse=True)
                         if any(b_["stock"] == s for b_ in bars_))
        label(c, x, y, f"{m.MAT[key]}: {len(bars_)} {'stuk' if len(bars_) == 1 else 'stuks'} ({mix})", 7.5, True, ACC)
        y -= 4
        bx = x + 21
        for i, bar in enumerate(bars_, 1):
            y -= pitch
            c.setStrokeColor(INK)
            c.setLineWidth(0.3)
            c.rect(x * mm, (y + 1.6) * mm, 3 * mm, 3 * mm)          # afvinkhokje
            label(c, x + 4.5, y + 2.2, f"{i}", 7, True)
            label(c, x + 10, y + 2.2, f"{bar['stock']}", 6.2)
            v = View(c, bx, y, sc)
            rect(v, 0, bar["stock"], 0, bh * sc, C("#f4f1ea"), lw=0.4)
            u = 0
            for l, nm in bar["cuts"]:
                rect(v, u, u + l, 0, bh * sc, FILL[m.MAT[key]], lw=0.3)
                w = l / sc - 0.8
                cx_ = (bx + (u + l / 2) / sc) * mm
                g, name = nm.split(":", 1)
                c.setFillColor(INK)
                t = fit(str(int(l)), "DB", 5.6, w)
                if t:
                    c.setFont("DB", 5.6)
                    c.drawCentredString(cx_, (y + 3.6) * mm, t)
                    c.setFont("D", 4.3)
                    c.drawCentredString(cx_, (y + 1.0) * mm, fit(f"{g} {name}", "D", 4.3, w))
                else:   # te kort voor tekst in de balk: maat erboven
                    c.setFont("DB", 4.6)
                    c.drawCentredString(cx_, (y + bh + 0.8) * mm, f"{g} {int(l)}")
                u += l + 4
            rest = bar["stock"] - u
            if rest > 0:
                c.setFillColor(C("#7a7a7a"))
                c.setFont("D", 4.6)
                t = next((t for t in (f"rest {int(rest)}", str(int(rest)))
                          if pdfmetrics.stringWidth(t, "D", 4.6) <= (rest / sc - 0.6) * mm), "")
                if t:
                    c.drawCentredString((bx + (u + rest / 2) / sc) * mm, (y + 2.4) * mm, t)
        return y - 7

    y = block("B69", 16, 272)
    y = block("I69", 16, y)
    y = block("R44", 16, y)
    block("P69", 16, y)
    y = block("LAT", 222, 272)

    notes = [
        "Zo lezen: elke balk is één handelslengte, links begonnen.",
        "Zaag de stukken in deze volgorde af; na elke snede gaat 4 mm verloren.",
        "Hornbach mag tot 1 cm korter leveren: meet de lat eerst en houd",
        "die marge aan het eind (de rest) over.",
        "Letter = bouwdeel, zoals in de zaaglijst en op de wandframes T8 en T9.",
        "Vink het hokje af als de balk gezaagd is.",
        "Schrijf bouwdeel en naam met potlood op elk stuk.",
        "Gelijke stukken (stijlen 417, balken 596) mogen onderling wisselen.",
        f"Sporen en zijsporen M: eerst op lengte {m.RAFT_L} zagen, daarna de schuine snede volgens T7.",
        f"Poten A: alle 6 op {m.Z_LEG-m.Z_POST} mm; de stelvoeten vangen het afschot",
        "van het terras op.",
        "Spouwlatten: hier als hele stukken getekend. Met een las op een regel of rand",
        "volstaan 9 latten (Excel, Inkoop); zaag dan de korte stukken uit de resten",
        "van de latten links, rechts en achter.",
        "Gevelplanken, hoeklatten, boeiboorden en kader uit Douglas 18 x 145:",
        "Excel, tabblad Latten op lengte.",
    ]
    ny = y - 4
    label(c, 222, ny, "Toelichting", 7.5, True, ACC)
    for t in notes:
        ny -= 4.6
        label(c, 222, ny, t, 6.3)


PAGE_LAYOUT = {   # A4-blad: uitsnede (x0, y0) op de A3-vorm en x van titel en notities; zo staat de tekening in het midden
    "T1a": (1.9, 28, 18.2), "T1b": (196.8, 28, 214.6), "T2a": (2.6, 24, 18.7), "T2b": (210.7, 24, 226.8),
    "T3a": (27.2, 24, 64.9), "T3b": (181.5, 24, 219.2), "T4a": (1.4, 24, 39.0), "T4b": (181.5, 24, 219.2),
    "T5a": (2.6, 24, 18.7), "T5b": (193.2, 24, 214.6), "T6a": (1.9, 24, 31.9), "T6b": (186.6, 24, 216.6),
    "T7a": (7.5, 24, 38.0), "T7b": (205.6, 50.7, 226.8),
}


def win(key):
    x0, y0, _ = PAGE_LAYOUT[key]
    return [(x0, y0, x0 + 196, y0 + 256)]


def tx(key):
    return PAGE_LAYOUT[key][2]


def write_drawings(path):
    c = canvas.Canvas(path, pagesize=landscape(A3))
    c.setTitle("Kattenchalet tekeningen")
    sh = Sheet(c)
    top = round(m.Z_RAFT + m.RAFT_B + 19.2)
    room_lbl = f"{m.ROOM_H}"

    # T1 overzicht 3D
    sh.new("Overzicht 3D", "n.v.t.", legend=True, split=True)
    sh.page("Overzicht 3D, voor-rechts", win("T1a"))
    view_title(c, tx("T1a"), 276, "Voor-rechts")
    iso_draw(c, iso_boxes(), 35, 95, 13)
    for x0 in (tx("T1a"),):
        label(c, x0, 40, f"Hoofdmaten: buiten {m.W} x {m.D}, hoogte {round(m.Z_TOP)} (bovenkant dak voor), dak {m.ROOF_W} x {m.ROOF_L}.", 6.8, True)
        label(c, x0, 35.5, f"Bovenkamer binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Trapkamer {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Veranda vrij {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H}.", 6.5)
        label(c, x0, 31, f"Raam boven 1000 x 500, beneden 500 x 500, beide binnenstebuiten. Totaalgewicht ongeveer {round(R['mass'])} kg.", 6.5)
    sh.page("Overzicht 3D, achter-links", win("T1b"))
    view_title(c, tx("T1b"), 276, "Achter-links")
    iso_draw(c, iso_boxes(mirror=True), 225, 95, 13)
    for x0 in (tx("T1b"),):
        label(c, x0, 40, f"Hoofdmaten: buiten {m.W} x {m.D}, hoogte {round(m.Z_TOP)} (bovenkant dak voor), dak {m.ROOF_W} x {m.ROOF_L}.", 6.8, True)
        label(c, x0, 35.5, f"Bovenkamer binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Trapkamer {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Veranda vrij {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H}.", 6.5)
        label(c, x0, 31, f"Raam boven 1000 x 500, beneden 500 x 500, beide binnenstebuiten. Totaalgewicht ongeveer {round(R['mass'])} kg.", 6.5)


    # T2 aanzichten voor/achter
    sh.new("Aanzichten voor en achter", "1:10", legend=True, split=True)
    sh.page("Vooraanzicht", win("T2a"))
    v = View(c, 40, 72, 10)
    view_title(c, tx("T2a"), 262, "Vooraanzicht")
    front_view(v)
    dim(v, 0, 0, m.W, 0, -10, str(m.W))
    dim(v, m.ROOF_X0, m.Z_TOP, m.ROOF_X1, m.Z_TOP, 4, f"{m.ROOF_W} dak")
    dim(v, -100, 0, -100, m.Z_TOP, -8, str(round(m.Z_TOP)))
    for w, t in ((m.WIN_U, "Raam 1000 x 500, tussen de wanden"), (m.WIN_L, "Raam 500 x 500")):
        x_, y_ = v.p((w["x0"] + w["x1"]) / 2, (w["z0"] + w["z1"]) / 2)
        c.setFillColor(INK)
        c.setFont("D", 6)
        c.drawCentredString(x_, y_ - 2, t)
    rx = m.ROOF_X1
    dim(v, rx, 0, rx, m.Z_DECK, 4, str(m.Z_DECK))
    dim(v, rx, m.Z_DECK, rx, m.Z_L_TOP, 4, room_lbl)
    dim(v, rx, m.Z_L_TOP, rx, m.Z_UP, 4, str(m.Z_UP - m.Z_L_TOP))
    dim(v, rx, m.Z_UP, rx, m.Z_U_TOP, 4, room_lbl)
    dim(v, rx, m.Z_U_TOP, rx, m.Z_TOP, 4, str(round(m.Z_TOP - m.Z_U_TOP)))
    dim(v, m.VER_X0, m.Z_DECK, m.IN_X1, m.Z_DECK, 5, f"{m.IN_X1-m.VER_X0} vrij", 6)
    for x0 in (tx("T2a"),):
        label(c, x0, 257.5, "Hoeklatten, boeiboorden en regenluifel in antraciet beits, de rest van de gevel met kader en band in grenen beits.", 6.3)
        label(c, x0, 254, "Tekenkleur indicatief; nerf blijft zichtbaar. Plankmaten: zie zaaglijst. Luifel tussen de hoeklatten.", 6.3)
    sh.page("Achteraanzicht", win("T2b"))
    v = View(c, 370, 72, 10, flip=True)
    view_title(c, tx("T2b"), 262, "Achteraanzicht (van achteren gezien)")
    back_view(v)
    dim(v, 0, 0, m.W, 0, -10, str(m.W))
    dim(v, -100, 0, -100, top, 8, str(top))
    for x0 in (tx("T2b"),):
        label(c, x0, 257.5, "Hoeklatten, boeiboorden en regenluifel in antraciet beits, de rest van de gevel met kader en band in grenen beits.", 6.3)
        label(c, x0, 254, "Tekenkleur indicatief; nerf blijft zichtbaar. Plankmaten: zie zaaglijst. Luifel tussen de hoeklatten.", 6.3)


    # T3 aanzichten zijkanten
    sh.new("Aanzichten zijkanten", "1:10", legend=True, split=True)
    sh.page("Linkeraanzicht", win("T3a"))
    v = View(c, 165, 72, 10, flip=True)
    view_title(c, tx("T3a"), 262, "Linkeraanzicht (voorzijde rechts), geen openingen")
    side_view(v, "L")
    dim(v, 0, 0, m.D, 0, -10, str(m.D))
    dim(v, m.ROOF_Y0, m.Z_TOP, m.ROOF_Y1, m.Z_TOP, 3, f"{m.ROOF_L} dak")
    sh.page("Rechteraanzicht", win("T3b"))
    v = View(c, 240, 72, 10)
    view_title(c, tx("T3b"), 262, "Rechteraanzicht (voorzijde links), geheel dicht")
    side_view(v, "R")
    dim(v, 0, 0, m.D, 0, -10, str(m.D))
    dim(v, m.ROOF_Y1, 0, m.ROOF_Y1, top, 4, f"achter {top}")

    # T4 doorsneden
    sh.new("Doorsneden A en B", "1:10", legend=True, split=True)
    sh.page("Doorsnede A-A", win("T4a"))
    v = View(c, 60, 72, 10)
    view_title(c, tx("T4a"), 262, "A-A: door trap, trapgat en bovenkamer (x = 215)")
    section_x(v, 215)
    dim(v, m.IN_Y0, m.Z_U_TOP, m.IN_Y1, m.Z_U_TOP, -6, f"{m.IN_Y1-m.IN_Y0} binnen", 6)
    dim(v, m.YB1, m.Z_DECK, m.YB1, m.Z_L_TOP, 8, room_lbl)
    dim(v, m.YB1, m.Z_UP, m.YB1, m.Z_U_TOP, 8, room_lbl)
    dim(v, m.HOLE_Y0, m.Z_UP, m.HOLE_Y1, m.Z_UP, 5, f"trapgat {m.HOLE_Y1-m.HOLE_Y0}", 6)
    sh.page("Doorsnede B-B", win("T4b"))
    v = View(c, 240, 72, 10)
    view_title(c, tx("T4b"), 262, f"B-B: door veranda en bovenkamer (x = {SEC_B})")
    section_x(v, SEC_B)
    dim(v, 0, m.Z_DECK, m.IN_Y1, m.Z_DECK, 5, f"{m.IN_Y1} vrij", 6)
    dim(v, m.YB1, 0, m.YB1, m.Z_LEG, 8, str(m.Z_LEG))
    dim(v, m.YB1, m.Z_LEG, m.YB1, m.Z_DECK, 8, str(m.Z_DECK - m.Z_LEG))
    dim(v, m.YB1, m.Z_L_TOP, m.YB1, m.Z_UP, 8, str(m.Z_UP - m.Z_L_TOP))
    dim(v, m.YB1, m.Z_U_TOP, m.YB1, m.Z_RAFT, 8, str(m.Z_RAFT - m.Z_U_TOP))

    # T5 doorsneden C/D
    sh.new("Doorsneden C en D", "1:10", legend=True, split=True)
    sh.page("Doorsnede C-C", win("T5a"))
    v = View(c, 40, 72, 10)
    view_title(c, tx("T5a"), 262, "C-C: door de ramen, kijkrichting achter (y = 30)")
    section_y(v, 30)
    dim(v, m.WIN_U["x0"], m.Z_UP, m.WIN_U["x1"], m.Z_UP, 8, f"raam {m.WIN_U_W}", 6)
    dim(v, m.WIN_L["x0"], m.Z_DECK, m.WIN_L["x1"], m.Z_DECK, 8, f"raam {m.WIN_L_W}", 6)
    sh.page("Doorsnede D-D", win("T5b"))
    v = View(c, 225, 72, 10)
    view_title(c, tx("T5b"), 262, f"D-D: door doorgang en trap, kijkrichting achter (y = {SEC_D})")
    section_y(v, SEC_D)
    dim(v, m.IN_X0, m.Z_U_TOP, m.IN_X1, m.Z_U_TOP, -6, f"{m.IN_X1-m.IN_X0} binnen", 6)
    dim(v, m.IN_X0, m.Z_DECK, m.ROOM_X1, m.Z_DECK, 5, f"{m.ROOM_X1-m.IN_X0} binnen", 6)
    dim(v, m.VER_X0, m.Z_DECK, m.IN_X1, m.Z_DECK, 5, str(m.IN_X1 - m.VER_X0), 6)

    # T6 plattegronden
    sh.new("Plattegronden", "1:10", legend=True, split=True)
    sh.page("Plattegrond beneden en vloerframe", win("T6a"))
    v = View(c, 40, 158, 10)
    view_title(c, tx("T6a"), 262, "Beneden, snede z = 500")
    plan(v, 500)
    dim(v, 0, 0, m.W, 0, -6, str(m.W), 6)
    dim(v, 0, 0, 0, m.D, -6, str(m.D), 6)
    dim(v, m.IN_X0, m.IN_Y1, m.ROOM_X1, m.IN_Y1, 12, str(m.ROOM_X1 - m.IN_X0), 6)
    dim(v, m.VER_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 12, str(m.IN_X1 - m.VER_X0), 6)
    dim(v, m.VER_X0, m.CAT_Y0, m.VER_X0, m.CAT_Y1, 7, str(m.CAT_Y1 - m.CAT_Y0), 5.5)
    label(c, tx("T6a"), 257.5, f"Trap langs de linkerwand, kattenluik achterin (doorgang {m.CAT_Y1 - m.CAT_Y0} x {m.CAT_H} aan de trapzijde), voorkant veranda open, rechterwand dicht.", 6.5)
    v = View(c, 40, 46, 10)
    view_title(c, tx("T6a"), 140, "Vloerframe, gezien van boven (vloerplaat weg)")
    plan(v, m.Z_DECK0 - 1, only=lambda p: p.group.startswith("A"))
    xs = [m.F1] + [e for x in m.FLOOR_X[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    depth_dims(v, m.XR1)
    c.setDash(2, 1.5)
    for lx in m.LEG_X:
        for ly in m.LEG_Y:
            rect(v, lx[0], lx[1], ly[0], ly[1], None, stroke=ACC, lw=0.5)
    c.setDash()
    cx = [(a + b) / 2 for a, b in m.LEG_X]
    cy = [(a + b) / 2 for a, b in m.LEG_Y]
    for a, b in zip(cx, cx[1:]):
        dim(v, a, m.F0, b, m.F0, -11, f"{round(b - a)} h.o.h. poot", 5.3)
    dim(v, m.F0, cy[0], m.F0, cy[1], -6, f"{round(cy[1] - cy[0])} h.o.h. poot", 5.3)
    label(c, tx("T6a"), 135.5, "Stippellijn: poten 68 x 68 onder het frame.", 6)
    sh.page("Plattegrond boven en tussenvloer", win("T6b"))
    v = View(c, 225, 158, 10)
    view_title(c, tx("T6b"), 262, "Boven, snede z = 1200")
    plan(v, 1200)
    dim(v, 0, 0, m.W, 0, -6, str(m.W), 6)
    dim(v, m.IN_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 12, str(m.IN_X1 - m.IN_X0), 6)
    dim(v, m.IN_X1, m.IN_Y0, m.IN_X1, m.IN_Y1, 13, str(m.IN_Y1 - m.IN_Y0), 6)
    dim(v, 0, 0, 0, m.D, -6, str(m.D), 6)
    dim(v, m.HOLE_X0, m.HOLE_Y1, m.HOLE_X1, m.HOLE_Y1, -17, f"gat {m.HOLE_X1-m.HOLE_X0}", 5.5)
    label(c, tx("T6b"), 257.5, "Raam voor, trapgat linksvoor, afvoer rechtsachter, mand bij het raam rechts van het trapgat.", 6.5)
    v = View(c, 225, 46, 10)
    view_title(c, tx("T6b"), 140, "Tussenvloer: balken en PIR (bovenplaat weg)")
    plan(v, m.Z_MID_T - 1, only=lambda p: p.group.startswith("G") and "plaat" not in p.name.lower())
    xs = [m.F1] + [e for x in m.MID_X[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    depth_dims(v, m.XR1)
    for a, b, t in ((m.F0, m.HOLE_Y0, None), (m.HOLE_Y0, m.HOLE_Y1, f"gat {m.HOLE_Y1 - m.HOLE_Y0}"), (m.HOLE_Y1, m.YB1, None)):
        dim(v, m.F0, a, m.F0, b, -5, t, 5.3)
    dim(v, m.F0, m.HOLE_Y0, m.HOLE_X0, m.HOLE_Y0, -3, size=5.3)
    label(c, tx("T6b"), 135.5, f"Trapgat {HOLE} in onderplaat en vloerplaat: {m.HOLE_X0 - m.F0} uit de linkerrand, {m.HOLE_Y0 - m.F0} uit de voorrand.", 6)

    # T7 dakplattegronden
    sh.new("Plafond en dak", "1:10", legend=True, split=True)
    sh.page("Plafond en spoor", win("T7a"))
    v = View(c, 45, 158, 10)
    view_title(c, tx("T7a"), 262, "Plafond: balken en PIR (van boven)")
    plan(v, m.Z_RAFT - 1, only=lambda p: p.group.startswith("L"))
    xs = [m.F1] + [e for x in m.CEIL_X[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    depth_dims(v, m.XR1)
    v = View(c, 45, 45, 10)
    view_title(c, tx("T7a"), 62, f"Spoor, zijaanzicht ({len(m.CEIL_X)} sporen + 2 zijsporen)")
    poly(v, [(0, 0), (m.RAFT_L, 0), (m.RAFT_L, m.RAFT_H1), (0, m.RAFT_H0)], FILL[m.MAT["B69"]], lw=0.4)
    dim(v, 0, 0, m.RAFT_L, 0, -5, str(m.RAFT_L), 6)
    dim(v, 0, 0, 0, m.RAFT_H0, -5, str(m.RAFT_H0), 5.5)
    dim(v, m.RAFT_L, 0, m.RAFT_L, m.RAFT_H1, 4, str(m.RAFT_H1), 5.5)
    label(c, tx("T7a"), 30, f"Uit balk 44x69: schuine zaagsnede. Afschot 1:{SLOPE} naar de achterkant. Dakgoot achter, afvoer weg van de schutting.", 6.5)

    sh.page("Dak: sporen en overstek", win("T7b"))
    v = View(c, 245, 150, 10)
    view_title(c, tx("T7b"), 262, "Dak: sporen en overstek (dakplaat weg)")
    plan(v, m.Z_RAFT + 70, only=lambda p: p.group.startswith("M") and p.mat != m.MAT["OSB"])
    dim(v, m.ROOF_X0, m.ROOF_Y0, m.ROOF_X1, m.ROOF_Y0, -5, str(m.ROOF_W), 6)
    dim(v, m.ROOF_X0, m.ROOF_Y0, m.ROOF_X0, m.ROOF_Y1, -6, str(m.ROOF_L), 6)
    dim(v, 0, m.ROOF_Y1, m.F0, m.ROOF_Y1, 4, size=5.3)
    for a, b in ((m.ROOF_Y0, 0), (0, m.D), (m.D, m.ROOF_Y1)):
        dim(v, m.ROOF_X1, a, m.ROOF_X1, b, 4, size=5.3)
    dim(v, m.ROOF_X0, m.ROOF_Y0, 0, m.ROOF_Y0, -10, size=5.3)
    ks = [m.RAFT_Y0] + [e for y in m.KLOS_Y for e in (y, y + m.S)] + [m.RAFT_Y1]
    for a, b in zip(ks, ks[1:]):
        dim(v, m.ROOF_X0, a, m.ROOF_X0, b, -2.5, size=4.8)
    label(c, tx("T7b"), 92, f"Links: maten van de rijklossen ({m.CEIL_X[0] - m.SIDE_RAFT[0] - m.S} lang) langs het zijspoor, vanaf de voorkant van de sporen. Rechts: overstek, gevel en dak.", 6)

    # T8, T9 wanden
    walls_page(sh, "Wandframes beneden", [
        ("B Voorwand beneden", "x", m.F0, m.PART_X1, f"B  Voorwand beneden, {m.PART_X1-m.F0} breed | Opening {m.PART_X0-m.XL1} = raam {m.WIN_L_W} + 2 x {m.WIN_GAP} speling. Stijlen pas definitief vast als het raam staat.", False),
        ("C Achterwand beneden", "x", m.F0, m.XR1, f"C  Achterwand beneden, {m.XR1-m.F0} lang", False),
        ("D Linkerwand beneden", "y", m.F1, m.IN_Y1, f"D  Linkerwand beneden, {m.IN_Y1-m.F1} lang", False),
        ("E Scheidingswand", "y", m.F1, m.IN_Y1, f"E  Scheidingswand, {m.IN_Y1-m.F1} lang | Doorgang {m.CAT_Y1 - m.CAT_Y0} x {m.CAT_H}; kattenluik {m.FLAP_W} x {m.FLAP_H} in de verandaplaat, op {m.FLAP_Z} boven de vloer. Luchtinlaat laag onder het luik.", False),
        ("F Rechterwand beneden", "y", m.F0, m.IN_Y1, f"F  Rechterwand beneden, {m.IN_Y1-m.F0} lang, geheel dicht", False),
    ])
    walls_page(sh, "Wandframes boven", [
        ("H Voorwand boven", "x", m.F0, m.XR1, f"H  Voorwand boven, {m.XR1-m.F0} breed | Opening {m.XR0-m.XL1} = raam {m.WIN_U_W} + 2 x {m.WIN_GAP} speling. Stijlen pas definitief vast als het raam staat.", False),
        ("I Achterwand boven", "x", m.F0, m.XR1, f"I  Achterwand boven, {m.XR1-m.F0} lang", False),
        ("J Linkerwand boven", "y", m.F1, m.IN_Y1, f"J  Linkerwand boven, {m.IN_Y1-m.F1} lang", False),
        ("K Rechterwand boven", "y", m.F1, m.IN_Y1, f"K  Rechterwand boven, {m.IN_Y1-m.F1} lang", False),
    ])

    details_page(sh)
    nest_page(sh)
    bars_page(sh)

    # montage explosie
    sh.new("Montagevolgorde (explosietekening)", "n.v.t.", [("Montagevolgorde (explosietekening)", [(10, 24, 204, 279)])])
    offs = {"A": 0, "B": 180, "C": 180, "D": 180, "E": 180, "F": 180, "N": 180, "G": 420, "H": 660, "I": 660, "J": 660, "K": 660, "L": 880, "M": 1100}
    EXS = 18
    iso_draw(c, iso_boxes(dz=lambda p: offs.get(p.group[0], 0), skip=("P", "Q")), 95, 66, EXS)
    for t, z in (("5. Dakopbouw: sporen, OSB, EPDM, boeiboord, daktrim", 2650), ("4. Plafondcassette op de bovenwanden", 2340),
                 ("3. Vier bovenwanden op de tussenvloer", 1750), ("2. Tussenvloer als cassette op de benedenwanden", 1150),
                 ("1. Benedenwanden en trap op het vloerframe", 700), ("0. Stelvoeten, poten en vloerframe", 200)):
        label(c, 14, 66 + (z + 450) / EXS, t, 6.5, True)
    label(c, 14, 30, "Gevelfolie, spouwlatten, ramen en gevelplanken volgen als het casco staat en waterdicht is.", 6.5)
    label(c, 14, 26.5, "De ramen zijn hier niet getekend.", 6.5)
    flap_page(sh)
    bp12_page(sh)
    sh.flush()
    c.save()


def bp12_page(sh):
    """Thuis zagen: de trapbomen en de betonplex-stroken uit de bouwmarkt op maat. De zaagopdracht voor de
    bouwmarkt zelf staat in Kattenchalet_zaagplannen_bouwmarkt.pdf."""
    from reportlab.lib.utils import simpleSplit
    sh.new("Trap en betonplex thuis zagen", "1:5", [("Trap en betonplex thuis zagen", [(10, 24, 204, 279)])])
    c = sh.c
    s_ = NEST["BP12"][0]

    def para(x, y, w, text, size=7, bold=False, color=INK):
        for line in simpleSplit(text, "DB" if bold else "D", size, w * mm):
            label(c, x, y, line, size, bold, color)
            y -= size * 0.46
        return y - 1

    x, w = 16, 182
    y = para(x, 272, w, f"Rechterboom op het plaatstuk {m.STRINGER_L} x {m.STRINGER_W} (1:5)", 8.5, True, ACC) - 2
    k, n = m.ST_K, m.ST_N
    pts = m.stringer_fwd(free=True)
    uv = [((yy + k * zz) / n, (-k * yy + zz) / n) for yy, zz in pts]
    u0, v0 = min(u for u, _ in uv), min(q for _, q in uv)
    y0 = y - m.STRINGER_W / 5 - 2
    vs = View(c, x + 8, y0, 5)
    rect(vs, 0, m.STRINGER_L, 0, m.STRINGER_W, C("#f4f1ea"))
    poly(vs, [(u - u0, q - v0) for u, q in uv], FILL[m.MAT["BP12"]])
    su = [((yy + k * zz) / n - u0, (-k * yy + zz) / n - v0) for yy, zz in m.strip_fwd()]
    poly(vs, su, C("#7f5a34"))
    dim(vs, 0, 0, m.STRINGER_L, 0, -4, str(m.STRINGER_L))
    dim(vs, m.STRINGER_L, 0, m.STRINGER_L, m.STRINGER_W, 4, str(m.STRINGER_W))
    y = para(x, y0 - 11, w, f"Onderkant langs de lange zaagkant van het stuk. Tanden: optrede {round(m.RISE)}, treden {TREADS} diep. "
             f"Bij de binnenhoeken blijft ca. {round(m.ST_CORNER)} mm hout over. Donker: versterkingsstrook {m.STRIP_L} x {m.STRIP_W} op de rechterboom. "
             f"Getekend is de rechterboom, met de lip van {m.TAB_Y1 - m.TAB_Y0} breed aan de bovenkant; bij de linkerboom zaag je de lip weg. "
             "Teken de tanden af volgens detail 6 (blad T10c). Boor in elke binnenhoek een gat Ø6 tegen scheuren en zaag daarnaartoe.", 7)

    y = para(x, y - 6, w, "Betonplex-stroken op maat: afkorten (afkortzaag) en smal rippen (tafelzaag)", 8.5, True, ACC) - 1
    for t in s_.home:
        y = para(x, y, w, "-  " + t, 7)
    y = para(x, y - 2, w, "De bouwmarkt zaagt de plaat in stroken volgens Kattenchalet_zaagplannen_bouwmarkt.pdf; de rest gebeurt thuis, zoals hierboven. "
             "Schrijf op elk stuk de naam. Bewaar de restplaat en de grotere reststroken droog en vlak; de kleine stukjes zijn bruikbaar als klos of vulstuk.", 7)


def flap_page(sh):
    """Kattenluik in wand E: aanzichten en doorsneden."""
    box = lambda x, y, w, h: (x - 0.6, y - 0.6, x + w + 0.6, y + h + 0.6)
    sh.new("Kattenluik in de scheidingswand", "1:2,5 en 1:5", [
        ("Kattenluik: aanzicht veranda, horizontale doorsnede", [box(14, 150, 194, 134), box(14, 28, 180, 116)]),
        ("Kattenluik: aanzicht trapkamer, verticale doorsnede", [box(212, 150, 194, 134), box(198, 28, 92, 116)]),
        ("Kattenluik: plaatsen", [box(294, 28, 112, 116)])])
    c = sh.c
    ply, beam, pir, floor_ = FILL[m.MAT["LP9"]], FILL[m.MAT["B69"]], FILL[m.MAT["PIR"]], FILL[m.MAT["BP12"]]
    frame, leaf, mesh, dbl = C("#dfe6ea"), C("#b8c6ce"), C("#d0d4d6"), C("#b08458")
    Z0 = m.Z_DECK
    fz0, fz1 = m.FLAP_Z, m.FLAP_Z + m.FLAP_H
    fc = (m.FLAP_Y0 + m.FLAP_Y1) / 2
    fr0, fr1 = fc - m.FLAP_FW / 2, fc + m.FLAP_FW / 2
    frz0, frz1 = (fz0 + fz1) / 2 - m.FLAP_FH / 2, (fz0 + fz1) / 2 + m.FLAP_FH / 2
    vy0, vy1, vz0, vz1 = m.VENT_E[0], m.VENT_E[1], m.VENT_E[2] - Z0, m.VENT_E[3] - Z0
    H, SS, CH = m.ROOM_H, m.S, m.CAT_H
    studs = [m.CAT_Y0 - SS, m.CAT_Y1]
    PX1, PL = m.PART_X1, m.PLY

    def dashed(view, u0, u1, v0, v1, col=INK, lw=0.3):
        c.setDash(2, 1.5)
        rect(view, u0, u1, v0, v1, None, stroke=col, lw=lw)
        c.setDash()

    # 1 aanzicht vanuit de veranda: voorkant links
    detail_box(c, 14, 150, 194, 134, "1  Aanzicht vanuit de veranda (1:5)")
    v = View(c, 20 - m.CLAD / 5, 170, 5)
    rect(v, m.CLAD, m.IN_Y1, 0, H, ply)
    for p in m.parts:   # regelwerk van wand E, zoals in het model (onderregel onderbroken bij de doorgang)
        if p.group.startswith("E") and p.mat == m.MAT["B69"]:
            dashed(v, p.box[2], p.box[3], p.box[4] - Z0, p.box[5] - Z0)
    rect(v, vy0, vy1, vz0, vz1, mesh)
    rect(v, fr0, fr1, frz0, frz1, frame, lw=0.5)
    rect(v, m.FLAP_Y0, m.FLAP_Y1, fz0, fz1, leaf)
    rect(v, m.CLAD - 15, m.IN_Y1 + 15, -6, 0, floor_)
    dim(v, m.FLAP_Y0, 0, m.FLAP_Y1, 0, -4.5, str(m.FLAP_W), 5.5)
    dim(v, m.FLAP_Y1, 0, m.IN_Y1, 0, -4.5, size=5.5)
    dim(v, m.CLAD, 0, m.IN_Y1, 0, -9, f"{m.IN_Y1 - m.CLAD} plaat", 5.5)
    dim(v, fr0, frz1, fr1, frz1, 2.5, f"frame {m.FLAP_FW}", 5)
    for a, b in ((0, vz0), (vz0, vz1), (vz1, fz0), (fz0, fz1)):
        dim(v, m.IN_Y1, a, m.IN_Y1, b, 3, size=5)
    dim(v, m.IN_Y1, 0, m.IN_Y1, CH, 10, f"latei {CH}", 5.3)
    tx = 172
    leader(v, fc, fz0 + 40, tx, 262, "Uitsparing: plaat +\nversterking, flap")
    leader(v, fr0 + 4, frz0 + 10, tx, 250, f"Buitenframe\n{m.FLAP_FW} x {m.FLAP_FH}")
    leader(v, (vy0 + vy1) / 2, vz1 - 15, tx, 238, f"Luchtinlaat {m.VENT_W} x {m.VENT_H},\nmidden onder het luik")
    leader(v, m.F1 + 22, 350, tx, 226, "Stippel: regelwerk\nachter de plaat")
    label(c, 20, 153, "Voorkant chalet links, achterwand rechts. Maten vanaf de achterkant van de plaat en vanaf de vloer.", 6)

    # 2 aanzicht vanuit de trapkamer: achterwand links
    detail_box(c, 212, 150, 194, 134, "2  Aanzicht vanuit de trapkamer (1:5)")
    v = View(c, 222 + m.IN_Y1 / 5, 170, 5, flip=True)
    rect(v, m.IN_Y0, m.IN_Y1, 0, H, ply)
    rect(v, m.CAT_Y0, m.CAT_Y1, 0, CH, dbl)
    rect(v, m.FLAP_Y0, m.FLAP_Y1, fz0, fz1, leaf)
    rect(v, vy0, vy1, vz0, vz1, mesh)
    rect(v, m.IN_Y0 - 15, m.IN_Y1 + 15, -6, 0, floor_)
    dim(v, m.CAT_Y0, 0, m.CAT_Y1, 0, -4.5, str(m.CAT_Y1 - m.CAT_Y0), 5.5)
    dim(v, m.CAT_Y1, 0, m.IN_Y1, 0, -4.5, size=5.5)
    dim(v, m.IN_Y0, 0, m.IN_Y1, 0, -9, f"{m.IN_Y1 - m.IN_Y0} plaat", 5.5)
    dim(v, m.CAT_Y0, 0, m.CAT_Y0, CH, 3, f"doorgang {CH}", 5.3)
    tx = 352
    leader(v, (m.CAT_Y0 + m.CAT_Y1) / 2, 25, tx, 262, "Doorgang open: je ziet\nde versterking en de\nflap van achteren")
    leader(v, (vy0 + vy1) / 2, vz1 - 15, tx, 244, f"Luchtinlaat {m.VENT_W} x {m.VENT_H}\n(door de open doorgang)")
    label(c, 222, 153, "Achterwand links, voorkant (raam) rechts. Geen binnenframe: de flap draait vrij de doorgang in.", 6)

    # 3 horizontale doorsnede door het luik, van boven: veranda boven
    detail_box(c, 14, 28, 180, 116, "3  Horizontale doorsnede door het luik, van boven (1:2,5)")
    sc = 2.5
    ya, yb = m.CAT_Y0 - SS - 25, m.IN_Y1 + 9
    v = View(c, 20 - ya / sc, 70 - m.ROOM_X1 / sc, sc)
    rect(v, ya, studs[0], m.PART_X0, PX1, pir)
    for y in studs:
        rect(v, y, y + SS, m.PART_X0, PX1, beam)
    rect(v, ya, m.CAT_Y0, m.ROOM_X1, m.PART_X0, ply)
    rect(v, m.CAT_Y1, m.IN_Y1, m.ROOM_X1, m.PART_X0, ply)
    rect(v, m.IN_Y1, yb, m.ROOM_X1 - 12, PX1 + PL + 12, ply)
    rect(v, ya, m.FLAP_Y0, PX1, PX1 + PL, ply)
    rect(v, m.FLAP_Y1, m.IN_Y1, PX1, PX1 + PL, ply)
    rect(v, m.CAT_Y0, m.FLAP_Y0, PX1 - PL, PX1, dbl)
    rect(v, m.FLAP_Y1, m.CAT_Y1, PX1 - PL, PX1, dbl)
    rect(v, fr0, fr1, PX1 + PL, PX1 + PL + 8, frame, lw=0.5)
    rect(v, m.FLAP_Y0, m.FLAP_Y0 + 3, PX1 - PL - 6, PX1 + PL, frame)
    rect(v, m.FLAP_Y1 - 3, m.FLAP_Y1, PX1 - PL - 6, PX1 + PL, frame)
    rect(v, m.FLAP_Y0 + 3, m.FLAP_Y1 - 3, PX1 - 2, PX1 + 2, leaf)
    dim(v, m.CAT_Y0, m.ROOM_X1, m.CAT_Y1, m.ROOM_X1, -4, f"{m.CAT_Y1 - m.CAT_Y0} tussen de stijlen", 5.5)
    dim(v, m.FLAP_Y0, PX1 + PL + 8, m.FLAP_Y1, PX1 + PL + 8, 3.5, f"uitsparing {m.FLAP_W}", 5.3)
    dim(v, fr0, PX1 + PL + 8, fr1, PX1 + PL + 8, 9, f"frame {m.FLAP_FW}", 5.3)
    dim(v, ya, m.ROOM_X1, ya, PX1 + PL, -3, str(PX1 + PL - m.ROOM_X1), 5.3)
    x_, y_ = v.p(ya, PX1 + PL + 30)
    label(c, x_ / mm, y_ / mm, "veranda", 7, True)
    x_, y_ = v.p(ya, m.ROOM_X1 - 32)
    label(c, x_ / mm, y_ / mm, "trapkamer", 7, True)
    tx = 150
    leader(v, m.CAT_Y0 + 10, PX1 - 5, tx, 128, "Versterking 9 (rest),\ngelijmd tussen stijlen")
    leader(v, ya + 15, PX1 + 5, tx, 116, "Plaat verandazijde 9")
    leader(v, fr1 - 6, PX1 + PL + 4, tx, 108, "Buitenframe, 4 RVS-\nschroeven max. 16 mm")
    leader(v, fc + 30, PX1, tx, 96, "Flap en tunnel\n(schematisch)")
    leader(v, m.CAT_Y1 + 22, m.PART_X0 + 40, tx, 84, "Stijl 44 x 69")
    leader(v, m.CAT_Y1 + 30, m.ROOM_X1 + 4, tx, 74, "Plaat trapzijde 9,\ndoorgang open")
    leader(v, yb - 4, m.ROOM_X1, tx, 60, "Plaat achterwand")
    label(c, 18, 31, "Samen 18 mm plaat waar het luik zit; de wand is 87 mm dik.", 6)

    # 4 verticale doorsnede door het luik
    detail_box(c, 198, 28, 92, 116, "4  Verticale doorsnede (1:5)")
    xa = m.ROOM_X1 - 40
    v = View(c, 216 - xa / 5, 34, 5)
    rect(v, xa, PX1 + 50, -10, 0, floor_)
    rect(v, m.ROOM_X1, m.PART_X0, CH, H, ply)
    rect(v, m.PART_X0, PX1, CH, CH + SS, beam)
    rect(v, m.PART_X0, PX1, CH + SS, H - SS, pir)
    rect(v, m.PART_X0, PX1, H - SS, H, beam)
    for a, b in ((0, vz0), (vz1, fz0), (fz1, H)):
        rect(v, PX1, PX1 + PL, a, b, ply)
    for a, b in ((0, vz0), (vz1, fz0), (fz1, CH)):
        rect(v, PX1 - PL, PX1, a, b, dbl)
    rect(v, PX1 + PL, PX1 + PL + 8, frz0, frz1, frame, lw=0.5)
    rect(v, PX1 - 2, PX1 + 2, fz0 + 5, fz1 - 5, leaf)
    dashed(v, PX1 + PL, PX1 + PL + 2, vz0, vz1, ACC, 0.5)
    for a, b in ((0, vz0), (vz0, vz1), (vz1, fz0), (fz0, fz1)):
        dim(v, PX1 + 50, a, PX1 + 50, b, 3, size=5)
    dim(v, xa, 0, xa, CH, -3, str(CH), 5.3)
    dim(v, xa, 0, xa, H, -8, str(H), 5.3)
    label(c, 201, 30.5, "trapkamer", 6.5, True)
    label(c, 258, 30.5, "veranda", 6.5, True)
    leader(v, PX1 + PL + 2, (vz0 + vz1) / 2, 262, 60, "inlaat met gaas")
    leader(v, (m.PART_X0 + PX1) / 2, CH + 120, 262, 120, "PIR boven de latei")

    # notities
    detail_box(c, 294, 28, 112, 116, "Plaatsen")
    notes = [
        f"Luik: PetSafe 700 S. Uitsparing {m.FLAP_W} breed x {m.FLAP_H} hoog, frame",
        f"{m.FLAP_FW} x {m.FLAP_FH} (volgens bol; eerst nameten op het luik).",
        f"Hoogte: onderkant uitsparing {m.FLAP_Z} boven de vloer, onderrand frame",
        f"ca. {round(frz0)}: ongeveer buikhoogte van een volwassen kat. Meet je",
        "eigen kat en pas zo nodig aan; de latei zit 5 mm boven de uitsparing",
        f"(nu op {CH}) en gaat mee. De luchtinlaat eronder moet blijven passen.",
        "Dubbele plaat: ja. 9 mm Lightply (zachte falcata) houdt kleine schroeven slecht,",
        "en de kat duwt bij elke doorgang tegen het luik. Lijm de versterking",
        f"({m.CAT_Y1 - m.CAT_Y0} x {CH}, rest Lightply 9) achter de verandaplaat, tussen",
        "de stijlen en onder de latei, en schroef hem in de stijlen. Samen 18 mm.",
        "Zaag de uitsparing pas als de lijm hard is, door beide platen",
        "tegelijk: dan liggen de randen gelijk. Randen afronden en lakken.",
        "Geen binnenframe: schroef het buitenframe met 4 RVS-houtschroeven",
        "van max. 16 mm in plaat en versterking; de punt mag er niet uit.",
        "Of het afsluitpaneel zonder binnenframe werkt: controleren.",
        "Plaats het luik als wand E nog plat ligt (stap 6). Aan de",
        "trapzijde blijft de doorgang open, zodat de flap vrij draait.",
        f"Luchtinlaat {m.VENT_W} x {m.VENT_H}, {m.VENT_Z} boven de vloer, onder het luik: koude",
        "lucht komt laag binnen en de warme lucht blijft bovenin de trapkamer.",
        "Alleen in verandaplaat en versterking, RVS-gaas aan de verandakant.",
        "Geen opening boven de latei: daar komt PIR.",
    ]
    for i, t_ in enumerate(notes):
        label(c, 297, 135 - i * 5.0, t_, 6)

# --- Tekst -------------------------------------------------------------------
ST = dict(
    h1=ParagraphStyle("h1", fontName="DB", fontSize=15, leading=19, spaceAfter=7, textColor=INK),
    h2=ParagraphStyle("h2", fontName="DB", fontSize=10.5, leading=14, spaceBefore=9, spaceAfter=4, textColor=ACC),
    p=ParagraphStyle("p", fontName="D", fontSize=8.8, leading=12.4, spaceAfter=4, textColor=INK, alignment=TA_LEFT),
    s=ParagraphStyle("s", fontName="D", fontSize=7.4, leading=9.7, textColor=INK),
    sb=ParagraphStyle("sb", fontName="DB", fontSize=7.4, leading=9.7, textColor=colors.white),
    b=ParagraphStyle("b", fontName="D", fontSize=8.8, leading=12.2, leftIndent=11, bulletIndent=1, spaceAfter=2.2, textColor=INK),
    title=ParagraphStyle("t", fontName="DB", fontSize=24, leading=28, spaceAfter=4, textColor=INK),
    sub=ParagraphStyle("su", fontName="D", fontSize=10.5, leading=14, spaceAfter=10, textColor=ACC),
)


def P(t, s="p"):
    return Paragraph(t, ST[s])


def B(t):
    return Paragraph(t, ST["b"], bulletText="•")


def T(data, widths, head=True, extra=None):
    rows = []
    for i, r in enumerate(data):
        rows.append([Paragraph(str(x), ST["sb" if (head and i == 0) else "s"]) for x in r])
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, C("#c5ccd0")),
          ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), INK))
    t.setStyle(TableStyle(st + (extra or [])))
    return t


PART = {"naam": "Deel 1"}


def footer(c, doc):
    c.setFont("D", 7)
    c.setFillColor(C("#667078"))
    c.drawString(16 * mm, 9 * mm, f"Kattenchalet bouwplan  |  {REV}, {DATE}")
    c.drawRightString((A4[0] / mm - 16) * mm, 9 * mm, f"{PART['naam']}, pagina {doc.page}")


# Inkooplijst: (omschrijving, aantal, eenheid, prijs of None, herkomst, status)
def split_art(name):
    """Haalt het Hornbach-artikelnummer uit de omschrijving."""
    mt = re.search(r"\s*\((?:([^()]*?),\s*)?art\.\s*(\d+)\)", name)
    if not mt:
        return name, ""
    extra = f" ({mt.group(1)})" if mt.group(1) else ""
    return name[:mt.start()] + extra + name[mt.end():], mt.group(2)


def purchase():
    n = {k: len(v) for k, v in NEST.items()}
    H = "Hornbach, 6-11-2026"
    C_ = "Prijs nog opvragen"
    rows = [
        ("Hout en plaat", None, None, None, None, None),
        ("KONSTA vuren 44x44, ca. 2400 (art. 5185884)", n["R44"] + 1, "st", 3.55, H, "Gecontroleerd"),
        ("KONSTA vuren 44x69, ca. 2400 (art. 5185888)", n["B69"] + 1, "st", 4.30, H, "Gecontroleerd"),
        ("Geïmpregneerde balk 44-45 x 69-70, min. 2400", n["I69"], "st", None, C_, "Niet gevonden als artikel; in vestiging vragen"),
        ("Geïmpregneerde paal 69x69, ca. 2700 (Elephant, art. 5506541)", n["P69"], "st", None, C_, "Artikel gevonden, prijs nog controleren"),
        ("Spouwlat 22x44 geïmpregneerd of Douglas, ca. 2400", n["LAT"], "st", None, C_, "Maat controleren; alternatief: 44x44 halveren (spouw 20)"),
        ("LIGHTPLY Multiplex ongegrond 244x122 cm, 9 mm (art. 12575686)", n["LP9"], "pl", 22.49, H, "Gecontroleerd 10-11-2026; falcata, binnen en beschut buiten, FSC. Geen reserve. Lijmklasse en formaldehydeklasse niet gevonden"),
        ("Betonplex Acacia 2500x1250x12 (art. 12628592)", n["BP12"], "pl", 57.49, H, "Gecontroleerd; vloeren, trap en overstek"),
        ("Constructieplaat OSB-III recht 2440x1220x11 (art. 10222931)", n["OSB"], "pl", 18.55, H, "Gecontroleerd; lange kant dwars op de sporen"),
        ("Douglas 18x145x3000 tand-en-groef (art. 10537457), gevel + kader", n["DG"] + n["DK"] + 2, "st", 11.59, H, "Gecontroleerd; werkende breedte ca. 135"),
        ("Isolatie en folie", None, None, None, None, None),
        ("IKO PIR 70 Rd 3,15, pak 7 st = 5,04 m² (art. 10368509)", 1, "pak", 88.64, H, f"{n['PIR']} platen nodig. Alu-cachering in vestiging bevestigen"),
        ("Dampopen waterkerende gevelfolie, Sd ≤ 0,1 m, ca. 10 m²", 1, "rol/stuk", None, C_, "Niet gevonden bij Hornbach; vestiging vragen of bouwmarkt"),
        ("Alu-tape PIR, 50 mm", 1, "rol", None, C_, ""),
        ("RVS 304 gaas, 20 mazen, ca. 1 mm, 40 x 200 cm (Amazon B0DL5P11F2)", 1, "rol", 18.99, "Eigen invoer, Amazon", "Spouw en ventilatiebuis. Maaswijdte bij ontvangst nameten"),
                ("Dak", None, None, None, None, None),
        ("Premiumfol EPDM 1,2 mm, breedte 2,8 m, per m (art. 10469549)", 1.5, "m", 38.92, H, "Gecontroleerd; maatwerk: geen retour. Reststrook is de goot onder de ramen"),
        ("EPDM-lijm en kit (Premiumfol/Berdal)", 1, "set", None, C_, "Spray 6-8 m² per bus volgens datablad"),
        ("SOLOTRIM daktrim alu 60x55, 2500 (art. 5581276)", 3, "st", 49.95, H, "Gecontroleerd; schroeven en neopreen ringen los"),
        ("Hoekstukken daktrim", 4, "st", None, C_, ""),
        ("Dakgoot 1,5 m met afvoer en hangers", 1, "set", None, C_, "Afvoer weg van de schutting, naar een plek waar het water weg kan"),
        ("Ramen", None, None, None, None, None),
        ("Kelderraam 100x50 draai/kiep links RAL9016 (art. 12074105)", 1, "st", 94.50, H, "Gecontroleerd; geen greep meegeleverd"),
        ("ARON Basic+ 50x50 DK links (art. 12331530)", 1, "st", 109.00, H, "Gecontroleerd; geen greep meegeleverd"),
        ("Afsluitbare raamgreep", 2, "st", None, C_, "Zit buiten, dus afsluitbaar. Passing bij aankoop controleren"),
        ("Kiepbeveiliging voor katten, of kiepstand blokkeren", 2, "st", None, C_, "Zie veiligheid"),
        ("GAH.ALBERTS Lekdorpelprofiel 34x17 alu blank 200 cm (art. 10295993)", 1, "st", 8.75, H, "Gecontroleerd; 1070 + 600 uit 1 stuk. Vorm in de winkel controleren"),
        ("Kit voor buitenaansluitingen en glaslatten, buitenkwaliteit", 1, "set", None, C_, "Geschikt voor kunststof"),
        ("5 RVS consoles voor regenluifel", 5, "st", None, C_, "Luifel over de hele breedte; bovenkant met EPDM-rest en druiprand"),
        ("Fundering", None, None, None, None, None),
        ("HETTICH Stelvoet M10x75 mm Ø 75 mm RVS (art. 4297033)", 6, "st", 4.95, "Hornbach, 12-11-2026", "Los op de tegel, EPDM-rest eronder. 50 kg opgegeven (meubel). Verstelbereik meten"),
        ("DRESSELHAUS Inslagmoer 10x13 mm galv. verzinkt, 4 stuks (art. 3857241)", 2, "pak", None, C_, "In de kopse kant van de poot; vet en kit tegen roest"),
        ("RVS zeskantmoer M10 (contramoer)", 6, "st", None, C_, "Los uit de bak"),
        ("Spanband met ratel, ca. 6 m", 1, "st", None, C_, "Tijdelijk bij code oranje wind, tot het chalet aan de schutting vast staat"),
        ("Bevestiging aan de schutting: 2 afstandhouders 44x69 plus RVS hoekankers en schroeven", 1, "set", None, C_, "Uitwerken na het meten van de palen"),
        ("Verwarming en elektra", None, None, None, None, None),
        ("Buisverwarming 120 W (of 2x60 W) met maximaalthermostaat, IP44", 1, "st", None, C_, "Geschikt model niet bij Hornbach gevonden"),
        ("Digitale thermostaat, kast IP65, mantelbuis, voeler", 1, "set", None, C_, "Installateur kiest onderdelen"),
        ("Stalen beschermkap voor verwarming (geperforeerd)", 1, "st", None, C_, "Op maat, afhankelijk van model"),
        ("Installateur buitenaansluiting met aardlek", 1, "post", None, "Offerte", "Afhankelijk van afstand tot meterkast"),
        ("Ventilatie en meting", None, None, None, None, None),
        ("PVC-buis Ø100 (eigen restant)", 1, "st", None, "Eigen voorraad", "Ca. 150 mm nodig; buitenmaat meten"),
        ("ROTHEIGNER Ventilatierooster afsluitbaar Ø100-125-150, binnen (art. 4152757)", 1, "st", 4.05, H, "Traploos regelbaar niet vermeld: in de winkel bekijken"),
        ("ROTHEIGNER Ventilatierooster rond wit Ø100, buiten (art. 8610839)", 1, "st", 2.45, H, "Past op de buis? Meten. Insectenwering erachter"),
        ("Hygrometer met geheugen", 1, "st", None, C_, ""),
        ("Afwerking en bevestiging", None, None, None, None, None),
        ("Remmers HK-Lazuur (gevel, houtnerf zichtbaar), 2,5 l", 1, "blik", None, C_, "Hoeveelheid volgens verbruik op blik"),
        ("Jotun Demidekk donker (kader), 1 l, plus grondverf", 1, "set", None, C_, ""),
        ("TENCO Bootlak blank mat 750 ml (art. 10728553)", 2, "st", 17.95, H, "Alle binnenwanden, minstens 3 lagen, ca. 1,1 l. Binnen en buiten, weer- en uv-bestendig. Oplosmiddel: goed laten luchten"),
        ("Waterdichte bouwlijm PU/D4; randsealer voor plaatmateriaal", 1, "set", None, C_, "Randen afronden en sealen: daar trekt de plaat vocht"),
        ("RVS schroeven 3,5x25, 100 stuks", 4, "pak", None, C_, "Binnenplaten en lekdorpel; ruwe schatting"),
        ("Hoekankers met passende schroeven, verzinkt of RVS", 14, "st", None, C_, "6 poten, 8 voorstijlen boven en onder; schatting"),
        ("Kozijnschroeven of raamankers", 1, "set", None, C_, "Lengte: kozijn + voeg 9 + min. 60 in de stijl. Kozijn eerst meten"),
        ("Sisal of rubbermat voor treden; mat voor veranda", 1, "set", None, C_, ""),
    ]
    return rows


def write_text(path_a, path_b):
    r = R
    A = []
    A += [P("Kattenchalet", "title"), P("Bouwplan", "sub")]
    A += [P("Een modern houten buitenverblijf voor een kat die ook 's nachts buiten blijft. Twee verdiepingen: boven een geïsoleerde "
            "bovenkamer, beneden een trapkamer en een veranda met open voorkant. Toegang voor het onderhoud "
            "via de ramen, die vanaf buiten opengaan. Het chalet staat op 6 stelvoeten los op het terras, met de rug naar de schutting, en wordt later aan de schutting vastgezet.")]
    A += [P("Hoofdmaten", "h2")]
    A += [T([["Onderdeel", "Maat (mm)"],
             ["Buitenmaat", f"{m.W} x {m.D}, hoogte {round(m.Z_TOP)}; dak {m.ROOF_W} x {m.ROOF_L}"],
             ["Bovenkamer", f"{m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}, raam 1000 x 500"],
             ["Trapkamer", f"{m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}, raam 500 x 500, trap langs de linkerwand"],
             ["Veranda", f"{m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H}, kattenluik naar de trapkamer"],
             ["Gewicht", f"ongeveer {round(R['mass'])} kg"],
             ], [33, 145])]
    A += [P("Inhoud", "h2")]
    A += [T([["Blad", "Onderwerp"],
             ["T1", "Overzicht 3D"], ["T2", "Aanzichten voor en achter"], ["T3", "Aanzichten zijkanten"],
             ["T4, T5", "Doorsneden"], ["T6", "Plattegronden, vloerframe en tussenvloer"], ["T7", "Plafond, dak en spoor"],
             ["T8, T9", "Wandframes beneden en boven"], ["T10", "Details"], ["T11, T12", "Zaagplannen platen, balken en latten"],
             ["T13", "Montagevolgorde"], ["T14", "Kattenluik in de scheidingswand"], ["T15", "Trap en betonplex thuis zagen"],
             ["Daarna", "Zaaglijst, stappenplan en onderhoud"],
             ], [33, 145])]
    A += [P("Zo lees je dit plan", "h2")]
    for t in (
        "Maten in mm. Hoogtes gemeten vanaf de hoogste terrastegel. Links en rechts zijn altijd gezien vanaf de voorkant, ook als je achter het chalet staat.",
        "Meet niet van de tekening, maar gebruik de maatgetallen. Zaag sparingen pas als de ramen binnen zijn en ingemeten.",
        "Bladen met een letter (T2a, T2b) horen bij elkaar; een verwijzing naar blad T2 bedoelt ze allebei.",
        "Apart: het Excel-bestand Kattenchalet_zaag_en_inkooplijst.xlsx (zaaglijst, inkoop, latten op lengte, platen op maat) en "
        "Kattenchalet_zaagplannen_bouwmarkt.pdf (de zaagopdracht per plaat voor de bouwmarkt).",
    ):
        A.append(B(t))

    doc = SimpleDocTemplate(path_a, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title="Kattenchalet bouwplan", author="Claude Code")
    PART["naam"] = "Titel en inhoud"
    doc.build(A, onFirstPage=footer, onLaterPages=footer)

    Bd = []
    Bd += [P("Zaaglijst", "h1"), P(f"Maten in mm, L x B x D. Bouwdelen komen overeen met de tekeningen. Bij gevelplanken is B de werkende breedte 135 (plank zelf 145); die planken hoeven dus niet gerift, behalve de bovenste rij van {m.TOP_STRIP} mm. Deze lijst staat ook, sorteerbaar, in het Excel-bestand.")]
    g_prev = None
    rows = [["Onderdeel", "Materiaal", "st", "L", "B", "D", "Opmerking"]]
    for r_ in ROWS:
        if r_["group"] != g_prev:
            rows.append([f"<b>{r_['group']}</b>", "", "", "", "", "", ""])
            g_prev = r_["group"]
        d = r_["dims"]
        rows.append([r_["name"], r_["mat"], r_["qty"], d[0], d[1], d[2], r_["note"]])
    Bd += [T(rows, [48, 42, 8, 11, 11, 8, 50])]
    Bd += [PageBreak(), P("Stappenplan", "h1")]
    # maten voor het stappenplan, uit het model
    FR_DIAG = round(math.hypot(m.XR1 - m.F0, m.YB1 - m.F0))
    LEG_DIAG = round(math.hypot(m.LEG_X[2][0] - m.LEG_X[0][0], LEG_DY))
    BALK = m.YR - m.F1
    PLATE_H = m.ROOM_H - 4
    E_X = m.PART_X0 - m.F0
    HOLE_L, HOLE_V = m.HOLE_X0 - m.F0, m.HOLE_Y0 - m.F0
    CAT_B = m.IN_Y1 - m.CAT_Y1
    VENT_R, VENT_Z = m.XR1 - m.VENT["x"], m.VENT["z"] - m.Z_UP
    OV_F, OV_B, OV_S = m.F0 - m.RAFT_Y0, m.RAFT_Y1 - m.YB1, m.F0 - m.SIDE_RAFT[0]
    KLOS = m.CEIL_X[0] - (m.SIDE_RAFT[0] + m.S)
    steps = [
        ("Voorbereiding", [
            "Lees eerst de tekeningen T1-T15. Links en rechts zijn in dit hele plan gezien vanaf de voorkant, ook als je achter het chalet staat. Hoogtes zijn gemeten vanaf de bovenkant van de hoogste terrastegel onder het chalet.",
            "Bestel eerst de ramen en meet ze (stap 2). Bestel de rest pas daarna en controleer de gemarkeerde artikelen bij Hornbach.",
            "Tot het dak in stap 9 dicht is, gaat er elke avond en bij elke bui een afdekzeil over het werk. PIR, gelakte platen en OSB mogen niet nat worden.",
        ]),
        ("Ramen inmeten", [
            f"Meet beide kozijnen na ontvangst op drie plekken in breedte en hoogte, en meet ook de diepte (het plan rekent met {m.WIN_D}). Is een maat anders dan 1000 x 500 of 500 x 500, pas dan eerst het model aan: breedte, kamerhoogte en diepte van het hele chalet hangen hiervan af.",
            "Bekijk de scharnierzijde, de glaslatten en de afwateringssleuven. Monteer de afsluitbare greep en de kiepbeveiliging. Test de kiep- en draaistand met het raam omgekeerd op de werkbank.",
        ]),
        ("Zagen en voorbehandelen", [
            f"Zaag de balken en regels volgens blad T12 en schrijf op elk stuk het bouwdeel en de naam. Zaag de platen volgens blad T11; de betonplex volgt jouw indeling, met maten uit het model. Wat je thuis zaagt (trapbomen en stroken op maat) staat op blad T15. Geef de bouwmarkt per plaat de zaagopdracht uit Kattenchalet_zaagplannen_bouwmarkt.pdf: daar staan alleen hun sneden, genummerd en met maat; PIR snijd je zelf. Laat grote platen in de vestiging voorzagen. Zaag alle wandplaten {PLATE_H} hoog in plaats van {m.ROOM_H}: ze komen 4 mm boven de vloer, met een kitvoeg, zodat ze geen water optrekken.",
            f"Sparingen in wand E, gemeten vanaf de achterkant van de plaat (de verandaplaat is aan de voorkant langer). Plaat trapzijde: doorgang {m.CAT_Y1 - m.CAT_Y0} breed en {m.CAT_H} hoog vanaf de vloer, {CAT_B} mm uit de achterkant. Verandaplaat: geen doorgang, maar de uitsparing voor het kattenluik, {m.FLAP_W} breed en {m.FLAP_H} hoog, {m.IN_Y1 - m.FLAP_Y1} mm uit de achterkant, met de onderkant {m.FLAP_Z} mm boven de vloer. Meet de zaagmaat eerst na op het luik zelf. In de verandaplaat onder het luik ook een luchtinlaat van {m.VENT_W} x {m.VENT_H}, {m.IN_Y1 - m.VENT_E[1]} mm uit de achterkant, {m.VENT_E[2] - m.Z_DECK}-{m.VENT_E[3] - m.Z_DECK} mm boven de vloer. Ook die zaag je pas na het lijmen, door beide platen. Zaag uit de rest ook de versterkingsplaat van {m.CAT_Y1 - m.CAT_Y0} x {m.CAT_H}. Zaag de uitsparing voor het luik daarin pas na het lijmen (blad T14). Trapgat in de onderplaat en de vloerplaat van de tussenvloer: {HOLE} mm, {HOLE_L} mm uit de linkerrand en {HOLE_V} mm uit de voorrand. Teken elke sparing af met de plaat in de stand waarin hij straks zit. De onderplaat ligt met de gelakte kant naar beneden: teken je hem af met de lakzijde boven, dan wisselen links en rechts.",
            f"Hoeklatten: zaag op de tafelzaag eerst tong en groef van de Douglas-plank, dan 4 stroken 58 x 18 en 4 stroken 40 x 18, lang {m.CLAD_Z1-m.CLAD_Z0}. Zet per hoek de smalle kant van de 40-strook tegen de achterkant van de 58-strook, zodat een L van 58 x 58 ontstaat. Lijm met PU-lijm, schroef RVS 4 x 40 om de 250 mm, voorgeboord, en klem tot de lijm hard is. Rif de overige stroken (boeiboorden, kader, band, voorrand, regenluifel en de bovenste gevelrij van {m.TOP_STRIP}) volgens het Excel-tabblad 'Latten op lengte'. Meet eerst een plank: is die zonder tong en groef smaller dan 145, dan klopt die indeling niet meer.",
            "Beits alles vóór de montage, binnen en niet onder +8 °C. Gevelplanken, kader, band en voorrand krijgen eerst grondverf en dan grenen beits. Hoeklatten, boeiboorden en regenluifel krijgen antraciet, 3 lagen rondom. Beits 2 lagen, op plekken die veel weer vangen 3, met 8 uur tussen de lagen. Kopse kanten en gerifte randen krijgen kopshoutverzegeling. Maak eerst een proefstuk voor de kleur. Behandel later elke zaagsnede op de bouw na.",
            "Laat de Lightply 48 uur acclimatiseren, binnenshuis en vrij van de grond. Schuur de zichtzijde en lak die met TENCO Bootlak blank mat, minstens 3 lagen en 24 uur per laag. De achterkant wordt gelijmd en blijft kaal. Bij de onderplaat van de tussenvloer en de plafondplaat is de onderkant de zichtzijde. Rond de randen af en seal ze. Sla hout droog en plat op.",
        ]),
        ("Plek en stelvoeten", [
            f"Kies de plek: achterwand minstens 250 mm van de schutting (dakoverstek 100 mm plus goot). De poten staan {LEG_DX[0]} en {LEG_DX[1]} mm hart op hart in de breedte en {LEG_DY} mm in de diepte (blad T6). Elke voet (Ø{m.FOOT_D}) moet helemaal op één tegel staan, niet op een voeg: schuif het chalet zo nodig iets op. Bepaal met waterpas en rechte lat welke van de 6 voetplekken het hoogst ligt: dat is hoogte 0. Meet ook hoeveel de laagste plek lager ligt.",
            f"Controleer de stelvoeten in de winkel: draad M10 aan de voet, minstens 60 mm vrij te stellen. Het plan rekent met de onderkant van de poot {m.Z_POST} mm boven hoogte 0. Ligt de laagste plek meer dan ca. 25 mm lager, dan is de draad te kort: maak de poten aan die kant langer.",
            f"Poten: zaag alle 6 op {m.Z_LEG - m.Z_POST} mm. Boor in het hart van elke kopse kant eerst een gat voor het busje van de inslagmoer, daarna Ø11 door tot 60 mm diep: daar verdwijnt de draad van de voet in. Verzegel de kopse kant en het gat. Vet de draad van de inslagmoer in, sla de moer erin en kit de rand rondom, zodat er geen water tussen hout en moer komt. Draai de contramoer en dan de voet in.",
            "De voeten staan los op de tegels, met een stukje rest-EPDM onder elke voet. Het chalet wordt na de bouw aan de schutting vastgezet (stap 15). Tot die tijd: let op weerwaarschuwingen voor wind en zet het chalet bij code oranje tijdelijk vast (stap 15).",
        ]),
        ("Vloerframe", [
            f"Bouw frame A plat: de langsbalken voor en achter ({m.XR1 - m.F0}) over de koppen van de {len(m.FLOOR_X)} dwarsbalken ({BALK}), met 2 constructieschroeven 5 x 80 per verbinding, voorgeboord. Controleer de diagonalen ({FR_DIAG} mm). Schroef de OSB-onderplaat met RVS 4 x 40 onder het frame, zonder kieren. De plaat komt uit één stuk uit de rest van de dakplaat, met uitsparingen van 68 x 68 rond de 6 poten. Seal alle randen en lak of beits de onderkant. Keer het frame om, leg PIR 70 in de vakken en tape de naden.",
            "Zet het frame op de poten met stelvoeten, op de plek uit stap 4. Stel de voeten af: in de breedte waterpas, in de diepte 5 mm aflopend naar voren. Elke voet moet dragen: druk op elke hoek en stel bij tot er geen voet meer los staat. Zet de contramoeren vast. Het hele chalet helt daardoor iets naar voren, dus zet wanden en ramen haaks op de vloer en niet op de waterpas in de diepte. Zet elke poot trekvast aan het frame met een hoekanker en constructieschroeven. Dicht de uitsparingen rond de poten af, zodat er geen kier voor muizen overblijft. Lijm en schroef de vloerplaat met RVS 4 x 40 en verzegel alle randen.",
        ]),
        ("Benedenwanden en trap", [
            f"Bouw de frames C, D, E en F volgens blad T8: de regels over de koppen van de stijlen, 2 schroeven 5 x 80 per verbinding, voorgeboord. Lijm en schroef de binnenplaat erop, met de gelakte kant naar de kamer en de onderrand 4 mm boven de onderkant van het frame. Gebruik RVS 3,5 x 25, voorgeboord, om de 100 mm en minstens 15 mm uit de rand. De plaat maakt het frame haaks, dus controleer de diagonalen voordat de lijm uithardt. Bij D en aan de trapzijde van E steekt de plaat 13 mm voor het frame uit, tot tegen het kozijn. In de open veranda lopen de platen door tot 18 mm achter de voorkant, tegen de kaderstijl en de afdekking van de wandkop: bij F 22 mm voorbij het frame, aan de verandazijde van E 66 mm. Zet die laatste plaat pas vast als raamstijl B staat, en schroef de voorrand in de raamstijl. Kattenluik volgens blad T14: lijm de versterkingsplaat achter de verandaplaat, tussen de stijlen van de doorgang. Zaag daarna de uitsparing door beide platen tegelijk. Schroef het buitenframe zonder binnenframe vast met korte RVS-schroeven, zolang de wand nog plat ligt. Plak RVS-gaas aan de verandakant over de luchtinlaat onder het luik. Leg nog geen PIR in de wanden.",
            f"Zet C op de vloer, gelijk met de achterrand, en schroef de onderregel om de 300 mm met 5 x 80 door de vloerplaat in het frame. Zet D en F gelijk met de zijkanten en E met het regelwerk op {E_X} mm uit de linkerrand van de vloer. F loopt door tot de voorrand; D en E beginnen 44 mm erachter, want daar komen de raamstijlen. Tussen de raamstijlen links en rechts komt straks het onderraam, met 1 mm speling per kant; meet dat na aan het echte raam. Schroef ze op de vloer en schroef vanuit het open vak 3 schroeven 5 x 80 door de achterste stijl en de achterplaat in de achterwand.",
            "Raamstijlen B: de 44 x 69 links voor, tegen de voorste stijl van D, en de 44 x 69 voor wand E. Zet ze nu alleen voorlopig vast, met één schroef schuin in de vloer. Ze dragen straks de cassette, maar de definitieve bevestiging volgt pas in stap 11, strak tegen het kozijn.",
            f"Trap. Zaag de trapbomen: teken de tanden af volgens detail 6 (optrede {round(m.RISE)}, treden {TREADS} diep, van onder naar boven; de onderste trede steekt 50 mm voorbij zijn tand, tot tegen de achterwand). Zaag aan de bovenkant van de rechterboom de lip mee uit ({m.TAB_Y1 - m.TAB_Y0} breed, tot {round(m.TAB_Z1 - m.Z_DECK)} boven de vloer); bij de linkerboom zaag je dat stuk weg. Zaag in de bovenste trede rechts een inkeping van {m.PLY_F} x {m.TAB_Y1 - m.TAB_Y0}, {m.TAB_Y0 - m.TREAD_AT[-1][0]} mm uit de voorkant, waar de lip doorheen gaat. Boor in elke binnenhoek een gat Ø6 tegen scheuren en zaag daarnaartoe, niet erlangs. Er blijft ca. {round(m.ST_CORNER)} mm hout over, dus zaag niet dieper dan de lijn. Schuur alles glad. Lijm de versterkingsstrook ({m.STRIP_L} x {m.STRIP_W}) met PU-lijm op de binnenkant van de rechterboom, langs de rechte onderkant, van de voet tot de bovenkant. Klem hem en schroef om de 10-15 cm met RVS 3,5 x 20; er mag geen punt uitsteken. Bekleed de treden nu met sisal of rubber, want later kom je er slecht bij. Lijm de treden met PU-lijm op de tanden en zet ze vast met RVS 3,5 x 25, voorgeboord, midden in de boomrand.",
            f"Zet de trap tegen de linkerwand, met de voet tegen de achterwand C en de bovenkant {m.ST_Y0 - m.IN_Y0} mm achter het kozijn: de trap mag het raam niet raken. De linkerboom wordt over zijn hele vlak tegen de wandplaat gelijmd. Zet de trap eerst droog op zijn plek en trek de omtrek van de linkerboom op de plaat af. Boor binnen die lijn, ca. 20 mm van de rand, om de ca. 150 mm een gaatje Ø3 door de plaat, zodat je de plek aan de buitenkant terugvindt. Schuur binnen de lijn de lak weg tot op kaal hout en schuur ook de gladde filmlaag op de buitenkant van de boom op: op lak en film hecht de lijm niet. Zet de boom met PU-lijm tegen de plaat. Wand D heeft maar twee stijlen, voor en achter. Schroef de boom met RVS 4 x 40 door de plaat in het hout erachter: bovenaan in de voorste stijl en de bovenregel, aan de voet in de achterste stijl en de onderregel. Druk de rest van de lijmnaad aan met RVS 3,5 x 16 van buitenaf: vanuit de open vakken van D door de gaatjes en de plaat in de boom. Niet langer dan 16 mm, anders komt de punt aan de katkant door de boom. Die schroeven mogen blijven zitten. Veeg uitgelopen lijm aan de katkant weg. Zet de voet van beide bomen schuin vast in de vloer. De lip van de rechterboom steekt boven de wanden uit; zet de rechterkant van die boom precies {m.ST_X1 - m.F0} mm uit de linkerrand van de vloer, want de lip komt straks strak naast de balk rechts van het trapgat. Maak schroefpunten aan de katkant nu onschadelijk. Na de tussenvloer is de trap niet meer uit te nemen.",
        ]),
        ("Tussenvloer", [
            f"Bouw cassette G volgens blad T6: de randen voor en achter over de koppen van de balken ({BALK}), 2 schroeven 5 x 80 per verbinding. Schroef de opvulstrook (44 x 69, op 25 mm gerift) tegen de linkerbalk en zet de raveelbalk tussen de opvulstrook en de balk rechts van het trapgat. Leg het frame ondersteboven. Lijm en schroef de onderplaat erop, met de gelakte kant naar beneden en het trapgat op zijn plek. Lijm de dagkanten (Lightply, 69 hoog) langs de linker- en voorkant van het trapgat.",
            "Zet de cassette, nog zonder vloerplaat, met twee personen op de benedenwanden, rondom gelijk met de buitenkant. Laat hem voorzichtig over de lip van de rechterboom zakken: die moet in het trapgat komen, tegen de balk rechts ervan. Schroef vanuit de open wandvakken om de 300 mm met 5 x 80 omhoog, door de bovenregels en de onderplaat in de randen en balken. Schroef daarna door het trapgat de lip met 2 RVS 4 x 40, voorgeboord, in die balk.",
            "Leg PIR 70 tussen de balken, ook achter de raveelbalk van het trapgat. Schuur de PIR zo nodig 1 mm vlak en tape de naden met alu-tape. Lijm en schroef de vloerplaat (betonplex, trapgat uitgezaagd) met RVS 4 x 40. Zet daarna de PIR in de benedenwanden C, D, E en F en tape de naden. In E komt ook PIR boven de latei. De lucht komt laag binnen, via de inlaat onder het luik.",
        ]),
        ("Bovenwanden", [
            f"Bouw de frames I, J en K volgens blad T9, met de platen zoals beneden. Zaag in de achterplaat van I het gat voor de ventilatiebuis (Ø102, op de buismaat): hart {VENT_R} mm uit de rechterrand, gezien vanuit de kamer, en {VENT_Z} mm boven de vloer.",
            "Zet I, J en K op de cassette zoals de benedenwanden: I eerst, J en K ertegen, en verbind ze vanuit de vakken. Schroef de onderregels met 5 x 80 door de vloerplaat in de cassette. Zet de twee hoekstijlen van wand H voor J en K, net als de raamstijlen B voorlopig met één schroef. Meer zit er niet in de voorwand: het raam komt ertussen.",
        ]),
        ("Plafond en dak", [
            f"Bouw de plafondcassette L zoals de tussenvloer, met de plafondplaat met de gelakte kant naar beneden. Zet hem op de bovenwanden en schroef vanuit de wandvakken omhoog. Boven het raam rust de rand voor alleen op de hoekstijlen; tussen rand en kozijn blijft {m.WIN_JOINT} mm. Leg PIR in de wanden I, J en K en tussen de plafondbalken, en tape alle naden. Snijd in wand I de PIR uit rond het gat voor de ventilatiebuis.",
            f"Zaag {len(m.CEIL_X)} sporen en 2 zijsporen op {m.RAFT_L} mm en schuin, van {m.RAFT_H0} voor naar {m.RAFT_H1} achter (blad T7). Schroef de sporen recht boven de plafondbalken, {OV_F} mm voor en {OV_B} mm achter het regelwerk uit. Zet de zijsporen {OV_S} mm buiten de zijkant van het regelwerk, met per kant 3 rijklossen van {KLOS} mm naar de buitenste spoor: boven de voorwand, in het midden en boven de achterwand. De bovenkant van elke klos loopt schuin mee met de sporen. Boor in elke klos een gat Ø16 zodat er lucht langs kan.",
            f"Boeiboorden: voor en achter ({m.ROOF_W - 36}) tegen de koppen van sporen en zijsporen, 2 schroeven 5 x 80 per spoor. Daarna links en rechts ({m.ROOF_L}) over de zijsporen en de koppen van voor en achter. De bovenkant komt {m.OSB_T} mm boven de sporen, gelijk met de dakplaat, en de onderkant 33 mm onder de sporen.",
            f"Leg de dakplaat ({m.ROOF_W - 36} x {m.RAFT_L}) tussen de boeiboorden, met de lange kant dwars op de sporen. Schroef hem met RVS 4 x 40 om de 150 mm in sporen en zijsporen en rond de hoeken af. Houd de plaat droog tot de EPDM erop zit.",
            f"Snij de EPDM (1520 x 1300) eerst op maat: 1520 over de breedte en in de diepte {m.ROOF_L} plus 30 mm voor en achter. Links en rechts snij je de overmaat af tot 30 mm. Zo valt er rondom 30 mm over de boeiboorden, net onder de trim van 28 mm. De rest, een strook van ca. 1520 x {1300 - m.ROOF_L - 60}, bewaar je voor het bovenraam. Lijm de EPDM met Coverbond contactlijm volgens het blik, bij droog weer boven 5 °C: smeer plaat en EPDM allebei in, laat afdampen en leg het in één keer goed. Test eerst op zuigende OSB of primer nodig is. Werk naden en randen af met EPDM-kit. Daktrim (Brute 35 x 28): zaag de 2 lengtes op {m.ROOF_W} en {m.ROOF_L} met de hoeken in verstek; meet eerst, want het is krap. Schroef met RVS 4,5 x 35 om de ca. 200 mm: bij de sporen en zijsporen door de plaat in het spoor, daartussen in de bovenkant van het boeiboord. Alleen in 11 mm OSB houdt de schroef niet. Hang het gootje met afschot aan het achterste boeiboord, met de afvoer weg van de schutting.",
            "<b>Het casco is nu regendicht.</b> Laat het droog nakijken voordat je verdergaat.",
        ]),
        ("Folie en spouw", [
            "Breng de folie aan op alle gevels rond het casco, met minstens 100 mm overlap en boven over onder. Vouw de folie in de raamopeningen om tot op de stijlen en plak hem vast met folietape.",
            "Ventilatiebuis: steek de PVC-buis door de achterplaat en de PIR naar buiten, met licht afschot naar buiten, zo lang dat hij straks gelijk komt met de buitenkant van de gevelplanken. Plak de folie rond de buis af met folietape.",
            "Spouwlatten volgens bladen T2 en T3, met RVS 4 x 40 om de 300 mm. Een lat mag uit meerdere stukken bestaan: 9 latten van 2500 zijn genoeg (samen 17,9 m nodig). Leg elke naad op hout, met minstens 2 schroeven per stuk, geen stukken korter dan 300 mm, en verdeel de naden over de hoogte. Behandel de zaagvlakken. De achterlatten staan recht voor de stijlen van beide verdiepingen. De middelste lat van elke zijwand heeft geen stijl achter zich: schroef hem in elke regel en zijbalk die hij kruist (tussen de regels ca. 420 mm vrij), niet in de PIR.",
            "Voorkant: de latten onder beide ramen (band tussenvloer en voorrand vloer) komen met de bovenkant precies gelijk met de vloer, want het kozijn steunt erop. Onderbreek de lat boven het bovenraam in het midden over 10 mm voor de ventilatie. Laat de spouw onder en boven open en dek af met stroken RVS-gaas van ca. 40 mm breed, in een L gevouwen. Draag handschoenen; er mogen geen draadjes uitsteken.",
        ]),
        ("Ramen", [
            f"Schroef eerst de band tussenvloer (90 hoog) en de voorrand vloer ({m.Z_DECK - m.CLAD_Z0} hoog) met RVS 4 x 40 op de latten, met de bovenkant gelijk met de vloer erachter. Laat links en rechts 58 mm vrij voor de hoeklatten.",
            "Zaag het lekdorpelprofiel op 1070 en 600 mm, zodat het 35 mm (boven) en 50 mm (beneden) voorbij elke kant van het kozijn steekt, en maak de randen glad. Zet de staande zijde tegen de voorkant van de band of voorrand, met de bovenkant gelijk met de vloer en de schuine zijde naar buiten. Niet hoger, anders staat het kozijn scheef. Voorboor en schroef met RVS 3,5 x 25 om de 200 mm en kit de gaten. Kit ook de open kopjes dicht.",
            "Lijm de EPDM op de vloerplaat, over de bovenrand van de band en langs de staande zijde omlaag, tot minstens 10 mm op de schuine zijde. Laat achter een rand van 30 mm vrij, die straks achter het kozijn omhoog komt. Geen stelblokjes en geen dorpellat: het kozijn staat direct op de EPDM.",
            f"Plaats het raam binnenstebuiten, kozijn gelijk met de gevel, waterpas en haaks op de vloer. Schuif de stijlen links en rechts er strak tegenaan, met {m.WIN_GAP} mm speling per kant: gebruik een plaatje van {m.WIN_GAP} mm als maat en haal het daarna weg. Zet de stijlen nu definitief vast: onder en boven een hoekanker, en 2 schroeven 5 x 80 in de wandstijl erachter. Kies rechte stijlen, want een kromme stijl trekt het kozijn mee. In de kopvoeg van {m.WIN_JOINT} mm komt bij elk bevestigingspunt boven een wig van 6 mm. Meet of het kozijn recht blijft.",
            "Bevestig met kozijnschroeven 7,5 x 112, Torx T30, voorgeboord, op ongeveer 55 mm van de gevel: maximaal 150 mm uit de binnenhoeken en maximaal 600 mm onderling, bij voorkeur bij de sluitpunten. Bovenraam: 2 per zijkant in de hoekstijlen en 3 boven. Onderraam: 2 per zijkant in de raamstijlen en 2 boven. Niet door de onderkant: dat doorboort de EPDM. Controleer de bediening en stel het beslag zo nodig af. Verlijm de EPDM-rand tegen de achterkant van het kozijn.",
            "Kit de zijvoegen tussen kozijn en stijl aan de buitenkant af, en kit ook de kopvoeg, de glaslatten en de naden. Vul de kopvoeg achter de kit met weinig PU-vulschuim of minerale wol en laat het raam vast staan tot het schuim hard is. Kit niet dicht wat water moet afvoeren. Controleer of de vleugel vrij langs de dorpel draait, controleer de bediening en blokkeer of beveilig de kiepstand.",
            "Watertest, nu het nog open is: spoel beide ramen 15 minuten met een tuinslang van boven naar beneden, met de ramen dicht. Kijk aan de binnenzijde van het kozijn en onder de dorpel. Lekt het, los dat eerst op.",
        ]),
        ("Gevel", [
            "Monteer de hoeklatten op de hoeken (blad T2), met RVS 4 x 40 in de spouwlatten.",
            f"Gevelplanken van onder naar boven, tong omhoog, stomp tegen de hoeklatten. De onderste plank komt {m.CLAD_OVER} mm onder de onderkant van het vloerframe en loopt evenwijdig aan het frame. Deze plank zit maar ca. {m.CLAD_Z0} mm boven de tegels en vangt spatwater: zaag de onderrand schuin af als druiprand, verzegel hem met kopshoutverzegeling en schroef de plank zonder lijm, zodat je hem later los kunt vervangen. De bovenste rij is de gerifte strook van {m.TOP_STRIP} mm. Schroef met RVS 4 x 40 in de spouwlatten en boor voor aan de plankeinden. Zaag de planken achter rond de ventilatiebuis uit.",
            "Voorkant: de kaderstijlen naast de ramen, het kader boven het bovenraam en de afdekking van de open wandkop van de veranda (blad T2). Plaats de regenluifel tussen de hoeklatten op 5 RVS-consoles, op ca. 30 cm afstand, 12 mm aflopend naar voren en met de achterkant tegen de band; kit die naad. Lijm een EPDM-rest over de bovenkant, met een druiprand aan de voorkant. Laat de lekdorpel van het bovenraam erboven vrij drupen. Controleer of de vleugels vrij blijven draaien.",
            "Schroef de onderplaten van het overstek (betonplex) onder de sporen, zijsporen en rijklossen. Houd 15 mm spleet tot de gevel en leg daar RVS-gaas in: hier ventileren spouw en dak.",
        ]),
        ("Ventilatie", [
            "Ventilatie: kit de buis rondom aan de gevel. Buitenrooster met een rondje RVS-gaas erachter, binnen het afsluitbare rooster.",
        ]),
        ("Inwerken", [
            "Kattenluik: zet het de eerste weken vast open, zodat de kat went. Zet het binnenpaneel er alleen in als je de doorgang wilt afsluiten, bijvoorbeeld voor de dierenarts. Laat het chalet luchten tot je de lak niet meer ruikt. Leg mat en mand, hang de hygrometer op en controleer alle schroefpunten aan de katkant.",
            "Test 3 dagen zonder kat: temperatuur, vocht, condens, de kap en de stand van het rooster.",
            "Laat de kat wennen met de voeding op de veranda. Controleer de eerste weken de hygrometer, de goot en de wanden, en na elke harde bui de binnenzijde van de kozijnen.",
        ]),
        ("Vastzetten aan de schutting", [
            "Zet het chalet pas vast als alles af is en het zeker op de goede plek staat. Los op zijn voeten kan het bij een harde windstoot op de voorkant (rond 75-85 km/h op chalethoogte, berekening met aannames) achterover tegen de schutting kantelen, en bij harde wind van achteren of opzij naar voren. Met de ramen op het zuidoosten is dat zeldzaam, maar niet uitgesloten, vooral bij onweersbuien.",
            "Tot het vast staat: kijk bij de weerberichten naar windwaarschuwingen. Bij code oranje voor wind zet je het chalet tijdelijk vast met een spanband: horizontaal om het chalet, ter hoogte van de tussenvloer, en om twee schuttingpalen. Leg hoekbeschermers of een doek onder de band op de hoeklatten, zodat de beits niet beschadigt. De schutting voorkomt kantelen naar achteren, de band kantelen naar voren.",
            "Definitief: twee afstandhouders van geïmpregneerd 44 x 69 tussen de achterwand en de schuttingpalen, ter hoogte van de plafondrand. Aan de chalet-kant elk met 2 RVS constructieschroeven door gevelplank en spouwlat in de achterrand van het plafond, recht achter een achterlat; aan de schutting met een RVS hoekanker of bout in de bankirai-paal. Bankirai is erg hard: altijd voorboren. Valt er geen paal recht achter het chalet, schroef dan eerst een regel horizontaal over twee palen. De precieze uitvoering volgt na het meten van de palen (aanname, nog uit te werken).",
            "Losmaken kan altijd: schroeven eruit, dan blijven er alleen gaatjes in de palen achter.",
        ]),
    ]
    for i, (t, ss) in enumerate(steps, 1):
        Bd.append(KeepTogether([P(f"{i}. {t}", "h2")] + [B(s) for s in ss]))
    Bd += [PageBreak(), P("Onderhoud", "h1")]
    for t in ("Elk jaar voor de winter: kit, EPDM, trim, gootje, gaas en roosters nakijken; hygrometer vergelijken.",
              "Onderste gevelplank en voet van de hoeklatten: elk jaar nakijken en zo nodig bijbeitsen; die krijgen spatwater van de tegels. De plank is los te vervangen.",
              "Stelvoeten: elk jaar kijken of alle voeten nog dragen, of de contramoeren vast zitten en of er roest bij de inslagmoeren zit. Zolang het chalet niet vast staat: let op windwaarschuwingen (stap 15).",
              "Dak: niet op de plaat staan of er een ladder tegen zetten. Maak het schoon vanaf een trap ernaast.",
              "Ramen: elk seizoen de goot en buitennaden controleren, want daar zit het grootste risico. Regelmatig reinigen en het beslag twee keer per jaar smeren.",
              "Gevel: Douglas vraagt om regelmatig bijhouden. Hornbach adviseert onbehandeld Douglas om de 2 jaar te beitsen; voor de Hybride houtbeits noemt Hornbach tot 7 jaar bescherming, afhankelijk van weer en constructie. Controleer jaarlijks en herstel beschadigingen direct.",
              "Binnen: met water en mild schoonmaakmiddel. Lak op tijd bijwerken bij krassen. Geen producten die voor de kat schadelijk zijn."):
        Bd.append(B(t))
    Bd += [P("Bronnen", "h2")]
    for t in (
        "Hornbach-pagina's bekeken op 6-11-2026: kelderraam 12074105, ARON Basic+ 12331530, betonplex 12628592, Elliotis Pine 10000081, TENCO Bootlak 10728553 (met productinformatieblad), Premiumfol Bonding Adhesive 12218370, betonmortel 7195709, PIR 10368509, EPDM 10469549, daktrim 5581276, Douglas 10537457, vuren 5185884 en 5185888, antraciet beits 10277060, folie 7049802. Op 10-11-2026: LIGHTPLY multiplex 12575686 met verwerkingsvoorschrift (as.170091148). Op 12-11-2026: Hettich stelvoet M10x75 Ø75 RVS 4297033 (belastbaarheid 50 kg, verstelbereik niet opgegeven) en Dresselhaus inslagmoer 10x13 3857241.",
        "KNMI: Windstotenklimatologie van Nederland (TR-306, 2009), figuren 5 en 7.",
        "ARON Basic+ 70 mm technisch blad en montageaanbeveling RC 1/RC 2 (Hornbach, as.187466783, as.187466663), door mij toegepast op een houten wand en op het kelderraam; maattekening kelderraam (as.91729658).",
        "IKO enertherm: Hornbach-productinformatie. Premiumfol: verwerkingsvoorschrift en handleiding via Hornbach.",
        "Zonneopbrengst: 2 % van jaaropbrengst in december (18 kWh per kWp) tot circa 32 kWh per kWp volgens verschillende Belgische en Britse bronnen; indicatief.",
        "Kiepraam en katten: Dierenbescherming en KNMvD, via AVROTROS Radar en Hart van Nederland.",
        "Binnenstebuiten monteren: geen bron gevonden die dit bevestigt of beschrijft; eigen beoordeling.",
    ):
        Bd.append(B(t))
    doc = SimpleDocTemplate(path_b, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    PART["naam"] = "Zaaglijst, stappenplan en onderhoud"
    doc.build(Bd, onFirstPage=footer, onLaterPages=footer)


def write_xlsx(path):
    wb = Workbook()
    F = "Arial"
    head = PatternFill("solid", fgColor="1F2A30")
    hf = Font(name=F, bold=True, color="FFFFFF", size=10)
    base = Font(name=F, size=10)
    bold = Font(name=F, size=10, bold=True)
    blue = Font(name=F, size=10, color="0000FF")
    yellow = PatternFill("solid", fgColor="FFFF99")
    ws = wb.active
    ws.title = "Zaaglijst"
    cols = ["Bouwdeel", "Onderdeel", "Materiaal", "Aantal", "Lengte mm", "Breedte mm", "Dikte mm", "Opmerking", "Gezaagd"]
    ws.append(cols)
    for r_ in ROWS:
        d = r_["dims"]
        ws.append([r_["group"], r_["name"], r_["mat"], r_["qty"], d[0], d[1], d[2], r_["note"], ""])
    for c in ws[1]:
        c.fill, c.font = head, hf
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = base
    for col, w in zip("ABCDEFGHI", (30, 32, 32, 8, 11, 11, 9, 48, 9)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Inkoop")
    ws["A1"] = "Vul de gele cellen in met de actuele prijs. Blauw = prijs gezien op Hornbach.nl op 6-11-2026, incl. btw. Leeg artikelnummer = nog geen Hornbach-artikel gekozen. Totalen rekenen automatisch."
    ws["A1"].font = bold
    ws.append([])
    ws.append(["Artikel", "Artikelnummer Hornbach", "Aantal", "Eenheid", "Prijs € incl. btw", "Regeltotaal €", "Herkomst prijs", "Status"])
    for c in ws[3]:
        c.fill, c.font = head, hf
    first = ws.max_row + 1
    for name, q, u, price, src, st in purchase():
        if q is None:
            ws.append([name])
            ws.cell(ws.max_row, 1).font = bold
            continue
        name, art = split_art(name)
        ws.append([name, art, q, u, price, None, src, st])
        i = ws.max_row
        ws.cell(i, 6, f'=IF(E{i}="","",C{i}*E{i})').number_format = "#,##0.00"
        for j in (1, 2, 3, 4, 7, 8):
            ws.cell(i, j).font = base
        ws.cell(i, 2).number_format = "@"
        ws.cell(i, 6).font = base
        pc = ws.cell(i, 5)
        pc.number_format = "#,##0.00"
        if price is None:
            pc.fill = yellow
            pc.font = base
        else:
            pc.font = blue
    last = ws.max_row
    ws.append(["Subtotaal ingevulde prijzen", None, None, None, None, f"=SUM(F{first}:F{last})"])
    ws.cell(ws.max_row, 1).font = bold
    ws.cell(ws.max_row, 6).font = bold
    ws.cell(ws.max_row, 6).number_format = "#,##0.00"
    ws.append(["Aantal regels zonder prijs", None, None, None, None, f'=COUNTIFS(C{first}:C{last},">0",E{first}:E{last},"")'])
    ws.cell(ws.max_row, 1).font = base
    ws.cell(ws.max_row, 6).font = base
    for col, w in zip("ABCDEFGH", (58, 14, 8, 9, 14, 13, 24, 56)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"

    ws = wb.create_sheet("Latten op lengte")
    ws.append(["Materiaal", "Lat nr.", "Handelslengte mm", "Zagen (mm)", "Rest mm"])
    for c in ws[1]:
        c.fill, c.font = head, hf
    for col, w in zip("ABCDE", (34, 8, 16, 90, 10)):
        ws.column_dimensions[col].width = w
    ws = wb.create_sheet("Platen op maat")
    ws.append(["Plaat", "Plaatnr.", "Onderdeel", "Lengte mm", "Breedte mm", "x vanaf hoek mm", "y vanaf hoek mm"])
    for c in ws[1]:
        c.fill, c.font = head, hf
    for col, w in zip("ABCDEFG", (26, 8, 42, 11, 11, 15, 15)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    fill_list_tabs(wb)
    wb.save(path)


def fill_list_tabs(wb):
    """Vult de tabbladen die uit het model volgen. Inkoop blijft ongemoeid."""
    base = Font(name="Arial", size=10)

    def reset(ws):
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row)

    def finish(ws):
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.font = base

    ws = wb["Zaaglijst"]
    reset(ws)
    for r_ in ROWS:
        d = r_["dims"]
        ws.append([r_["group"], r_["name"], r_["mat"], r_["qty"], d[0], d[1], d[2], r_["note"], ""])
    finish(ws)
    ws.auto_filter.ref = ws.dimensions

    ws = wb["Latten op lengte"]
    reset(ws)
    for key in STOCK:
        for i, bar in enumerate(NEST[key], 1):
            ws.append([m.MAT[key], i, bar["stock"], " + ".join(str(int(c_[0])) for c_ in bar["cuts"]), int(bar["left"])])
    for key, label_ in (("DG", m.MAT["DG"]), ("DK", "Douglas 18x145 (hoek/boei/luifel antraciet + kader grenen beits)")):
        for i, s in enumerate(NEST[key], 1):
            ws.append([label_, i, 3000, " + ".join(f"{int(it[2])}x{int(it[3])}" for it in s.items), ""])
    finish(ws)

    ws = wb["Platen op maat"]
    reset(ws)
    for key, label_ in (("LP9", "Lightply 9, 2440x1220"), ("BP12", "Betonplex 12, 2500x1250"), ("OSB", "OSB-3 11, 2440x1220"), ("PIR", "PIR 70, 1200x600")):
        for i, sheet in enumerate(NEST[key], 1):
            for x_, y_, w_, h_, nm in sorted(sheet.items, key=lambda it: (it[1], it[0])):
                ws.append([label_, i, nm.replace(":", " "), round(w_), round(h_), round(x_), round(y_)])
    finish(ws)


def write_store(path):
    """Zaagopdrachten voor de bouwmarkt: per plaat één A4 met alleen de sneden die de bouwmarkt maakt."""
    W_, H_ = [v / mm for v in landscape(A4)]
    c = canvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle("Zaagopdrachten bouwmarkt")
    c.setAuthor("Claude Code")
    plates = [(key, i, s_) for key in ("BP12", "LP9", "OSB") for i, s_ in enumerate(NEST[key], 1)]
    red, wood, strip, rest_, keep = C("#c0392b"), C("#e6cfa6"), C("#e6cfa6"), C("#f6f3ee"), C("#d9dee2")
    for n, (key, i, s_) in enumerate(plates, 1):
        name, art, pw, ph = PLATE_INFO[key]
        if n > 1:
            c.showPage()
        label(c, 16, H_ - 18, "Zaagopdracht", 18, True)
        label(c, W_ - 62, H_ - 18, f"Plaat {n} van {len(plates)}", 14, True, red)
        label(c, 16, H_ - 27, f"{name}, {pw} x {ph} mm, Hornbach art. {art}" + (f"  (plaat {i} van {len(NEST[key])})" if len(NEST[key]) > 1 else ""), 11)
        label(c, 16, H_ - 34, f"{len(s_.cuts)} zaagsneden, in de volgorde 1, 2, 3 ... Elke snede gaat door het hele stuk. Maten in mm.", 9.5)
        sc = max(pw / 215, ph / 84)
        ox, oy = 30, H_ - 41 - ph / sc
        v = View(c, ox, oy, sc)
        for x, y, w, h, kind in s_.store:
            fill = {"piece": wood, "home": strip, "rest": rest_, "keep": rest_}[kind]
            rect(v, x, x + w, y, y + h, fill, lw=0.5)
            cx, cy = v.p(x + w / 2, y + h / 2)
            t = f"{round(w)} x {round(h)}"
            if kind in ("rest", "keep"):
                t = "rest " + t
            c.setFillColor(INK if kind in ("piece", "home") else colors.grey)
            wmm, hmm = w / sc, h / sc
            fs = 11 if min(wmm, hmm) > 20 else 8 if min(wmm, hmm) > 7 else 6 if min(wmm, hmm) > 4 else 4.5
            if wmm >= hmm or wmm > 30:
                c.setFont("DB" if kind != "rest" and kind != "keep" else "D", fs)
                c.drawCentredString(cx, cy - fs * 0.35, t)
            else:
                c.saveState(); c.translate(cx, cy); c.rotate(90)
                c.setFont("DB" if kind not in ("rest", "keep") else "D", fs); c.drawCentredString(0, -fs * 0.35, t); c.restoreState()
        rect(v, 0, pw, 0, ph, None, lw=1.0)
        for k_, (x0, y0, x1, y1) in [(n_, sg) for n_, (sg0, ct) in enumerate(s_.cuts, 1) for sg in [sg0] + ct["more"]]:
            a, b = v.p(x0, y0), v.p(x1, y1)
            c.setStrokeColor(red)
            c.setLineWidth(1.6)
            c.line(*a, *b)
            horiz = abs(a[1] - b[1]) < .1
            if horiz:
                px, py = (a[0] - 5 * mm, a[1]) if x1 - x0 >= pw - 1 else (a[0] + 7 * mm, a[1])
            else:
                px, py = a[0], a[1] + 7 * mm
            c.setFillColor(red)
            c.circle(px, py, 3 * mm, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("DB", 9)
            c.drawCentredString(px, py - 3.2, str(k_))
        dim(v, 0, 0, pw, 0, -6, str(pw), 8)
        dim(v, 0, 0, 0, ph, -6, str(ph), 8)

        # tabel
        y = oy - 15
        cols = (16, 26, 84, 108, 132)
        for x_, t in zip(cols, ("Nr", "Zaag uit stuk", "Richting", "Op maat", "Geeft")):
            label(c, x_, y, t, 9.5, True)
        c.setStrokeColor(INK); c.setLineWidth(0.5); c.line(16 * mm, (y - 1.6) * mm, (W_ - 16) * mm, (y - 1.6) * mm)
        y -= 6
        for k_, (_, ct) in enumerate(s_.cuts, 1):
            a_, b_ = ct["out"]
            for x_, t, bold in zip(cols, (str(k_), src_text(ct), ct["dir"], str(ct["at"]),
                                          f"{out_text(a_, ct['stack'])}   en   {out_text(b_, ct['stack'])}"), (True, False, False, True, False)):
                label(c, x_, y, t, 9.5, bold, red if x_ == 16 else INK)
            y -= 4.8
        label(c, 16, 10, "Zaagsnede circa 4 mm; die valt steeds in het tweede stuk. Een snede met 'smal strookje' zaagt het laatste stuk op maat. Graag alle stukken en resten meegeven.", 8.5)
        if any(ct["stack"] > 1 for _, ct in s_.cuts):
            label(c, 16, 14, "Gelijke stroken: leg ze op elkaar en zaag ze in één keer; hetzelfde nummer staat dan op beide stroken.", 8.5, True)
    c.save()



def main():
    probs = m.collisions() + m.window_clearance() + m.stringer_clashes()
    if probs:
        sys.exit(f"Geometrieconflicten: {probs}")
    tmp = os.path.join(HERE, ".tmp")
    os.makedirs(tmp, exist_ok=True)
    a, b, d = [os.path.join(tmp, x) for x in ("a.pdf", "b.pdf", "d.pdf")]
    write_drawings(d)
    write_text(a, b)
    w = PdfWriter()
    for f in (a, d, b):
        for pg in PdfReader(f).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": "Kattenchalet bouwplan", "/Author": "Claude Code"})
    with open(OUT_PDF, "wb") as fh:
        w.write(fh)
    write_store(OUT_STORE)
    if "--xlsx" in sys.argv:   # overschrijft alle eigen invoer in het Excel-bestand
        write_xlsx(OUT_XLSX)
    if "--lijsten" in sys.argv:   # alleen de modeltabbladen; Inkoop blijft staan, daarna herberekenen
        wb = load_workbook(OUT_XLSX)
        fill_list_tabs(wb)
        wb.save(OUT_XLSX)
    for f in (a, b, d):
        os.remove(f)
    os.rmdir(tmp)
    print("OK", {k: len(v) for k, v in NEST.items()}, "pagina's", len(PdfReader(OUT_PDF).pages))
    for key in STOCK:
        print(key, {s: sum(b["stock"] == s for b in NEST[key]) for s in STOCK[key]})


if __name__ == "__main__":
    main()
