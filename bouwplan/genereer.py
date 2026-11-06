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
from collections import defaultdict

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
LEGEND = [("R44", "regel 44x44"), ("B69", "balk 44x69"), ("I69", "geïmpr. balk"), ("LP9", "Elliotis Pine 9"), ("BP12", "betonplex 12"),
          ("OSB", "OSB-3 11"), ("PIR", "PIR 70"), ("LAT", "spouwlat"), ("DG", "gevel grenen beits"), ("DK", "hoek/boei/luifel antraciet")]


def nl(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


# --- Tekenprimitieven -------------------------------------------------------
class Sheet:
    """A3-blad met titelhoek. Alle tekeninguitvoer in mm op papier."""

    def __init__(self, c):
        self.c = c
        self.n = 0
        self.W, self.H = [v / mm for v in landscape(A3)]

    def new(self, title, scale):
        if self.n:
            self.c.showPage()
        self.n += 1
        c = self.c
        c.setStrokeColor(INK)
        c.setLineWidth(0.6)
        c.rect(8 * mm, 8 * mm, (self.W - 16) * mm, (self.H - 16) * mm)
        c.rect((self.W - 148) * mm, 8 * mm, 140 * mm, 16 * mm)
        c.setFillColor(INK)
        c.setFont("DB", 10)
        c.drawString((self.W - 146) * mm, 18 * mm, f"Blad T{self.n}: {title}")
        c.setFont("D", 7)
        c.drawString((self.W - 146) * mm, 12.8 * mm, f"Kattenchalet  |  schaal {scale} op A3  |  {REV}, {DATE}  |  maten in mm")
        c.setFont("D", 6)
        c.drawString((self.W - 146) * mm, 9.6 * mm, "Sparingen pas zagen nadat de ramen binnen zijn en ingemeten. Niet van tekening meten.")


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
            return m.stringer_outline() if p.extra["stringer"] == 1 else m.strip_outline()
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
    """Poeren onder de tegels, terras en paalhouders (schematisch)."""
    u0 = min(a for a, _ in xs) - 250
    u1 = max(b for _, b in xs) + 250
    for a, b in xs:
        rect(view, (a + b) / 2 - 150, (a + b) / 2 + 150, -280, -60, C("#c9c9c9"))
    rect(view, u0, u1, -50, 0, C("#b9b4aa"))
    for a, b in xs:
        mid = (a + b) / 2
        rect(view, mid - 8, mid + 8, -170, m.Z_POST - 4, C("#8d979c"))
        rect(view, a - 2, b + 2, m.Z_POST - 4, m.Z_POST, C("#8d979c"))
        rect(view, a - 2, a + 2, m.Z_POST, m.Z_POST + 100, C("#8d979c"))
        rect(view, b - 2, b + 2, m.Z_POST, m.Z_POST + 100, C("#8d979c"))


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
        return not p.name.startswith(("Spoor", "Onderplaat"))
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
LONG_FIXED = {"B69": 5}   # mix uit de Inkoop-tab; andere mixen schelen maar een paar cent
STOCK = {"R44": {3600: 5.29, 2400: 3.55}, "B69": {3600: 6.49, 3000: 5.40, 2400: 4.30}, "I69": {3600: 6.75},
         "P69": {1800: 6.69}, "LAT": {2500: 5.49}}


def bars(items, stocks, kerf=4, margin=10, n_fixed=None):
    """Eerst n_long lange latten, daarna korte; houdt de goedkoopste indeling, of n_fixed lange. margin: tolerantie Hornbach."""
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


def collect():
    rows = m.cutlist()
    by = defaultdict(list)
    for r in rows:
        for _ in range(r["qty"]):
            by[r["mat"]].append(r)
    res = {}
    short = lambda r: r["group"][0] + ":" + r["name"]
    for key, stocks in STOCK.items():
        res[key] = bars([(r["dims"][0], short(r)) for r in by[m.MAT[key]]], stocks, n_fixed=LONG_FIXED.get(key))
    res["LP9"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in by[m.MAT["LP9"]]], 2440, 1220, tries=60000)
    res["BP12"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in by[m.MAT["BP12"]]], 2500, 1250)
    res["OSB"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in by[m.MAT["OSB"]]], 2440, 1220)
    res["PIR"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in by[m.MAT["PIR"]]], 1200, 600, kerf=2)
    res["DG"] = nest([(r["dims"][0], max(r["dims"][1], 145) if r["dims"][1] >= 100 else r["dims"][1], short(r)) for r in by[m.MAT["DG"]]], 3000, 145, kerf=4, rotate=False)
    # hoek-, boei- en kaderdelen uit dezelfde planken: beitsen gebeurt na het zagen
    res["DK"] = nest([(r["dims"][0], r["dims"][1], short(r)) for r in rows if r["mat"] in (m.MAT["DK"], m.MAT["DM"]) for _ in range(r["qty"])], 3000, 145, kerf=4, rotate=False)
    return rows, res


ROWS, NEST = collect()
R = berekening.results()
STAIR_DEG = round(math.degrees(math.atan(m.RISE / m.TREAD)))
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
    sh.new(title, "1:10")
    c = sh.c
    col_w = 134
    row_h = 90
    for i, (grp, axis, u0, u1, name, flip) in enumerate(walls):
        cx = 18 + (i % 3) * col_w
        cy = 200 - (i // 3) * row_h
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
        view_title(c, cx, cy + 66, name)
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
    c.setFont("D", 7)
    c.setFillColor(INK)
    c.drawString(18 * mm, 16 * mm, "Regelwerk gezien vanaf de BUITENZIJDE. Plaat en spouwlatten zijn weggelaten. Geel = PIR. Maten van wandbegin tot stijl-randen.")


def detail_box(c, x, y, w, h, title):
    c.setStrokeColor(C("#aab2b6"))
    c.setLineWidth(0.3)
    c.rect(x * mm, y * mm, w * mm, h * mm)
    label(c, x + 2, y + h - 5, title, 8.5, True)


def details_page(sh):
    sh.new("Details", "1:2 t/m 1:10")
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
    leader(v, 113, 40, 80, 230, "Elliotis Pine 9: gelijmd, geschroefd, blank gelakt")
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
    label(c, 214, 232, f"Tussen stijlen {m.XR0-m.XL1} x {m.ROOM_H}, beneden {m.PART_X0-m.XL1} x {m.ROOM_H}.", 6.3, True)
    label(c, 214, 228, "Geen dorpellat, geen houten opstand: kozijn direct op vloer.", 6)
    label(c, 214, 224, "Schroef 7,5x112 zijkant en boven: max. 150 uit hoek,", 6)
    label(c, 214, 220, "max. 600 h.o.h.; onder niet schroeven. Voeg 9 per kant;", 6)
    label(c, 214, 216, f"kozijn raakt stijl over {m.WIN_D-m.F0} mm: voorboren, klossen, niet krom.", 6)
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
    leader(v, 100, base + 58, 286, 272, f"EPDM 1,2 op OSB-3 11; afschot 1:{SLOPE} naar achter")
    leader(v, 40, base + 30, 286, 266, "Ventilatieruimte 28-57 tussen sporen, voor en achter open")
    leader(v, -8, base - 3, 286, 260, "Spleet 15 mm met RVS gaas: spouw en dak ventileren hier")
    leader(v, 120, m.PLY + 20, 286, 254, "PIR 70 op plafondplaat; plafond Elliotis Pine 9")
    leader(v, -141, base + 50, 286, 248, "Boeiboord en alu daktrim met druiprand")
    dim(v, -150, -5, 0, -5, -5, "150", 5.8)

    # 4 fundering
    detail_box(c, 14, 92, 130, 92, "4  Fundering (1:6, poer afgebroken getekend)")
    v = View(c, 45, 127, 6)
    rect(v, -150, 150, -200, -60, grey)
    rect(v, -150, 150, -60, -50, C("#a8a8a8"))
    rect(v, -190, 190, -50, 0, C("#b9b4aa"))
    rect(v, -8, 8, -170, m.Z_POST - 4, C("#8d979c"))
    rect(v, -34, 34, m.Z_POST, 180, FILL[m.MAT["P69"]])
    rect(v, -38, 38, m.Z_POST - 4, m.Z_POST, C("#8d979c"))
    rect(v, -38, -34, m.Z_POST, m.Z_POST + 100, C("#8d979c"))
    rect(v, 34, 38, m.Z_POST, m.Z_POST + 100, C("#8d979c"))
    rect(v, -44, 44, 58, 63, C("#5a6268"))
    rect(v, -44, 44, 100, 105, C("#5a6268"))
    rect(v, -60, 150, 180, 249, FILL[m.MAT["I69"]])
    rect(v, -60, 150, 249, m.Z_DECK, floor18)
    rect(v, 34, 150, 180 - m.OSB_T, 180, FILL[m.MAT["OSB"]])
    rect(v, -100, -82, m.CLAD_Z0, m.Z_DECK, wood)
    label(c, 15, 129, "terras", 5.5)
    leader(v, 0, -130, 90, 101, "Poer 300x300x500 onder de tegel; op klei 700 diep")
    leader(v, 150, -25, 90, 108, "Tegel in mortelbed; gat Ø25 rond de staaf, daarna kit")
    leader(v, 0, -90, 90, 115, "Staaf Ø16 x 200 (aanname), 90-110 mm in het beton")
    leader(v, 36, 90, 90, 122, "U-paalhouder 71, art. 3896646, thermisch verzinkt")
    leader(v, 44, 60, 90, 129, "2 RVS bouten M10 door U en poot; speling opvullen")
    leader(v, 0, 150, 90, 136, "Poot 68x68, nominaal 150; zaagvlak behandelen")
    leader(v, 80, 215, 90, 143, "Frame 44x69 geïmpr., PIR 70; onderplaat OSB 11")
    leader(v, 80, 255, 90, 150, "Betonplex 12, afschot 5 mm naar voren")
    dim(v, 150, 0, 150, 180, 4, "180", 5.8)
    label(c, 72, 96, "Elke poot trekvast verankeren: kantelgevaar bij storm.", 6.3, True)

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
    hole0 = m.HOLE_Y0 - m.IN_Y0
    rect(v, 0, depth, -12, 0, floor18)
    rect(v, 0, hole0, m.ROOM_H, climb, beam)
    h0 = m.ST_Y0 - m.IN_Y0
    t0 = m.ST_T0 - m.IN_Y0
    poly(v, [(y - m.IN_Y0, z - m.Z_DECK) for y, z in m.stringer_outline()], floor18)
    poly(v, [(y - m.IN_Y0, z - m.Z_DECK) for y, z in m.strip_outline()], C("#7f5a34"))
    for i in range(m.N_RISE - 1):
        z = m.RISE * (i + 1)
        y = t0 + m.TREAD * i
        rect(v, y, y + m.TREAD_D, z - 12, z, C("#7f5a34"))
    dim(v, t0, m.RISE, t0 + m.TREAD, m.RISE, 4, str(round(m.TREAD)), 5.5)
    dim(v, depth, 0, depth, climb, 5, str(climb), 5.5)
    dim(v, h0, -12, depth, -12, -3, str(depth - h0), 5.5)
    label(c, 290, 97.5, f"{m.N_RISE} optreden van {round(m.RISE)}, {m.N_RISE-1} tredes {m.TREAD_D} x {m.ST_X1-m.ST_X0} op de tanden, helling {STAIR_DEG}°. Sisal", 6.3)
    label(c, 290, 94.5, "of rubbermat. Donkere strook: versterking binnenkant rechterboom. Plaats de trap vóór de tussenvloer.", 6.3)

    # 7 ventilatie
    detail_box(c, 14, 28, 196, 60, "7  Ventilatie (natuurlijke trek)")
    label(c, 18, 78, f"Afvoer: PVC Ø100 door de achterwand, hart z = {m.VENT['z']} ({m.Z_U_TOP-m.VENT['z']} onder het plafond), x = {m.VENT['x']}.", 6.5)
    label(c, 18, 74, "Binnen: afsluitbaar rooster Ø100. Buiten: rooster Ø100, buis licht aflopend naar buiten; RVS-gaas ca. 1 mm erachter, jaarlijks nakijken.", 6.5)
    label(c, 18, 70, f"Aanvoer: open voorkant -> veranda -> doorgang 190 x 260 -> trapkamer -> trapgat {m.HOLE_X1-m.HOLE_X0} x {m.HOLE_Y1-m.HOLE_Y0}.", 6.5)
    label(c, 18, 66, "De afvoer zit rechtsachter en het trapgat linksachter: de lucht loopt langs de achterwand, niet over het bed bij het raam.", 6.5)
    label(c, 18, 60, "Stand rooster: vorst bijna dicht (circa 2 m³/h volstaat), 0-5 °C half open, boven 5 °C helemaal open.", 6.5, True)
    label(c, 18, 56, "Hygrometer in de bovenkamer. Blijft de luchtvochtigheid langdurig boven 75-80 %: rooster verder open of", 6.5)
    label(c, 18, 52, "een kleine 12 V-ventilator op hygrostaat op het binnenrooster (Ø100 past daarvoor).", 6.5)

    # 8 verwarming
    detail_box(c, 214, 28, 192, 60, "8  Verwarming en elektra (uitvoering elektra: installateur)")
    label(c, 218, 78, "Verwarming tegen de rechterwand, laag, achter een verankerde stalen beschermkap (niet aanraakbaar).", 6.5)
    label(c, 218, 74, "Bevestig kap en verwarming in de stijlen, niet in de 9 mm plaat. Volg de afstanden van de fabrikant. Niet-brandbare plaat erachter.", 6)
    label(c, 218, 70, "Thermostaat in dichte kast buiten (IP65), voeler in de bovenkamer op ongeveer 300 hoogte, niet vlak bij de verwarming.", 6.5)
    label(c, 218, 66, "Kabel: geheel in mantelbuis Ø16 in de wand/vloer. Geen kabel in het bereik van de kat.", 6.5)
    label(c, 218, 60, f"Vermogen: 120 W buisverwarming of 2 x 60 W. Berekende piek {round(R['peak'])} W bij -5 °C.", 6.5, True)
    label(c, 218, 56, "Tweede beveiliging: maximaalthermostaat op 25 °C in serie. Buitenaansluiting op aardlekschakelaar 30 mA.", 6.5)
    label(c, 218, 52, "Niet in dit ontwerp: zonnepaneel als hoofdbron. Zie berekening. Mantelbuis maakt uitbreiding later mogelijk.", 6.5)


def nest_page(sh):
    sh.new("Zaagplan platen", "1:20")
    c = sh.c
    x, y = 16, 268
    colz = 0
    for key, name, sw, sh_ in (("BP12", "Betonplex 12 mm, 2500x1250", 2500, 1250), ("OSB", "OSB-3 11 mm, 2440x1220", 2440, 1220), ("LP9", "Elliotis Pine 9 mm, 2440x1220", 2440, 1220), ("PIR", "PIR 70 mm, 1200x600", 1200, 600)):
        for i, s in enumerate(NEST[key]):
            sc = 20 if key != "PIR" else 20
            pw, ph = sw / sc, sh_ / sc
            if key == "PIR" and i % 6 == 0 and i > 0:
                pass
            if x + pw > 410:
                x = 16
                y -= 72
            label(c, x, y, f"{name}  plaat {i+1}/{len(NEST[key])}", 6.8, True)
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
            x += pw + 8
    c.setFont("D", 7)
    c.setFillColor(INK)
    c.drawString(16 * mm, 16 * mm, "Zaagsnede 4 mm meegerekend. Letter = bouwdeel (zie zaaglijst). Positie van elk stuk: Excel, tabblad Platen op maat. Hornbach kan platen in de vestiging op maat voorzagen; laat grote stroken voorsnijden voor transport.")


def write_drawings(path):
    c = canvas.Canvas(path, pagesize=landscape(A3))
    c.setTitle("Kattenchalet tekeningen")
    sh = Sheet(c)
    top = round(m.Z_RAFT + m.RAFT_B + 19.2)
    room_lbl = f"{m.ROOM_H}"

    # T1 overzicht 3D
    sh.new("Overzicht 3D", "n.v.t.")
    view_title(c, 14, 280, "Voor-rechts")
    iso_draw(c, iso_boxes(), 35, 95, 13)
    view_title(c, 215, 280, "Achter-links")
    iso_draw(c, iso_boxes(mirror=True), 225, 95, 13)
    legend(c, 18, 42)
    label(c, 195, 46, f"Hoofdmaten: buiten {m.W} x {m.D}, hoogte {round(m.Z_TOP)} (bovenkant dak voor), dak {m.ROOF_W} x {m.ROOF_L}.", 7.5, True)
    label(c, 195, 41, f"Bovenkamer binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Trapkamer {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Veranda vrij {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H}.", 7.5)
    label(c, 195, 36, f"Raam boven 1000 x 500, beneden 500 x 500, beide binnenstebuiten. Totaalgewicht ongeveer {round(R['mass'])} kg.", 7.5)

    # T2 aanzichten voor/achter
    sh.new("Aanzichten voor en achter", "1:10")
    v = View(c, 40, 72, 10)
    view_title(c, 40, 262, "Vooraanzicht")
    front_view(v)
    dim(v, 0, 0, m.W, 0, -34, str(m.W))
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
    v = View(c, 370, 72, 10, flip=True)
    view_title(c, 225, 262, "Achteraanzicht (van achteren gezien)")
    back_view(v)
    dim(v, 0, 0, m.W, 0, -34, str(m.W))
    dim(v, -100, 0, -100, top, 8, str(top))
    legend(c, 18, 28)
    label(c, 110, 30, "Hoeklatten, boeiboorden en regenluifel in antraciet beits, de rest van de gevel met kader en band in grenen beits.", 7)
    label(c, 110, 26, "Tekenkleur indicatief; nerf blijft zichtbaar. Plankmaten: zie zaaglijst. Luifel tussen de hoeklatten.", 7)

    # T3 aanzichten zijkanten
    sh.new("Aanzichten zijkanten", "1:10")
    v = View(c, 165, 72, 10, flip=True)
    view_title(c, 45, 262, "Linkeraanzicht (voorzijde rechts), geen openingen")
    side_view(v, "L")
    dim(v, 0, 0, m.D, 0, -34, str(m.D))
    dim(v, m.ROOF_Y0, m.Z_TOP, m.ROOF_Y1, m.Z_TOP, 3, f"{m.ROOF_L} dak")
    v = View(c, 240, 72, 10)
    view_title(c, 225, 262, "Rechteraanzicht (voorzijde links), geheel dicht")
    side_view(v, "R")
    dim(v, 0, 0, m.D, 0, -34, str(m.D))
    dim(v, m.ROOF_Y1, 0, m.ROOF_Y1, top, 4, f"achter {top}")
    legend(c, 18, 28)

    # T4 doorsneden
    sh.new("Doorsneden A en B", "1:10")
    v = View(c, 60, 72, 10)
    view_title(c, 45, 262, "A-A: door trap, trapgat en bovenkamer (x = 215)")
    section_x(v, 215)
    dim(v, m.IN_Y0, m.Z_U_TOP, m.IN_Y1, m.Z_U_TOP, -6, f"{m.IN_Y1-m.IN_Y0} binnen", 6)
    dim(v, m.YB1, m.Z_DECK, m.YB1, m.Z_L_TOP, 8, room_lbl)
    dim(v, m.YB1, m.Z_UP, m.YB1, m.Z_U_TOP, 8, room_lbl)
    dim(v, m.HOLE_Y0, m.Z_UP, m.HOLE_Y1, m.Z_UP, 5, f"trapgat {m.HOLE_Y1-m.HOLE_Y0}", 6)
    v = View(c, 240, 72, 10)
    view_title(c, 225, 262, f"B-B: door veranda en bovenkamer (x = {SEC_B})")
    section_x(v, SEC_B)
    dim(v, 0, m.Z_DECK, m.IN_Y1, m.Z_DECK, 5, f"{m.IN_Y1} vrij", 6)
    dim(v, m.YB1, 0, m.YB1, m.Z_LEG, 8, str(m.Z_LEG))
    dim(v, m.YB1, m.Z_LEG, m.YB1, m.Z_DECK, 8, str(m.Z_DECK - m.Z_LEG))
    dim(v, m.YB1, m.Z_L_TOP, m.YB1, m.Z_UP, 8, str(m.Z_UP - m.Z_L_TOP))
    dim(v, m.YB1, m.Z_U_TOP, m.YB1, m.Z_RAFT, 8, str(m.Z_RAFT - m.Z_U_TOP))
    legend(c, 18, 28)

    # T5 doorsneden C/D
    sh.new("Doorsneden C en D", "1:10")
    v = View(c, 40, 72, 10)
    view_title(c, 40, 262, "C-C: door de ramen, kijkrichting achter (y = 30)")
    section_y(v, 30)
    dim(v, m.WIN_U["x0"], m.Z_UP, m.WIN_U["x1"], m.Z_UP, 8, f"raam {m.WIN_U_W}", 6)
    dim(v, m.WIN_L["x0"], m.Z_DECK, m.WIN_L["x1"], m.Z_DECK, 8, f"raam {m.WIN_L_W}", 6)
    v = View(c, 225, 72, 10)
    view_title(c, 225, 262, f"D-D: door doorgang en trap, kijkrichting achter (y = {SEC_D})")
    section_y(v, SEC_D)
    dim(v, m.IN_X0, m.Z_U_TOP, m.IN_X1, m.Z_U_TOP, -6, f"{m.IN_X1-m.IN_X0} binnen", 6)
    dim(v, m.IN_X0, m.Z_DECK, m.ROOM_X1, m.Z_DECK, 5, f"{m.ROOM_X1-m.IN_X0} binnen", 6)
    dim(v, m.VER_X0, m.Z_DECK, m.IN_X1, m.Z_DECK, 5, str(m.IN_X1 - m.VER_X0), 6)
    legend(c, 18, 28)

    # T6 plattegronden
    sh.new("Plattegronden", "1:10")
    v = View(c, 40, 158, 10)
    view_title(c, 40, 262, "Beneden, snede z = 500")
    plan(v, 500)
    dim(v, 0, 0, m.W, 0, -6, str(m.W), 6)
    dim(v, 0, 0, 0, m.D, -6, str(m.D), 6)
    dim(v, m.IN_X0, m.IN_Y1, m.ROOM_X1, m.IN_Y1, 12, str(m.ROOM_X1 - m.IN_X0), 6)
    dim(v, m.VER_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 12, str(m.IN_X1 - m.VER_X0), 6)
    dim(v, m.VER_X0, m.CAT_Y0, m.VER_X0, m.CAT_Y1, 7, "190", 5.5)
    label(c, 40, 257.5, "Trap langs de linkerwand, doorgang 190 x 260 achterin, voorkant veranda open, rechterwand dicht.", 6.5)
    v = View(c, 225, 158, 10)
    view_title(c, 225, 262, "Boven, snede z = 1200")
    plan(v, 1200)
    dim(v, 0, 0, m.W, 0, -6, str(m.W), 6)
    dim(v, m.IN_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 12, str(m.IN_X1 - m.IN_X0), 6)
    dim(v, m.IN_X1, m.IN_Y0, m.IN_X1, m.IN_Y1, 13, str(m.IN_Y1 - m.IN_Y0), 6)
    dim(v, m.HOLE_X0, m.HOLE_Y1, m.HOLE_X1, m.HOLE_Y1, -17, f"gat {m.HOLE_X1-m.HOLE_X0}", 5.5)
    label(c, 225, 257.5, "Raam voor, trapgat linksachter, afvoer rechtsachter, verwarming rechterwand, mand bij het raam.", 6.5)
    v = View(c, 40, 46, 10)
    view_title(c, 40, 140, "Vloerframe, gezien van boven (vloerplaat weg)")
    plan(v, m.Z_DECK0 - 1, only=lambda p: p.group.startswith("A"))
    xs = [m.F1] + [e for x in m.FLOOR_X[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    v = View(c, 225, 46, 10)
    view_title(c, 225, 140, "Tussenvloer: balken en PIR (bovenplaat weg)")
    plan(v, m.Z_MID_T - 1, only=lambda p: p.group.startswith("G") and "plaat" not in p.name.lower())
    xs = [m.F1] + [e for x in m.MID_X[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    legend(c, 18, 28)

    # T7 dakplattegronden
    sh.new("Plafond en dak", "1:10")
    v = View(c, 45, 158, 10)
    view_title(c, 40, 262, "Plafond: balken en PIR (van boven)")
    plan(v, m.Z_RAFT - 1, only=lambda p: p.group.startswith("L"))
    xs = [m.F1] + [e for x in m.BACK_U[1:-1] for e in (x, x + m.S)] + [m.XB]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, m.YB1, b, m.YB1, 4, size=5.3)
    dim(v, m.F0, m.F0, m.XR1, m.F0, -5, str(m.XR1 - m.F0), 6)
    v = View(c, 245, 150, 10)
    view_title(c, 225, 262, "Dak: sporen en overstek (dakplaat weg)")
    plan(v, m.Z_RAFT + 70, only=lambda p: p.group.startswith("M") and p.mat != m.MAT["OSB"])
    dim(v, m.ROOF_X0, m.ROOF_Y0, m.ROOF_X1, m.ROOF_Y0, -5, str(m.ROOF_W), 6)
    dim(v, m.ROOF_X0, m.ROOF_Y0, m.ROOF_X0, m.ROOF_Y1, -6, str(m.ROOF_L), 6)
    dim(v, 0, m.ROOF_Y1, m.F0, m.ROOF_Y1, 4, size=5.3)
    v = View(c, 45, 45, 10)
    view_title(c, 40, 62, "Spoor, zijaanzicht (5 stuks)")
    poly(v, [(0, 0), (m.ROOF_L, 0), (m.ROOF_L, m.RAFT_B), (0, m.RAFT_F)], FILL[m.MAT["B69"]], lw=0.4)
    dim(v, 0, 0, m.ROOF_L, 0, -5, str(m.ROOF_L), 6)
    dim(v, 0, 0, 0, m.RAFT_F, -5, str(m.RAFT_F), 5.5)
    dim(v, m.ROOF_L, 0, m.ROOF_L, m.RAFT_B, 4, str(m.RAFT_B), 5.5)
    label(c, 110, 36, f"Uit balk 44x69: schuine zaagsnede. Afschot 1:{SLOPE} naar de achterkant. Dakgoot achter, afvoer weg van de schutting.", 7)
    legend(c, 18, 28)

    # T8, T9 wanden
    walls_page(sh, "Wandframes beneden", [
        ("B Voorwand beneden", "x", m.F0, m.PART_X1, f"B  Voorwand beneden, {m.PART_X1-m.F0} breed (raam ertussen)", False),
        ("C Achterwand beneden", "x", m.F0, m.XR1, f"C  Achterwand beneden, {m.XR1-m.F0} lang", False),
        ("D Linkerwand beneden", "y", m.F1, m.IN_Y1, f"D  Linkerwand beneden, {m.IN_Y1-m.F1} lang", False),
        ("E Scheidingswand", "y", m.F1, m.IN_Y1, f"E  Scheidingswand, {m.IN_Y1-m.F1} lang (doorgang 190 x 260)", False),
        ("F Rechterwand beneden", "y", m.F0, m.IN_Y1, f"F  Rechterwand beneden, {m.IN_Y1-m.F0} lang, geheel dicht", False),
    ])
    walls_page(sh, "Wandframes boven", [
        ("H Voorwand boven", "x", m.F0, m.XR1, f"H  Voorwand boven, {m.XR1-m.F0} breed (alleen hoekstijlen, raam ertussen)", False),
        ("I Achterwand boven", "x", m.F0, m.XR1, f"I  Achterwand boven, {m.XR1-m.F0} lang", False),
        ("J Linkerwand boven", "y", m.F1, m.IN_Y1, f"J  Linkerwand boven, {m.IN_Y1-m.F1} lang", False),
        ("K Rechterwand boven", "y", m.F1, m.IN_Y1, f"K  Rechterwand boven, {m.IN_Y1-m.F1} lang", False),
    ])

    details_page(sh)
    nest_page(sh)

    # montage explosie
    sh.new("Montagevolgorde (explosietekening)", "n.v.t.")
    offs = {"A": 0, "B": 180, "C": 180, "D": 180, "E": 180, "F": 180, "N": 180, "G": 420, "H": 660, "I": 660, "J": 660, "K": 660, "L": 880, "M": 1100}
    iso_draw(c, iso_boxes(dz=lambda p: offs.get(p.group[0], 0), skip=("P", "Q")), 225, 72, 17)
    for t, z in (("5. Dakopbouw: sporen, OSB, EPDM, boeiboord, daktrim", 2650), ("4. Plafondcassette op de bovenwanden", 2340),
                 ("3. Vier bovenwanden op de tussenvloer", 1750), ("2. Tussenvloer als cassette op de benedenwanden", 1150),
                 ("1. Benedenwanden en trap op het vloerframe", 700), ("0. Poeren, poten en vloerframe", 200)):
        label(c, 18, 72 + (z + 450) / 17, t, 8, True)
    label(c, 18, 28, "Gevelfolie, spouwlatten, ramen en gevelplanken volgen als het casco staat en waterdicht is. De ramen zijn hier niet getekend.", 7)
    c.save()


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
        ("Constructieplaat Elliotis Pine 2440x1220x9 (art. 10000081)", n["LP9"], "pl", 18.38, H, "Gecontroleerd; C+/C: platen zelf uitzoeken. Geen reserve. Lijmklasse en formaldehydeklasse vragen"),
        ("Betonplex Acacia 2500x1250x12 (art. 12628592)", n["BP12"], "pl", 57.49, H, "Gecontroleerd; vloeren, trap en overstek"),
        ("Constructieplaat OSB-III recht 2440x1220x11 (art. 10222931)", n["OSB"], "pl", 18.55, H, "Gecontroleerd; lange kant dwars op de sporen"),
        ("Douglas 18x145x3000 tand-en-groef (art. 10537457), gevel + kader", n["DG"] + n["DK"] + 2, "st", 11.59, H, "Gecontroleerd; werkende breedte ca. 135"),
        ("Isolatie en folie", None, None, None, None, None),
        ("IKO PIR 70 Rd 3,15, pak 7 st = 5,04 m² (art. 10368509)", 1, "pak", 88.64, H, f"{n['PIR']} platen nodig. Alu-cachering in vestiging bevestigen"),
        ("Dampopen waterkerende gevelfolie, Sd ≤ 0,1 m, ca. 10 m²", 1, "rol/stuk", None, C_, "Niet gevonden bij Hornbach; vestiging vragen of bouwmarkt"),
        ("Alu-tape PIR, 50 mm", 1, "rol", None, C_, ""),
        ("RVS 304 gaas, 20 mazen, ca. 1 mm, 40 x 200 cm (Amazon B0DL5P11F2)", 1, "rol", 18.99, "Eigen invoer, Amazon", "Spouw en ventilatiebuis. Maaswijdte bij ontvangst nameten"),
        ("SOUDAL Soudaband BG1 20/5-10, 5,6 m (art. 12731245)", 1, "rol", 8.45, H, "Gecontroleerd; 4 m nodig, alleen de zijvoegen"),
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
        ("Beton 25 kg (6 poeren 300x300x500 = 270 liter)", 24, "zak", None, C_, "Hoeveelheid van verpakking afhankelijk; meer op klei"),
        ("KAISERTHAL U-paalhouder met betonanker 71x100x200, thermisch verzinkt (art. 3896646)", 6, "st", 2.95, "Hornbach, 6-11-2026", "In verse poer zetten. Treksterkte en inbouwdiepte niet opgegeven"),
        ("RVS bout M10 x 100 met 2 ringen en moer", 12, "st", None, C_, "2 per poot; 3 mm speling in de U opvullen met ringen"),
        ("Cementmortel 25 kg voor het tegelbed", 1, "zak", None, C_, ""),
        ("Diamantboor Ø25 voor de tegels", 1, "st", None, C_, "Misschien te lenen"),
        ("Reservetegels, zelfde als het terras", 6, "st", None, "Prijs nog opvragen", "Voor als het chalet later weggaat; formaat nog meten"),
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


def inkoop_uit_excel():
    """De inkooplijst in het Excel-bestand is leidend: daar staan ook eigen prijzen en wijzigingen."""
    ws = load_workbook(OUT_XLSX, data_only=True)["Inkoop"]
    return [tuple(c.value for c in r[:8]) for r in ws.iter_rows(min_row=4) if r[0].value is not None]


def write_text(path_a, path_b):
    r = R
    A = []
    A += [P("Kattenchalet", "title"), P("Bouwplan, tekeningen, materiaal en zaaglijst", "sub")]
    A += [P(f"<b>{REV}, {DATE}.</b> Dit plan vervangt Rev A en de eerdere voorlopige tekening en zaaglijst. "
            "Alle maten, zaaglijsten en plaatindelingen komen uit één rekenmodel. Dat model controleert automatisch dat geen onderdelen door elkaar lopen en dat de ramen vrij in hun sparingen passen.")]
    A += [P("In het kort", "h2")]
    A += [T([["Onderdeel", "Uitvoering"],
             ["Buitenmaat", f"{m.W} x {m.D} x {round(m.Z_TOP)} mm, dak {m.ROOF_W} x {m.ROOF_L} mm"],
             ["Bovenkamer", f"Binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H} mm. Raam 100 x 50. Vloer, wanden en plafond geïsoleerd met PIR 70 mm."],
             ["Trapkamer", f"Binnen {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H} mm. Raam 50 x 50. Wanden met de rest van de PIR, onverwarmd. Trap langs de linkerwand, helling {STAIR_DEG}°, {m.N_RISE} optreden van {round(m.RISE)} mm."],
             ["Veranda", f"Kamer met open voorkant, {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H} mm. Zijkant dicht. Doorgang naar de trapkamer 190 x 260 mm."],
             ["Toegang", "Via de ramen, die binnenstebuiten zijn gemonteerd en vanaf buiten opengaan. Geen luiken."],
             ["Wandbekleding", f"Elliotis Pine 9 mm, {len(NEST['LP9'])} platen 2440 x 1220 (Hornbach, voor binnen), gelijmd, geschroefd en blank gelakt, zodat de nerf zichtbaar blijft. Ook plafond en onderkant tussenvloer, beide uit één stuk."],
             ["Vloeren en trap", "Betonplex 12 mm (art. 12628592). Ook de trap en de onderkant van het dakoverstek."],
             ["Verwarming", f"Netstroom met thermostaat, 120 W buisverwarming achter beschermkap. Piek berekend op {round(r['peak'])} W bij -5 °C. Circa {round(r['kwh'])} kWh per winter."],
             ["Ventilatie", "PVC Ø100 met afsluitbaar rooster, aanvoer via trapgat. Ø40 is te weinig (zie berekening)."],
             ["Plaatsing", "Op het terras in Rijswijk, in de hoek bij de schutting. Rug naar de schutting, ramen naar het terras. Achterwand minstens 250 mm van de schutting."],
             ["Fundering", "6 betonpoeren onder de terrastegels, met U-paalhouders in het beton; trekvast. Vloer beneden met PIR 70 en een OSB-onderplaat. Vrije hoogte onder het frame ca. 170 mm."],
             ["Materiaal", "Vooral Hornbach. Gevel Douglas 18 x 145 met Hornbach Hybride houtbeits grenen, hoeklatten, boeiboorden en regenluifel in Hybride houtbeits RAL 7016 antraciet; dak EPDM."],
             ], [33, 145])]
    A += [P("Jouw keuzes", "h2")]
    for t in (
        "<b>Geen toegangsluiken.</b> De ramen zijn de toegang en zitten binnenstebuiten, gelijk met de gevel.",
        f"<b>Zo klein mogelijk rond het bovenraam.</b> Het raam van 1000 mm past precies tussen de binnenplaten van de linker- en rechterwand, zonder raamstijlen ernaast. Daardoor is het chalet {m.W} mm breed. De kamers zijn {m.IN_Y1-m.IN_Y0} mm diep, gemeten vanaf de achterkant van het kozijn; buitenmaat {m.D} mm.",
        f"<b>Kozijn direct op de vloer, geen dorpellat.</b> Kamers {m.ROOM_H} mm hoog: raam {m.WIN_H} plus {m.WIN_JOINT} mm montagevoeg boven, zodat het kozijn past en het plafond er niet op rust. Totale hoogte {round(m.Z_TOP)} mm, onder de 1650-1750 uit de overdracht. Dit geeft minder waterreserve dan de eerdere opstand van 30 mm; zie 'Ramen binnenstebuiten'.",
        f"<b>Zijkant veranda dicht.</b> Toegang alleen via de voorkant. De verandapaal vervalt, waardoor de veranda {m.IN_X1-m.VER_X0} mm breed wordt.",
        f"<b>Trap tegen de linkerwand,</b> stijgend van voor naar achter, met het trapgat linksachter. De voet van de trapboom staat {m.ST_Y0-m.IN_Y0} mm achter het kozijn, vrij van de EPDM-rand; dat kan, omdat de vleugel nu naar buiten draait. Helling {STAIR_DEG}°, jouw keuze.",
        "<b>Elliotis Pine 9 mm als wandbekleding en betonplex 12 mm voor de vloeren.</b> Goedkoper dan multiplex 6 mm op bestelling en betonplex 18 mm. Zie 'Plaatmateriaal'.",
        "<b>Op het terras, met poeren onder de tegels.</b> De U-paalhouders staan in vers beton en steken door een gat in de tegel. Zo blijft het terras heel en het beton uit het zicht. Weghalen kan door de staven door te slijpen en de 6 tegels te vervangen.",
    ):
        A.append(B(t))
    A += [P("Mijn adviezen waarmee je akkoord bent", "h2")]
    for t in (
        f"<b>Zonnepaneel en accu niet als hoofdbron.</b> In december is ongeveer {round(r['wh_day_dec'])} Wh per dag nodig, terwijl 100 Wp paneel dan {round(r['pv100'][0])}-{round(r['pv100'][1])} Wh per dag oplevert. Daarvoor is {round(r['wp_needed'][0],-2):.0f}-{round(r['wp_needed'][1],-2):.0f} Wp nodig, plus accu: niet haalbaar binnen €250-500. Netstroom past wel. De mantelbuis houdt een uitbreiding open.",
        f"<b>Ø100 in plaats van Ø40 ventilatie.</b> Bij 5 °C trekt Ø40 op natuurlijke wijze {nl(r['vent'][2][3])} m³/h terwijl minstens {nl(r['vent'][2][1])} m³/h nodig is. Ø100 haalt {nl(r['vent'][2][5])} m³/h. Bij vorst knijp je het rooster om warmte te sparen.",
        f"<b>Verankering in de grond.</b> Bij storm is het kantelmoment ongeveer {nl(r['M_over']/r['M_stab'],1)} keer zo groot als wat het eigen gewicht kan opvangen.",
    ):
        A.append(B(t))
    A += [P("Status van de keuzes", "h2")]
    A += [T([["Onderwerp", "Status", "Keuze en toelichting"],
             ["Ramen binnenstebuiten", "Jouw keuze, afwijkend van de bedoelde montage", "Zie 'Ramen binnenstebuiten'. De garantie zal dit waarschijnlijk niet dekken."],
             ["Bovenraam", "Jouw voorkeur", "Hornbach kelderraam 100 x 50 (art. 12074105). Dubbel glas, Uw 1,3, 15,5 kg. Glasdoorkijk ongeveer 764 x 264 mm."],
             ["Raam trapkamer", "Jouw voorkeur", "ARON Basic+ 50 x 50 (art. 12331530). Triple glas, Uw 0,92, 10,4 kg. Glasdoorkijk ongeveer 298 x 298 mm."],
             ["Maat ramen", "Te controleren", "Jij en ik gaan ervan uit dat 1000 en 500 de buitenmaat van het kozijn zijn. Hornbach bevestigt dit niet. Breedte en hoogte van het hele chalet hangen hier nu direct van af: meet na levering; voor die tijd niet zagen."],
             ["Wandbekleding", "Jouw keuze", "Elliotis Pine 9 mm, 2440 x 1220 (art. 10000081), blank gelakt. Bovenkamer prima. Veranda en trapkamer: goed afwerken, zie 'Plaatmateriaal'."],
             ["Vloeren", "Jouw keuze", "Betonplex 12 mm (art. 12628592). Sterk genoeg voor kat en mand, niet om op te staan of te knielen."],
             ["Isolatie", "Jouw keuze", "PIR 70 mm alu in regels 44 x 69, geen vezels voor de kat. Eén pak van 5,04 m² (7 platen). De plaat is 1 mm dikker dan de regel: hij drukt in tegen de folie."],
             ["Wanden beneden", "Jouw keuze", "De rest van de PIR gaat in de buitenwanden van trapkamer en veranda. Dat levert weinig warmte op, want die ruimtes zijn onverwarmd en de veranda staat open, maar er blijft minder materiaal over."],
             ["Dampopbouw", "Mijn advies", "Alu-PIR met getapete naden als dampscherm, geen extra folie. Buiten dampopen waterkerende folie."],
             ["Dak", "Mijn advies", f"Koud dak: PIR op plafondplaat, geventileerde ruimte, OSB-3 11 mm (jouw keuze), EPDM. Afschot 1:{SLOPE} naar achter. Niet op het dak staan."],
             ["Tussenvloer", "Mijn advies", "PIR 70 mm vult de hele holte tussen de balken. De plaat is 1 mm dikker dan de balk: schuur of druk hem in, zodat de vloer vlak blijft."],
             ["Vloer beneden", "Jouw keuze", "PIR 70 tussen de balken van het geïmpregneerde frame, OSB-3 11 eronder uit de rest van de dakplaat, betonplex erop, 5 mm afschot naar voren. Weinig winst in warmte; het gebruikt vooral restmateriaal. De onderkant is daarna niet meer te controleren: frame rondom dicht houden."],
             ["Verwarming", "Besloten", "Netstroom met thermostaat. Specifiek verwarmingsmodel nog te kiezen; ik vond er geen bij Hornbach."],
             ["Ventilatie", "Besloten", "PVC Ø100 (eigen restant) met afsluitbaar rooster. De werking in de praktijk controleren met een hygrometer."],
             ["Fundering", "Jouw keuze", "6 poeren onder de tegels met KAISERTHAL U-paalhouder (art. 3896646) in vers beton. Beton blijft bij weghalen onzichtbaar in de grond."],
             ["Treksterkte paalhouder", "Te controleren", "Hornbach geeft geen treksterkte, inbouwdiepte of betekenis van de maten. Ik neem aan: U 100 hoog, staaf 200 lang. Meet dit na ontvangst."],
             ["Tegels", "Te controleren", "Formaat, dikte en tegelpatroon meten. Elke staaf moet minstens 50 mm van een voeg uitkomen."],
             ["Grond onder het terras", "Te controleren", "Zand, puin of klei zie je bij het graven. Op klei 700 mm diep, dan is meer beton nodig."],
             ["Houtsoort gevel", "Jouw keuze", "Douglas 18 x 145 tand-en-groef (Hornbach) met Hornbach Hybride houtbeits grenen, op primer. Op Douglas wordt de kleur warmer en roder dan op het inspiratieplaatje: eerst een proefstuk; hoeklatten en boeiboorden in Hybride houtbeits RAL 7016 antraciet."],
             [f"Buitenmaat {m.W} x {m.D}", "Jouw keuze", f"Volgt uit het raam (breedte) en {m.IN_Y1-m.IN_Y0} mm binnendiepte. Vervangt de 1300 x 900 uit de overdracht."],
             ["Vergunning", "Te controleren", "Niet onderzocht; controleer lokale regels en afspraken met buren."],
             ], [33, 30, 115])]

    A += [PageBreak(), P("Ramen binnenstebuiten", "h1")]
    A += [P("Dit ontwerp volgt jouw keuze. Beide ramen zijn gemaakt om naar binnen open te draaien en Hornbach vermeldt geen buitendraaiende montage. Deze montage is dus niet door de fabrikant bedoeld. Het risico zit vooral in water. De details vangen dat zo goed mogelijk op, maar ik kan niet garanderen dat het volledig dicht blijft. Ik vond geen bron die deze montage bevestigt; de punten hieronder zijn mijn eigen beoordeling op basis van de profieltekening.")]
    A += [T([["Wat verandert", "Gevolg", "Maatregel in dit ontwerp"],
             ["Afwateringssleuven wijzen naar de andere kant", "Water dat achter de eerste rubber komt, loopt aan de binnenzijde uit het kozijn.", "EPDM onder het kozijn, 30 mm omhoog achter het kozijn verlijmd, en naar buiten over de lekdorpel. Er is geen houten opstand meer: dit is de enige waterkering, en een lek komt sneller op de vloer."],
             ["Glaslatten en vleugel zitten buiten", "Meer naden in de regen. De vleugel heeft aan deze kant geen druiprand.", "Raam onder overstek (150) en luifel (90). Naden en glaslatten dun afkitten. Lekdorpel met overstek 34."],
             ["Wind drukt de vleugel van het kozijn af", "De rubbers sluiten bij harde wind minder goed. De sluitpunten vangen de kracht op.", "Kleine afmetingen beperken de kracht. Na storm goot en binnenzijde controleren."],
             ["Kiepstand kantelt naar buiten", "Regen valt in de opening. Risico voor de kat blijft.", "Alleen op kiep in droog weer en als de kat niet binnen is, of de kiepstand blokkeren."],
             ["Greep zit buiten", "Iedereen kan het raam openen. Vleugel kan bij wind dichtslaan.", "Afsluitbare greep; bij wind vasthouden tijdens gebruik."],
             ["Links wordt spiegelbeeld", "De scharnierzijde verandert mee. Greep links gezien van binnen wordt greep links gezien van buiten.", "Kies bij bestellen welke kant je wil; controleer dit op het raam zelf."],
             ["Garantie", "DHK sluit 'verkeerde montage' uit; de voorwaarden van Hornbach en ARON heb ik niet gelezen.", "Reken erop dat de garantie vervalt. Vraag het zo nodig aan Hornbach."],
             ], [44, 66, 68])]
    A += [P("Als het toch lekt, is het terugzetten naar normale montage lastig, omdat dan de bediening verdwijnt. Controleer daarom de eerste maanden na elke harde regenbui de goot en de binnenzijde van het kozijn.")]
    A += [P("Bereik door de ramen", "h2")]
    A += [P(f"De doorgang in het raam is kleiner dan de buitenmaat: ongeveer 866 x 366 mm boven en 360 x 360 mm beneden. De ruimtes zijn {m.IN_Y1-m.IN_Y0} mm diep, en daar komt de wanddikte van het kozijn bij. Het bovenraam is breed genoeg, maar de achterhoeken zijn net haalbaar. In de <b>trapkamer</b> is de achterhoek achter de trap het lastigst: gebruik een kleine stofzuiger met slang of een borstel met lange steel, eventueel ook via de doorgang vanuit de veranda. De trap is na het plaatsen van de tussenvloer niet meer uit te nemen.")]

    A += [P("Plaatmateriaal", "h2")]
    A += [P("<b>Buitenkwaliteit is binnen inderdaad niet nodig.</b> In de verwarmde bovenkamer is Elliotis Pine prima. De trapkamer en veranda zijn onverwarmd en de veranda staat aan de voorkant open. Hornbach noemt deze plaat alleen voor binnen en geeft geen lijmklasse. Daar ligt dus het enige echte risico; vraag de lijmklasse en de formaldehydeklasse na.")]
    for t in ("Elliotis Pine is kwaliteit C+/C: duidelijke nerf en kwasten, ongeveer 540 kg/m³ (afgeleid). Een krabplank blijft nuttig. De kwaliteit wisselt: zoek de platen zelf uit en leg de mooiste kant naar binnen.",
              "48 uur acclimatiseren, voorboren, schroeven minstens 15 mm uit de rand. Schuur goed tot er geen splinters meer zijn en werk af met TENCO Bootlak blank mat in minstens 3 lagen, zonder witte grondverf. Schuur licht tussen de lagen en wacht 24 uur per laag; verwerken tussen 8 en 25 °C, niet in de volle zon. De fabrikant noemt alleen hardhout: test daarom op een restje of de lak goed hecht en of kwasten erdoorheen komen. Randen afronden (R3) en sealen: dat is het kwetsbaarste deel.",
              "Lijm met PU- of houtlijm en schroef om de 100 mm op de regels, omdat de platen het chalet stijf houden. Dat geldt vooral voor de wanden rond de open voorkant van de veranda.",
              "Laat de onderrand 3-5 mm boven de vloer stoppen en kit de naad, zodat de plaat geen water optrekt. Controleer de veranda de eerste winter. Blijft de plaat daar nat of trekt hij bol, vervang dan alleen die wanden door betonplex 12 mm.",
              f"Alles past uit {len(NEST['LP9'])} platen van 2440 x 1220 mm, ongeveer {round(LP_USE*100)} % benut; volg het zaagplan op blad T11. Alle wanden, het plafond en de onderkant van de tussenvloer zijn uit één stuk. Laat de platen bij Hornbach voorzagen langs de eerste lange snede als ze anders niet in de auto passen.",
              "Bevestig zware dingen, zoals de verwarmingskap, in de regels en niet in de plaat.",
              f"Betonplex 12 mm is sterk genoeg voor een kat en mand bij deze balkafstand (maximaal {BAY_MAX} mm), maar niet om op te staan of te knielen. Ik gebruik het ook voor de trap en de onderkant van het dakoverstek, omdat die buiten hangt en er restmateriaal van de vloeren is."):
        A.append(B(t))

    A += [PageBreak(), P("Berekeningen", "h1")]
    A += [P("Aannames: binnen 11 °C, ontwerpnacht -5 °C. Warmte van de kat zelf is niet meegeteld, dus dit is aan de veilige kant. Warmtebruggen zijn per wanddeel meegenomen. Het zijn handberekeningen, geen gevalideerde simulatie.")]
    A += [P("Warmteverlies bovenkamer", "h2")]
    rows = [["Onderdeel", "W/K", f"W bij {round(r['dT'])} K verschil"]]
    for k, v in r["parts"].items():
        rows.append([k, nl(v, 2), nl(v * r["dT"], 0)])
    rows.append(["<b>Totaal transmissie</b>", f"<b>{nl(r['H'],2)}</b>", f"<b>{nl(r['p_trans'],0)}</b>"])
    rows.append([f"Ventilatie, {nl(r['q_design'])} m³/h (rooster bijna dicht)", nl(0.34 * r['q_design'], 2), nl(r["p_vent"], 0)])
    rows.append(["<b>Piek bij -5 °C</b>", "", f"<b>{nl(r['peak'],0)}</b>"])
    A += [T(rows, [108, 30, 40])]
    A += [P(f"Gemiddeld in november tot en met maart is ongeveer {round(r['p_avg'])} W nodig, ongeveer {round(r['kwh'])} kWh per winter. Bij een aangenomen stroomprijs van €0,30 per kWh is dat ongeveer €{round(r['kwh']*0.3)}. "
            "Een verwarming van 120 W geeft reserve voor strenge vorst en snel opwarmen. Een lichtere 60 W laat bij de berekende piek weinig ruimte over. Het raam is met ongeveer " f"{round(r['parts']['Raam 100x50 (Uw 1,3)'] / r['H'] * 100)} % van het verlies een groot deel; als het door de omgekeerde montage minder goed sluit, wordt het verbruik hoger.")]
    A += [P("Oppervlaktetemperatuur en condens", "h2")]
    A += [P(f"Het dauwpunt bij 11 °C en 75 % luchtvochtigheid is {nl(r['dew'])} °C. Bij -5 °C buiten is de wand op de isolatie {nl(r['s_ins'])} °C, op een regel {nl(r['s_wood'])} °C en op het glas {nl(r['s_glass'])} °C. "
            "Dat ligt allemaal boven het dauwpunt. De kozijnrand kan kouder zijn, dus lichte condens onderin het raam is bij strenge vorst mogelijk.")]
    A += [P("Ventilatie op natuurlijke trek", "h2")]
    A += [P(f"Vochtproductie van de kat is geschat op 5-10 g/h (een aanname: geschaald vanaf mensgegevens). Doel: onder 75 % luchtvochtigheid bij buitenlucht van 90 %. Trekhoogte {nl(berekening.STACK_H,2)} m, stromingscoëfficiënt 0,5. Wind helpt meestal, maar telt niet mee.")]
    rows = [["Buiten °C", "Nodig 5 g/h", "Nodig 10 g/h", "Ø40 (36 binnen)", "Ø75 (71 binnen)", "Ø100 (96 binnen)"]]
    for t, a, b, c, d, e in r["vent"]:
        na = "n.v.t.*" if a == float("inf") else nl(a)
        nb = "n.v.t.*" if b == float("inf") else nl(b)
        rows.append([str(t), na, nb, nl(c), nl(d), f"<b>{nl(e)}</b>"])
    A += [T(rows, [26, 28, 28, 32, 32, 32])]
    A += [P("Waarden in m³/h. *Bij 10 °C en vochtige buitenlucht haalt geen enkele luchtverversing 75 %: de lucht is zelf al zo vochtig. Geen probleem zolang de wanden warmer zijn dan de lucht buiten, en kort van duur.", "s")]
    A += [Spacer(1, 4), P("<b>Conclusie:</b> Ø40 volstaat alleen bij vorst. Ø100 is bij 5 °C net voldoende, ook voor de hoge schatting, zonder de weerstand van insectenwering en rooster. De hygrometer moet dit in de praktijk bevestigen; een kleine ventilator is de terugvaloptie.")]
    A += [P("Energievoorziening: waarom geen zonnepaneel als hoofdbron", "h2")]
    A += [T([["Gegeven", "Waarde"],
             ["Benodigd in december", f"Ongeveer {round(r['p_dec'])} W, {round(r['wh_day_dec'])} Wh per dag"],
             ["Opbrengst 100 Wp in december", f"{round(r['pv100'][0])}-{round(r['pv100'][1])} Wh per dag (18-32 kWh per kWp in de maand, geen schaduw)"],
             ["Benodigd paneel", f"{round(r['wp_needed'][0],-2):.0f}-{round(r['wp_needed'][1],-2):.0f} Wp, zonder laadverlies en donkere weken"],
             ["Accu LiFePO4 100 Ah, 12,8 V", f"Ongeveer {round(r['batt_wh'])} Wh bruikbaar, dus ongeveer {round(r['batt_hours'])} uur zonder zon"],
             ], [66, 112])]
    A += [P("Conclusie: een accu overbrugt ruim een etmaal, en in donkere weken laadt een klein paneel die niet op. Netstroom is de enige realistische hoofdbron binnen het budget. Een klein paneel zou wel een ventilator of ledlampje kunnen voeden.")]
    A += [KeepTogether([P("Stabiliteit bij storm", "h2"), P(f"Windkracht op {nl(m.ROOF_W/1000,2)} x {nl(m.Z_TOP/1000,2)} m bij 0,9 kN/m² (aanname, ongeveer een stoot van {r['v_ref']} km/h op chalethoogte): {nl(r['F'])} kN. Kantelmoment {nl(r['M_over'],2)} kNm. Het eigen gewicht van ongeveer {round(r['mass'])} kg geeft {nl(r['M_stab'],2)} kNm tegenwicht. "
            f"Tekort: {nl(r['tension'],1)} kN trek aan de loefzijde, verdeeld over 3 poeren: ongeveer {round(r['leg_kg'])} kg per poot. Eén poer van 300 x 300 x 500 mm weegt ongeveer {round(r['poer_kg'])} kg. Tegel en grondwrijving tel ik niet mee. Daarmee houden de poeren tot ongeveer {math.floor(r['v_anchor']/10)*10} km/h, zolang de 3 poeren gelijk dragen. Bevestig de paalhouders dus echt trekvast in de poer en de poten aan het frame. Dit is een handberekening, niet gecontroleerd door een constructeur. Voor de treksterkte van de paalhouder zelf geeft Hornbach geen waarde."),
            P(f"<b>Waarom niet los of alleen op de tegels.</b> Zonder verankering kantelt het chalet bij wind op de voor- of achterkant al rond {round(r['v_free'],-1):.0f} km/h. Een tegel van 60 x 60 x 5 cm weegt ongeveer 41 kg (aanname voor het formaat), minder dan de trek per poot, en ligt los op het zand."),
            P("<b>Wind in Rijswijk.</b> Rijswijk ligt volgens mijn schatting in de kuststrook van ca. 10 km die het KNMI hanteert. Meetstations die ik op de kaart aanneem als Rotterdam en Valkenburg (KNMI TR-306, 1961-2007): stoot van 108 km/h eens per 2-3 jaar, 130 km/h eens per 10-20 jaar, ongeveer 145 km/h eens per 50 jaar. Die cijfers gelden voor open terrein op ca. 10 m hoogte. In een bebouwde tuin op 1,5 m hoogte is de wind lager; ik neem ca. 20 % aan, maar dat is niet gemeten.")])]
    A += [P("Sterkte", "h2")]
    A += [P(f"Dakplaat OSB-3 {m.OSB_T} mm (jouw keuze) op sporen {m.CEIL_X[1]-m.CEIL_X[0]} mm hart op hart: met 70 kg/m² sneeuw doorbuiging ongeveer 0,1-0,2 mm en spanning circa 0,3 MPa, ruim onder de sterkte van OSB-3 (circa 16 MPa, EN 12369-1, niet nagezocht). Het zwakke punt is de bevestiging van de daktrim, zie het stappenplan. Niet berekend: een knie of ladder op de plaat; ga daarom niet op het dak staan.")]
    A += [P(f"Plafondrand boven het raam (44 x 69, overspanning {m.XR0-m.XL1} mm): dak plus 70 kg/m² sneeuw geeft ongeveer 0,57 kN/m, buigspanning circa 2,1 MPa en doorbuiging circa 0,7 mm, binnen de voeg van {m.WIN_JOINT} mm. Die voeg is nodig: zo komt het dak niet op het kozijn te rusten. Vloerrand boven de veranda (44 x 69, {m.XR0-m.PART_X1} mm): ruim voldoende. Dit is een eenvoudige controle zonder rekenmodel van een constructeur; vuren van Hornbach is niet als C24 gesorteerd.")]

    A += [Spacer(1, 10), P("Veiligheid voor de kat", "h1")]
    A += [T([["Risico", "Maatregel in dit ontwerp"],
             ["<b>Kiepstand van het raam</b>", "<b>Dit is het grootste risico.</b> Katten raken vast in een kiepraam en kunnen daardoor ernstig gewond raken of sterven. Dat geldt ook als het raam naar buiten kiept. Zet de ramen nooit op kiep als de kat erbij kan, tenzij met een beveiliging."],
             ["Open raam", "Door de omgekeerde montage kan de kat er bij een open raam direct uit, en terug. Sluit het raam tijdens het schoonmaken als de kat binnen is. Greep afsluitbaar."],
             ["Eén uitgang", "Met de dichte zijkant is de voorkant van de veranda de enige uitgang. Een vreemde kat of ander dier kan de jouwe dan in het chalet in het nauw drijven. Let daarop in de eerste weken. Een tweede uitgang kan later in de rechterwand, boven de vloer, als dit een probleem blijkt."],
             ["EPDM-rand achter het kozijn", "Deze rand zit nu in de kamer, op kattenhoogte. Verlijm hem volledig en controleer hem regelmatig op krabsporen: een beschadiging is ook een waterlek."],
             ["Isolatie", "PIR volledig achter de wandplaat; geen vezels. Naden gekit, randen afgedekt."],
             ["Elektra en hitte", "Verwarming achter stalen kap, kabels in mantelbuis, thermostaat buiten bereik, maximaalthermostaat, aardlek."],
             ["Brand", "PIR niet bij warmtebron; niet-brandbare plaat achter verwarming; afstand volgens fabrikant. Geen warmtelamp en geen open gloeielement."],
             ["Vastzitten", f"Doorgang 190 x 260; trapgat {HOLE}. Ventilatiegaten met RVS gaas. Treden liggen op de tanden en steken niet buiten de bomen uit; geen kier waar een poot in kan."],
             ["Trap", f"Treden met sisal of rubber. Hoek {STAIR_DEG}°: steil voor een oudere of stijve kat, dus controleer dat in de eerste weken. De bovenste trede komt tegen de achterwand; de kat stapt daar zijwaarts of vooruit de kamer in."],
             ["Lage kamers", f"Vrije hoogte {m.ROOM_H} mm: ruim genoeg voor een kat, minder om te klimmen of springen. Mand laag houden, zodat de kat nog door het raam kan kijken."],
             ["Houtbehandeling", "Gebruik de houtbeits alleen buiten. Binnen geen biocide. De TENCO-lak bevat oplosmiddel: lak de platen vóór montage en goed geventileerd, en laat ze dagen luchten tot je niets meer ruikt voordat de kat erin gaat. Controleer het veiligheidsblad van elk product."],
             ["Tocht", "Dichte zijkant, doorgang achterin, bed bij het raam; lucht loopt achterlangs naar de afvoer."],
             ["Scherpe delen", "Schroeven door de plaat mogen niet uitsteken: verzink ze. Plaatranden licht afronden."],
             ], [38, 140])]
    A += [P("Wat de Hornbach-ramen betekenen", "h2")]
    for t in (
        f"<b>Glashoogte.</b> Een profiel van {m.SIGHT_U} mm rondom laat bij het bovenraam {m.WIN_H-2*m.SIGHT_U} mm glashoogte over, op {m.SIGHT_U}-{m.WIN_H-m.SIGHT_U} mm boven de vloer. Een kat op een lage mand kijkt er goed doorheen. Je ziet niet het royale panorama uit de inspiratieafbeelding.",
        "<b>Isolatie.</b> Het betere raam (Uw 0,92) zit in de onverwarmde trapkamer. Een triple 100 x 50 zou ongeveer 3 W schelen; niet de moeite waard.",
        "<b>Levering.</b> Geen van beide heeft een greep. Hornbach adviseert montage door een vakman.",
        "<b>Maat.</b> De maattekening van het kelderraam is een algemeen catalogusprofiel. Meet beide ramen na ontvangst en pas zo nodig de sparing aan.",
    ):
        A.append(B(t))

    doc = SimpleDocTemplate(path_a, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title="Kattenchalet bouwplan", author="Claude Code")
    PART["naam"] = "Deel 1: uitgangspunten"
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
    Bd += [PageBreak(), P("Inkooplijst", "h1")]
    Bd += [P("Aantallen volgen uit het zaagplan, zonder reservelatten en met krappe indelingen: bij een zaagfout koop je een lat of plaat bij. Latten zijn op prijs gekozen, met 4 mm zaagverlies en de tolerantie van Hornbach van -1 cm. Prijzen zijn inclusief btw, bekeken op Hornbach.nl op 6-11-2026 en gelden alleen als dat erbij staat. Regels met 'Prijs nog opvragen' zijn niet geverifieerd, dus daar noem ik geen bedrag.")]
    rows = [["Artikel", "Art.nr. Hornbach", "Aantal", "Prijs", "Totaal", "Status"]]
    for row in inkoop_uit_excel():
        name, art, q, u, price, tot_, src, st = row
        name = str(name).replace("&", "&amp;")
        if name == "Subtotaal ingevulde prijzen":
            rows.append(["<b>Subtotaal bekende prijzen</b>", "", "", "", f"<b>€{nl(tot_ or 0,2)}</b>", "Exclusief alles met ?"])
        elif name == "Aantal regels zonder prijs":
            rows.append([name, "", "", "", str(tot_), ""])
        elif q is None:
            rows.append([f"<b>{name}</b>", "", "", "", "", ""])
        elif q:   # aantal 0: artikel is bij deze maten niet nodig
            qt = f"{str(q).replace('.', ',')} {u or ''}"
            if price is None:
                rows.append([name, art or "", qt, "?", "?", st or src or ""])
            else:
                rows.append([name, art or "", qt, f"€{nl(price,2)}", f"€{nl(q*price,2)}", st or src or ""])
    Bd += [T(rows, [66, 19, 16, 15, 17, 45])]
    Bd += [Spacer(1, 6), P("<b>Eerst bij Hornbach controleren:</b> geïmpregneerde balk 44 x 69, gebruiksklasse van de spouwlat, gevelfolie, alu-cachering van de PIR en OSB per plaat. Het EPDM wordt op maat gemaakt en kan niet retour, dus bestel het als de dakmaat vaststaat.")]
    Bd += [PageBreak(), P("Stappenplan", "h1")]
    steps = [
        ("Voorbereiding", ["Kies de plek. Houd de voorkant vrij om bij de ramen en de veranda te komen.", "Bespreek met een installateur de voeding, de aardlek en de positie van de thermostaatkast.", "Controleer de gemarkeerde artikelen bij Hornbach en bestel eerst de ramen."]),
        ("Ramen inmeten", ["Meet beide kozijnen na ontvangst op drie plekken in breedte en hoogte. Is een maat anders dan 1000 x 500 of 500 x 500, pas dan het model aan voor je zaagt: de breedte en kamerhoogte van het hele chalet hangen hiervan af.", "Bekijk de scharnierzijde, glaslatten en afwateringssleuven. Monteer de greep en test kiep- en draaistand met het raam omgekeerd op de werkbank."]),
        ("Hout voorbehandelen", ["Zaag volgens zaaglijst. Laat grote platen in de vestiging voorzagen.", f"Hoeklatten: zaag op de tafelzaag eerst tong en groef van de Douglas-plank, dan 4 stroken 58 x 18 en 4 stroken 40 x 18, lang {m.CLAD_Z1-m.CLAD_Z0}. Zet per hoek de smalle kant van de 40-strook tegen de achterkant van de 58-strook, zodat een L van 58 x 58 ontstaat. Lijm met PU-lijm, schroef RVS 4 x 40 om de 250 mm, voorgeboord, en klem tot de lijm hard is. Daarna gronden en beitsen. De hoeklat ligt in hetzelfde vlak als de gevelplanken, die er stomp tegenaan komen; behandel de kopse kanten van de planken.", "Beits vóór montage, binnen en niet onder +8 °C: alle gevelplanken eerst gronden, kopse kanten met kopshoutverzegeling. Beits 2 lagen, op plekken die veel weer vangen 3; 8 uur tussen de lagen. Maak eerst een proefstuk voor de kleur.", "Laat de Elliotis Pine 48 uur acclimatiseren. Schuur de zichtzijde en lak die met TENCO Bootlak blank mat vóór montage, minstens 3 lagen; randen afronden en sealen. Sla hout droog en plat op."]),
        ("Fundering", [f"Kies de plek: achterwand minstens 250 mm van de schutting (dakoverstek 100 mm plus goot). Zet de hartmaten van de poten uit (blad T6): {LEG_DX[0]} en {LEG_DX[1]} mm in de breedte, {LEG_DY} mm in de diepte. Elke staaf moet minstens 50 mm van een tegelvoeg uitkomen; schuif het chalet zo nodig iets op. Controleer of er geen kabels of leidingen lopen.",
                       "Maak een mal: schroef aan een rechte lat 3 korte stukken paal op de hartmaten en bout daaraan de paalhouders. Neem de 3 tegels van de voorste rij uit en boor op de staafplek een gat Ø25 met een diamantboor.",
                       "Graaf 300 x 300 mm, 500 mm diep onder de tegel; op klei 700 mm om opvriezen te voorkomen. Stort beton tot 10 mm onder de onderkant van de tegel. Leg de tegel in een mortelbed op het verse beton, gelijk met de tegels ernaast.",
                       f"Druk de staven door de gaten in het verse beton en steun de lat op blokken. Bodem van de U {m.Z_POST} mm boven de hoogste tegel, waterpas en haaks. Het terras loopt af, dus aan de lage kant steekt de staaf verder uit: er moet overal minstens 90 mm staaf in het beton zitten.",
                       f"Laat uitharden en doe de achterste rij op dezelfde manier. Koppel de tweede lat aan de eerste rij: {LEG_DY} mm hart op hart en gelijke diagonalen. Kit de gaten rond de staven dicht. Laat alles minstens een week uitharden voordat het chalet erop komt.",
                       "Later weghalen: bouten los, staaf onder de tegel doorslijpen en de geboorde tegels vervangen. Het beton blijft onzichtbaar onder het terras."]),
        ("Vloerframe", [f"Bouw frame A plat en controleer de diagonalen ({round(math.hypot(m.XR1-m.F0, m.YB1-m.F0))} mm). Zaag de OSB-onderplaat uit één stuk uit de rest van de dakplaat, 90 graden gedraaid, met sparingen rond de 6 poten. Seal alle randen, lak of beits de onderkant, en schroef de plaat met RVS 4 x 40 onder het frame, zonder kieren. Keer het frame om, leg PIR 70 in de vakken en tape de naden. Zaag elke poot op maat (nominaal {m.Z_LEG-m.Z_POST} mm), zodat de vloer waterpas staat op 5 mm afschot naar voren na. Behandel de zaagvlakken.", "Bout elke poot met 2 RVS bouten M10 door de U en vul de 3 mm speling op met ringen. Zet het frame trekvast op de poten met hoekankers en constructieschroeven.", "Dicht de sparingen rond de poten af, zodat er geen kier voor muizen overblijft. Lijm en schroef de vloerplaat met RVS 4 x 40. Verzegel alle randen."]),
        ("Benedenwanden", ["Bouw wanden C, D, E, F plat op de vloer, met PIR 70 in de vakken van C, D en F, en tape de naden. E blijft zonder PIR. Zaag de doorgang van 190 x 260 uit de 2 platen van wand E, elk uit één stuk, en rond de randen af. Monteer eerst de achterwand met de binnenplaat over de volle breedte, ook beneden uit één stuk, en zet de zijwanden en wand E daar tegenaan: zo heeft de plaat in de hoeken houvast. Zet alles waterpas. Plaats de stijlen van wand B met hoekankers op de vloer.", "Lijm en schroef de wandplaten met RVS 3,5 x 25: voorboren, om de 100 mm, minstens 15 mm uit de rand. Dit maakt het geheel stijf; controleer de haaksheid vóór de lijm uithardt.", f"Zaag de trapbomen: teken de tanden af volgens detail 6 ({round(m.RISE)} x {round(m.RISE)} mm), boor in elke binnenhoek een gat Ø6 tegen scheuren en zaag daarnaartoe, niet erlangs. Er blijft ca. 60 mm hout over, dus zaag niet dieper dan de lijn. Schuur alles glad. Lijm eerst de versterkingsstrook (580 x 30, uit de rest) met PU-lijm op de binnenkant van de rechterboom, langs de rechte onderkant en met schuine uiteinden. Klem en schroef om de 10-15 cm met RVS 3,5 x 20, of kort langere schroeven in: er mag geen punt uitsteken waar de kat langsloopt. Lijm daarna de treden met PU-lijm op de tanden en zet ze vast met RVS 3,5 x 25, voorgeboord, midden in de boomrand. Schroef de linkerboom ook in de wandstijlen. Monteer de trap N tegen de linkerwand en proefpas: die is hierna niet meer uit te nemen."]),
        ("Tussenvloer", ["Maak de cassette G: randen, balken, opvulstrook langs het trapgat (44 x 69 op 25 mm breed rifen), raveel, PIR 70 tussen de balken, onderplaat. Schuur de PIR zo nodig 1 mm vlak. Tape PIR-naden met alu-tape.", "Hef de cassette met twee personen op de benedenwanden. Schroef hem vast en veranker de raamstijlen boven en onder."]),
        ("Bovenwanden", ["Bouw I, J, K met PIR tussen de regels. Tape alle naden. Monteer ze op de vloer. Plaats de twee hoekstijlen van wand H met hoekankers: meer zit er niet in de voorwand.", "Monteer de binnenplaten. Kit de naden en dicht de plaat rond de ventilatiebuis."]),
        ("Plafond en dak", ["Maak de plafondcassette L en schroef die op de wanden. PIR bovenop de plaat.", "Zaag de 5 sporen schuin en schroef ze op de balken. Schroef de OSB-plaat met RVS 4 x 40 op de sporen, met de lange kant dwars erop; rond de hoeken af. Houd de plaat droog tot de EPDM erop zit.", "Lijm de EPDM met Premiumfol Bonding Adhesive volgens de handleiding, bij droog weer boven 5 °C. Dit is contactlijm: smeer plaat en EPDM allebei in, laat afdampen en leg het in één keer goed; op zuigende OSB eerst testen of primer nodig is. Werk de naden af met Adhesive & Sealant. Bevestig boeiboorden, gootje en afvoer.", "Bevestig de daktrim: 11 mm OSB geeft schroeven te weinig houvast, en de wind trekt aan de dakrand. Laat elke schroef doorlopen in het boeiboord. Lukt dat niet, schroef dan een stuk spouwlat onder de dakrand en schroef daarin.", "<b>Het casco is nu regendicht.</b> Laat het droog nakijken voordat je verdergaat."]),
        ("Folie en spouw", ["Breng de folie aan op alle gevels rond het casco, met minstens 100 mm overlap en boven over onder. Neem de folie mee in de sparingen.", "Spouwlatten volgens bladen T2 en T3, met RVS 4 x 40 om de 300 mm. Een lat mag uit meerdere stukken bestaan: 10 latten van 2500 zijn genoeg (samen 20,3 m nodig). Leg elke naad op hout, met minstens 2 schroeven per stuk, geen stukken korter dan 300 mm, en verdeel de naden over de hoogte. Behandel de zaagvlakken. Op de achterwand beneden staan de latten niet recht voor de stijlen: schroef daar alleen waar een regel of stijl achter de lat zit, niet in de PIR. Laat onder en boven open en dek af met stroken RVS-gaas van ca. 40 mm breed, in een L gevouwen. Draag handschoenen; geen uitstekende draadjes."]),
        ("Ramen", ["Zaag het lekdorpelprofiel op 1070 en 600 mm en maak de randen glad. Zet de staande zijde tegen de voorkant van de band, met de bovenkant gelijk met de vloer en de schuine zijde naar buiten. Niet hoger, anders staat het kozijn scheef. Voorboor en schroef met RVS 3,5 x 25 om de 200 mm en kit de gaten. Kit ook de open kopjes dicht.", "Lijm de EPDM op de vloerplaat, over de bovenrand van de band en langs de staande zijde omlaag, tot minstens 10 mm op de schuine zijde. Laat achter een rand van 30 mm vrij, die straks achter het kozijn omhoog komt. Geen stelblokjes en geen dorpellat: het kozijn staat direct op de EPDM.", "Plaats het raam binnenstebuiten, kozijn gelijk met de gevel, waterpas en haaks, met de zijkanten gelijk met de binnenplaten. Zet het tijdelijk vast met wiggen. Vul bij elk bevestigingspunt drukvast op: wig 6 mm plus 3 mm in de zijvoeg van 9 mm, wig 6 mm in de kopvoeg van 5 mm. Meet of het kozijn recht blijft.", f"Bevestig met kozijnschroeven 7,5 x 112, Torx T30, voorgeboord, op ongeveer 55 mm van de gevel: maximaal 150 mm uit de binnenhoeken en maximaal 600 mm onderling, bij voorkeur bij de sluitpunten. Bovenraam: 2 per zijkant en 3 boven. Onderraam: 2 per zijkant en 2 boven. Niet door de onderkant: dat doorboort de EPDM. Controleer de bediening en stel het beslag zo nodig af. Verlijm de EPDM-rand tegen de achterkant van het kozijn.", "Compriband aan de buitenkant van de zijvoegen, kit in de kopvoeg, op glaslatten en naden. Vul de rest van de voeg volledig met weinig PU-vulschuim of minerale wol en laat het raam vast staan tot het schuim hard is; niet dichtkitten wat water moet afvoeren. Controleer of de vleugel vrij langs de dorpel draait. Controleer bediening en blokkeer of beveilig de kiepstand."]),
        ("Gevel", [f"Monteer van onder naar boven, tong omhoog. De bovenste rij is een gerifte strook van {m.TOP_STRIP} mm. Hoeklatten en kader volgens blad T2. Plaats de regenluifel tussen de hoeklatten op 5 RVS consoles, op ca. 30 cm afstand, 12 mm aflopend naar voren en met de achterkant tegen de band; kit die naad. Lijm een EPDM-rest over de bovenkant, met een druiprand aan de voorkant. Laat de lekdorpel van het bovenraam erboven vrij drupen.", "Bevestig met RVS 4 x 40 op de spouwlatten; voorboren aan de plankeinden. Controleer of de vleugels vrij blijven draaien."]),
        ("Ventilatie en elektra", [f"Boor Ø102 (op de buismaat) op x = {m.VENT['x']}, z = {m.VENT['z']}. Plaats de PVC-buis met licht afschot naar buiten en het buitenrooster met een rondje RVS-gaas erachter. Rooster binnen.", "Installateur: voeding, kast, thermostaat, voeler, verwarming, aardlektest.", "Bescherm de kabels volledig, plaats de kap en controleer de temperatuur van de kap na 2 uur vol vermogen."]),
        ("Watertest", ["Spoel beide ramen 15 minuten met een tuinslang, van boven naar beneden, met de ramen dicht.", "Kijk daarna aan de binnenzijde van het kozijn en in de goot. Lekt het, dan eerst dat oplossen."]),
        ("Inwerken", ["Bekleed de treden, plaats mat, mand, hygrometer. Maak alle schroefpunten aan de kat-zijde onschadelijk.", "Test 3 dagen zonder kat: temperatuur, vocht, condens, kap en roosterstand.", "Laat de kat wennen met de voeding op de veranda. Controleer de eerste weken de hygrometer, de goot en de wanden."]),
    ]
    for i, (t, ss) in enumerate(steps, 1):
        Bd.append(KeepTogether([P(f"{i}. {t}", "h2")] + [B(s) for s in ss]))
    Bd += [PageBreak(), P("Onderhoud", "h1")]
    for t in ("Elk jaar voor de winter: kit, EPDM, trim, gootje, gaas en roosters nakijken; hygrometer vergelijken; verwarming en aardlek testen.",
              "Dak: niet op de plaat staan of er een ladder tegen zetten. Maak het schoon vanaf een trap ernaast.",
              "Ramen: elk seizoen de goot en buitennaden controleren, want daar zit het grootste risico. Regelmatig reinigen en het beslag twee keer per jaar smeren.",
              "Gevel: Douglas vraagt om regelmatig bijhouden. Hornbach adviseert onbehandeld Douglas om de 2 jaar te beitsen; voor de Hybride houtbeits noemt Hornbach tot 7 jaar bescherming, afhankelijk van weer en constructie. Controleer jaarlijks en herstel beschadigingen direct.",
              "Binnen: met water en mild schoonmaakmiddel. Lak op tijd bijwerken bij krassen. Geen producten die voor de kat schadelijk zijn."):
        Bd.append(B(t))
    Bd += [P("Bronnen", "h2")]
    for t in (
        "Hornbach-pagina's bekeken op 6-11-2026: kelderraam 12074105, ARON Basic+ 12331530, betonplex 12628592, Elliotis Pine 10000081, TENCO Bootlak 10728553 (met productinformatieblad), Premiumfol Bonding Adhesive 12218370, betonmortel 7195709, PIR 10368509, EPDM 10469549, daktrim 5581276, Douglas 10537457, vuren 5185884 en 5185888, antraciet beits 10277060, folie 7049802. U-paalhouder 3896646 met gegevensblad (as.80179845).",
        "KNMI: Windstotenklimatologie van Nederland (TR-306, 2009), figuren 5 en 7.",
        "ARON Basic+ 70 mm technisch blad en montageaanbeveling RC 1/RC 2 (Hornbach, as.187466783, as.187466663), door mij toegepast op een houten wand en op het kelderraam; maattekening kelderraam (as.91729658).",
        "IKO enertherm: Hornbach-productinformatie. Premiumfol: verwerkingsvoorschrift en handleiding via Hornbach.",
        "Zonneopbrengst: 2 % van jaaropbrengst in december (18 kWh per kWp) tot circa 32 kWh per kWp volgens verschillende Belgische en Britse bronnen; indicatief.",
        "Kiepraam en katten: Dierenbescherming en KNMvD, via AVROTROS Radar en Hart van Nederland.",
        "Binnenstebuiten monteren: geen bron gevonden die dit bevestigt of beschrijft; eigen beoordeling.",
    ):
        Bd.append(B(t))
    doc = SimpleDocTemplate(path_b, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    PART["naam"] = "Deel 3: zaaglijst, inkoop, uitvoering (deel 2 = tekeningen)"
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
    for key, label_ in (("LP9", "Elliotis Pine 9, 2440x1220"), ("BP12", "Betonplex 12, 2500x1250"), ("OSB", "OSB-3 11, 2440x1220"), ("PIR", "PIR 70, 1200x600")):
        for i, sheet in enumerate(NEST[key], 1):
            for x_, y_, w_, h_, nm in sorted(sheet.items, key=lambda it: (it[1], it[0])):
                ws.append([label_, i, nm.replace(":", " "), round(w_), round(h_), round(x_), round(y_)])
    finish(ws)


def main():
    probs = m.collisions() + m.window_clearance()
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
