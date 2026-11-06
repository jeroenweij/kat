"""Genereert het bouwplan (PDF) en de lijsten (XLSX) uit model.py en berekening.py.

Gebruik:  python genereer.py   (vereist reportlab, openpyxl, pypdf)
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
REV = "Rev I"
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
    m.MAT["LAT"]: C("#d8c7a6"), m.MAT["DG"]: C("#8f4f32"), m.MAT["DM"]: C("#8f4f32"), m.MAT["DK"]: C("#3a3f43"),
}
LEGEND = [("R44", "regel 44x44"), ("B69", "balk 44x69"), ("I69", "geïmpr. balk"), ("LP9", "Lightply 9"), ("BP12", "betonplex 12"),
          ("OSB", "OSB-3 18"), ("PIR", "PIR 40"), ("LAT", "spouwlat"), ("DG", "gevel mahonie"), ("DK", "hoek/boei antraciet")]


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
        if kind == "deck":
            return [(y0, m.roof_z(y0)), (y1, m.roof_z(y1)), (y1, m.roof_z(y1) + 18), (y0, m.roof_z(y0) + 18)]
        if p.extra.get("stringer"):
            return [(y0, z0), (y0 + 90, z0), (y1, z1 - 120), (y1, z1), (y0 + 15, z0 + 20)]
        if p.extra.get("trim"):
            return [(y0, z0), (y1, z0), (y1, m.roof_z(y1) + 18), (y0, m.roof_z(y0) + 18)]
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
    """Poeren, paalhouders en maaiveld (schematisch)."""
    for a, b in xs:
        rect(view, (a + b) / 2 - 150, (a + b) / 2 + 150, -280, 0, C("#c9c9c9"))
        rect(view, a + 15, b - 15, 0, 80, C("#8d979c"))
    u0 = min(a for a, _ in xs) - 250
    u1 = max(b for _, b in xs) + 250
    x0, y0 = view.p(u0, -30)
    x1, y1 = view.p(u1, -30)
    view.c.setStrokeColor(C("#5b7a4a"))
    view.c.setLineWidth(0.8)
    view.c.setDash(3, 2)
    view.c.line(x0, y0, x1, y1)
    view.c.setDash()


def window_front(view, w, sight):
    rect(view, w["x0"] - 10, w["x1"] + 10, w["z0"] - 10, w["z1"] + 10, C("#6a7780"))
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
    foot(view, "y", [(40, 108), (792, 860)])


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
    foot(view, "y", [(40, 108), (792, 860)])


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
        return p.name in ("Binnenplaat veranda", "Plaat verandazijde voor", "Plaat verandazijde achter",
                          "Plaat verandazijde boven opening", "Onderplaat tussenvloer") or p.group[0] == "F"
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


def bars(items, stock, kerf=4):
    items = sorted(items, key=lambda i: -i[0])
    out = []
    for l, name in items:
        for bar in out:
            if bar["left"] >= l + kerf:
                bar["cuts"].append((l, name))
                bar["left"] -= l + kerf
                break
        else:
            if l > stock:
                raise ValueError(f"{name} {l} langer dan {stock}")
            out.append({"cuts": [(l, name)], "left": stock - l})
    return out


def collect():
    rows = m.cutlist()
    by = defaultdict(list)
    for r in rows:
        for _ in range(r["qty"]):
            by[r["mat"]].append(r)
    res = {}
    short = lambda r: r["group"][0] + ":" + r["name"]
    for key, stock in (("R44", 2400), ("B69", 2400), ("I69", 2400), ("P69", 1800), ("LAT", 2400)):
        res[key] = bars([(r["dims"][0], short(r)) for r in by[m.MAT[key]]], stock)
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
    v = View(c, 22, 214, 2)
    rect(v, 0, 18, 0, 110, wood)
    rect(v, 18, 40, 45, 89, lat)
    rect(v, 40, 84, 0, 44, stud)
    rect(v, 40, 80, 44, 110, pir)
    rect(v, 84, 93, 0, 110, ply)
    c.setStrokeColor(C("#2a6fb0"))
    c.setLineWidth(0.8)
    x0, y0 = v.p(40, 0)
    x1, y1 = v.p(40, 110)
    c.line(x0, y0, x1, y1)
    leader(v, 9, 100, 80, 270, "Gevelplank 18 (Douglas, werkende breedte 135)")
    leader(v, 29, 60, 80, 262, "Spouwlat 22x44; spouw onder en boven open met RVS gaas")
    leader(v, 40, 92, 80, 254, "Dampopen waterkerende folie op de regels, overlap 100")
    leader(v, 60, 80, 80, 246, "PIR 40 alu; naden met alu-tape, luchtdicht aan regels")
    leader(v, 82, 20, 80, 238, "4 mm spleet tussen PIR en plaat (geen extra dampfolie)")
    leader(v, 88, 40, 80, 230, "Lightply 9: gelijmd, geschroefd, gegrond en gelakt")
    dim(v, 0, 0, 18, 0, -5, "18", 5.5)
    dim(v, 18, 0, 40, 0, -5, "22", 5.5)
    dim(v, 40, 0, 84, 0, -5, "44", 5.5)
    dim(v, 84, 0, 93, 0, -5, "9", 5.5)
    dim(v, 0, 0, 93, 0, -11, "93", 6)
    label(c, 80, 197, "Dampdicht binnen, dampopen buiten: droogt naar buiten.", 5.8)
    label(c, 80, 193, "Plaat draagt niets, maar schoort wel: schroef om de 100.", 5.8)

    # 2 raam onderaansluiting
    detail_box(c, 148, 188, 130, 94, "2  Raam binnenstebuiten, onderkant, verticaal (1:3)")
    v = View(c, 170, 220, 3)
    rect(v, 40, 84, -81, -12, beam)           # rand tussenvloer
    rect(v, 40, 110, -12, 0, floor18)         # vloerplaat
    rect(v, 0, 18, -81, 0, wood)              # band
    rect(v, 18, 40, -81, -37, lat)
    rect(v, 0, 18, 0, 22, wood)               # kader onder raam
    rect(v, 18, 40, 0, 22, lat)
    rect(v, 40, 84, 0, 22, lat)               # dorpelregel
    rect(v, 84, 93, 0, 30, ply)               # opstand
    poly(v, [(-8, 22), (84, 22), (84, 33), (94, 33), (94, 30), (87, 30), (87, 25), (-8, 25)], tray, lw=0.2)
    rect(v, 4, 66, 25, 30, foam, lw=0.2)      # stelblokjes
    rect(v, 0, 71, 30, 130, colors.white, lw=0.5)   # kozijn
    rect(v, -19, 0, 62, 130, colors.white, lw=0.3)  # vleugel, nu buiten
    rect(v, -8, 16, 130, 150, C("#bfdcec"))
    poly(v, [(-34, 16), (0, 26), (0, 29), (-34, 19)], alu, lw=0.3)
    leader(v, -10, 110, 214, 272, "Vleugel 19 naar buiten; draait en kiept naar buiten")
    leader(v, 36, 100, 214, 266, "Kozijn 71 diep, gelijk met gevel. Greep zit nu buiten")
    leader(v, 88, 28, 214, 260, "Opstand 30 onder de EPDM houdt water uit de kamer")
    leader(v, 44, 23, 214, 254, "EPDM-goot over dorpelregel, afschot naar buiten")
    leader(v, -20, 22, 214, 248, "Alu lekdorpel: overstek 34 met druipneus")
    leader(v, 62, 11, 214, 242, "Dorpelregel 22 hoog, stelblokjes 8: raam vrij van vloer")
    label(c, 214, 232, "Sparing 1020 x 540 hoog, beneden 520 x 540.", 6.3, True)
    label(c, 214, 228, "Vloerrand en plafondrand zijn de boven- en onderdorpel.", 6)
    label(c, 214, 224, "Bevestigen via de zijkanten: max. 150 uit de hoeken,", 6)
    label(c, 214, 220, "max. 600 h.o.h., min. 60 in de stijl. Kozijn raakt", 6)
    label(c, 214, 216, "de stijl over 31 mm: voorboren, klossen, niet krom trekken.", 6)
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
    poly(v, [(-150, base + ztop(-150)), (250, base + ztop(250)), (250, base + ztop(250) + 18), (-150, base + ztop(-150) + 18)], FILL[m.MAT["OSB"]])
    rect(v, -132, -15, base - m.SOF_T, base, floor18)
    rect(v, -150, -132, base - 33, base + 75, dark)
    leader(v, 100, base + 62, 286, 272, "EPDM 1,2 op OSB-3 18; afschot 1:40 naar achter")
    leader(v, 40, base + 30, 286, 266, "Ventilatieruimte 28-57 tussen sporen, voor en achter open")
    leader(v, -8, base - 3, 286, 260, "Spleet 15 mm met RVS gaas: spouw en dak ventileren hier")
    leader(v, 120, m.PLY + 20, 286, 254, "PIR 40 op plafondplaat; plafond Lightply 9")
    leader(v, -141, base + 50, 286, 248, "Boeiboord en alu daktrim met druiprand")
    dim(v, -150, -5, 0, -5, -5, "150", 5.8)

    # 4 fundering
    detail_box(c, 14, 92, 130, 92, "4  Fundering (1:6, poer afgebroken getekend)")
    v = View(c, 45, 127, 6)
    rect(v, -150, 150, -200, 0, grey)
    rect(v, -20, 20, 0, 80, C("#8d979c"))
    rect(v, -34, 34, 80, 180, FILL[m.MAT["P69"]])
    rect(v, -60, 150, 180, 249, FILL[m.MAT["I69"]])
    rect(v, -60, 150, 249, m.Z_DECK, floor18)
    rect(v, -100, -82, m.CLAD_Z0, m.Z_DECK, wood)
    x0, y0 = v.p(-190, -30)
    x1, y1 = v.p(190, -30)
    c.setStrokeColor(C("#5b7a4a"))
    c.line(x0, y0, x1, y1)
    label(c, 16, 117, "maaiveld", 5.5)
    leader(v, 0, -120, 90, 116, "Poer 300x300x500, 6 stuks; op klei 700 diep (vorstvrij)")
    leader(v, 0, 40, 90, 123, "Verstelbare paalhouder 70x70, 30-150, thermisch verzinkt")
    leader(v, 0, 130, 90, 130, "Poot 68x68, zaagvlak behandelen; maat op locatie stellen")
    leader(v, 80, 215, 90, 138, "Vloerframe 44x69 geïmpregneerd")
    leader(v, 80, 255, 90, 146, "Betonplex 12, afschot 5 mm naar voren")
    dim(v, 150, 0, 150, 180, 4, "180", 5.8)
    label(c, 72, 98, "Elke poot trekvast verankeren: kantelgevaar bij storm.", 6.3, True)

    # 5 raam kop
    detail_box(c, 148, 92, 130, 92, "5  Raam binnenstebuiten, bovenkant beneden, verticaal (1:3)")
    v = View(c, 184, 126, 3)
    rect(v, 40, 84, 19, 88, beam)              # rand tussenvloer
    rect(v, 40, 84, 10, 19, ply)               # onderplaat (bovenkant raam + 10)
    rect(v, 40, 84, 88, 100, floor18)
    rect(v, 0, 18, 10, 100, wood)              # band
    rect(v, 18, 40, 10, 54, lat)
    rect(v, 0, 71, -90, 0, colors.white, lw=0.5)
    rect(v, -19, 0, -90, -6, colors.white, lw=0.3)
    rect(v, -90, 0, 22, 40, wood)              # luifel
    poly(v, [(-96, 19), (2, 42), (2, 45), (-96, 22)], alu, lw=0.3)
    rect(v, 0, 71, 0, 10, foam, lw=0.2)
    leader(v, -45, 36, 214, 174, "Regenluifel 18x100, alu kap met druipneus (alleen beneden)")
    leader(v, 8, 30, 214, 168, "Band tussenvloer met spouwlat; boven dicht tegen de EPDM")
    leader(v, 35, 5, 214, 162, "Kop 10 mm: compriband, folie omzetten over het kozijn")
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
    poly(v, [(h0, 0), (h0 + 90, 0), (depth, climb - 120), (depth, climb), (h0 + 15, 20)], floor18)
    for i in range(m.N_RISE - 1):
        z = m.RISE * (i + 1)
        y = h0 + m.TREAD * i
        rect(v, y, y + m.TREAD - 4, z - 12, z, C("#7f5a34"))
    dim(v, h0, m.RISE, h0 + m.TREAD, m.RISE, 4, str(round(m.TREAD)), 5.5)
    dim(v, depth, 0, depth, climb, 5, str(climb), 5.5)
    dim(v, h0, -12, depth, -12, -3, str(depth - h0), 5.5)
    label(c, 290, 97.5, f"{m.N_RISE} optreden van {round(m.RISE)}, {m.N_RISE-1} tredes {round(m.TREAD)} x {round(m.ST_X1-m.ST_X0-24)}, helling 39°. Tredes met sisal", 6.3)
    label(c, 290, 94.5, "of rubbermat. Plaats de trap voordat de tussenvloer erop gaat.", 6.3)

    # 7 ventilatie
    detail_box(c, 14, 28, 196, 60, "7  Ventilatie (natuurlijke trek)")
    label(c, 18, 78, f"Afvoer: PVC Ø75 door de achterwand, hart z = {m.VENT['z']} (94 onder het plafond), x = {m.VENT['x']}.", 6.5)
    label(c, 18, 74, "Binnen: regelbaar rooster Ø75. Buiten: afvoerkap met afschot naar buiten en RVS gaas, gaasmaas 3-4 mm.", 6.5)
    label(c, 18, 70, "Aanvoer: open voorkant -> veranda -> doorgang 190 x 260 -> trapkamer -> trapgat 247 x 367.", 6.5)
    label(c, 18, 66, "De afvoer zit rechtsachter en het trapgat linksachter: de lucht loopt langs de achterwand, niet over het bed bij het raam.", 6.5)
    label(c, 18, 60, "Stand rooster: vorst bijna dicht (circa 2 m³/h volstaat), 0-5 °C half open, boven 5 °C helemaal open.", 6.5, True)
    label(c, 18, 56, "Hygrometer in de bovenkamer. Blijft de luchtvochtigheid langdurig boven 75-80 %: rooster verder open of", 6.5)
    label(c, 18, 52, "een kleine 12 V-ventilator op hygrostaat op het binnenrooster (Ø75 past daarvoor).", 6.5)

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
    for key, name, sw, sh_ in (("BP12", "Betonplex 12 mm, 2500x1250", 2500, 1250), ("OSB", "OSB-3 18 mm, 2440x1220", 2440, 1220), ("LP9", "Lightply 9 mm, 2440x1220", 2440, 1220), ("PIR", "PIR 40 mm, 1200x600", 1200, 600)):
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
    label(c, 195, 46, f"Hoofdmaten: buiten 1300 x 900, hoogte {round(m.Z_TOP)} (bovenkant dak voor), dak 1500 x 1150.", 7.5, True)
    label(c, 195, 41, f"Bovenkamer binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Trapkamer {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H}. Veranda vrij {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H}.", 7.5)
    label(c, 195, 36, f"Raam boven 1000 x 500, beneden 500 x 500, beide binnenstebuiten. Totaalgewicht ongeveer {round(R['mass'])} kg.", 7.5)

    # T2 aanzichten voor/achter
    sh.new("Aanzichten voor en achter", "1:10")
    v = View(c, 40, 72, 10)
    view_title(c, 40, 262, "Vooraanzicht")
    front_view(v)
    dim(v, 0, 0, 1300, 0, -34, "1300")
    dim(v, -100, m.Z_TOP, 1400, m.Z_TOP, 4, "1500 dak")
    dim(v, -100, 0, -100, m.Z_TOP, -8, str(round(m.Z_TOP)))
    for w, t in ((m.WIN_U, "Raam 1000 x 500, sparing 1020 x 540"), (m.WIN_L, "Raam 500 x 500")):
        x_, y_ = v.p((w["x0"] + w["x1"]) / 2, (w["z0"] + w["z1"]) / 2)
        c.setFillColor(INK)
        c.setFont("D", 6)
        c.drawCentredString(x_, y_ - 2, t)
    dim(v, 1400, 0, 1400, m.Z_DECK, 4, str(m.Z_DECK))
    dim(v, 1400, m.Z_DECK, 1400, m.Z_L_TOP, 4, room_lbl)
    dim(v, 1400, m.Z_L_TOP, 1400, m.Z_UP, 4, str(m.Z_UP - m.Z_L_TOP))
    dim(v, 1400, m.Z_UP, 1400, m.Z_U_TOP, 4, room_lbl)
    dim(v, 1400, m.Z_U_TOP, 1400, m.Z_TOP, 4, str(round(m.Z_TOP - m.Z_U_TOP)))
    dim(v, m.VER_X0, m.Z_DECK, m.IN_X1, m.Z_DECK, 5, f"{m.IN_X1-m.VER_X0} vrij", 6)
    v = View(c, 370, 72, 10, flip=True)
    view_title(c, 225, 262, "Achteraanzicht (van achteren gezien)")
    back_view(v)
    dim(v, 0, 0, 1300, 0, -34, "1300")
    dim(v, -100, 0, -100, top, 8, str(top))
    legend(c, 18, 28)
    label(c, 110, 28, "Hoeklatten en boeiboorden in antraciet beits, de rest van de gevel met kader en band in mahonie beits; bij beide blijft de houtnerf zichtbaar. Plankmaten: zie zaaglijst. Boven de lage ramen zit de regenluifel.", 7)

    # T3 aanzichten zijkanten
    sh.new("Aanzichten zijkanten", "1:10")
    v = View(c, 165, 72, 10, flip=True)
    view_title(c, 45, 262, "Linkeraanzicht (voorzijde rechts), geen openingen")
    side_view(v, "L")
    dim(v, 0, 0, 900, 0, -34, "900")
    dim(v, -150, m.Z_TOP, 1000, m.Z_TOP, 3, "1150 dak")
    v = View(c, 240, 72, 10)
    view_title(c, 225, 262, "Rechteraanzicht (voorzijde links), geheel dicht")
    side_view(v, "R")
    dim(v, 0, 0, 900, 0, -34, "900")
    dim(v, 1000, 0, 1000, top, 4, f"achter {top}")
    legend(c, 18, 28)

    # T4 doorsneden
    sh.new("Doorsneden A en B", "1:10")
    v = View(c, 60, 72, 10)
    view_title(c, 45, 262, "A-A: door trap, trapgat en bovenkamer (x = 215)")
    section_x(v, 215)
    dim(v, m.IN_Y0, m.Z_U_TOP, m.IN_Y1, m.Z_U_TOP, -6, f"{m.IN_Y1-m.IN_Y0} binnen", 6)
    dim(v, 860, m.Z_DECK, 860, m.Z_L_TOP, 6, room_lbl)
    dim(v, 860, m.Z_UP, 860, m.Z_U_TOP, 6, room_lbl)
    dim(v, m.HOLE_Y0, m.Z_UP, m.HOLE_Y1, m.Z_UP, 5, f"trapgat {m.HOLE_Y1-m.HOLE_Y0}", 6)
    v = View(c, 240, 72, 10)
    view_title(c, 225, 262, "B-B: door veranda en bovenkamer (x = 900)")
    section_x(v, 900)
    dim(v, 0, m.Z_DECK, m.IN_Y1, m.Z_DECK, 5, f"{m.IN_Y1} vrij", 6)
    dim(v, 860, 0, 860, m.Z_LEG, 6, str(m.Z_LEG))
    dim(v, 860, m.Z_LEG, 860, m.Z_DECK, 6, str(m.Z_DECK - m.Z_LEG))
    dim(v, 860, m.Z_L_TOP, 860, m.Z_UP, 6, str(m.Z_UP - m.Z_L_TOP))
    dim(v, 860, m.Z_U_TOP, 860, m.Z_RAFT, 6, str(m.Z_RAFT - m.Z_U_TOP))
    legend(c, 18, 28)

    # T5 doorsneden C/D
    sh.new("Doorsneden C en D", "1:10")
    v = View(c, 40, 72, 10)
    view_title(c, 40, 262, "C-C: door de ramen, kijkrichting achter (y = 30)")
    section_y(v, 30)
    dim(v, 140, m.Z_UP, 1160, m.Z_UP, 8, "sparing 1020", 6)
    dim(v, 84, m.Z_DECK, m.PART_X0, m.Z_DECK, 8, "sparing 520", 6)
    v = View(c, 225, 72, 10)
    view_title(c, 225, 262, "D-D: door doorgang en trap, kijkrichting achter (y = 690)")
    section_y(v, 690)
    dim(v, m.IN_X0, m.Z_U_TOP, m.IN_X1, m.Z_U_TOP, -6, f"{m.IN_X1-m.IN_X0} binnen", 6)
    dim(v, m.IN_X0, m.Z_DECK, m.ROOM_X1, m.Z_DECK, 5, f"{m.ROOM_X1-m.IN_X0} binnen", 6)
    dim(v, m.VER_X0, m.Z_DECK, m.IN_X1, m.Z_DECK, 5, str(m.IN_X1 - m.VER_X0), 6)
    legend(c, 18, 28)

    # T6 plattegronden
    sh.new("Plattegronden", "1:10")
    v = View(c, 40, 158, 10)
    view_title(c, 40, 262, "Beneden, snede z = 500")
    plan(v, 500)
    dim(v, 0, 0, 1300, 0, -6, "1300", 6)
    dim(v, 0, 0, 0, 900, -6, "900", 6)
    dim(v, m.IN_X0, m.IN_Y1, m.ROOM_X1, m.IN_Y1, 8, str(m.ROOM_X1 - m.IN_X0), 6)
    dim(v, m.VER_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 8, str(m.IN_X1 - m.VER_X0), 6)
    dim(v, m.VER_X0, m.CAT_Y0, m.VER_X0, m.CAT_Y1, 7, "190", 5.5)
    label(c, 40, 257.5, "Trap langs de linkerwand, doorgang 190 x 260 achterin, voorkant veranda open, rechterwand dicht.", 6.5)
    v = View(c, 225, 158, 10)
    view_title(c, 225, 262, "Boven, snede z = 1200")
    plan(v, 1200)
    dim(v, 0, 0, 1300, 0, -6, "1300", 6)
    dim(v, m.IN_X0, m.IN_Y1, m.IN_X1, m.IN_Y1, 8, str(m.IN_X1 - m.IN_X0), 6)
    dim(v, m.IN_X1, m.IN_Y0, m.IN_X1, m.IN_Y1, 7, str(m.IN_Y1 - m.IN_Y0), 6)
    dim(v, m.HOLE_X0, m.HOLE_Y1, m.HOLE_X1, m.HOLE_Y1, -17, f"gat {m.HOLE_X1-m.HOLE_X0}", 5.5)
    label(c, 225, 257.5, "Raam voor, trapgat linksachter, afvoer rechtsachter, verwarming rechterwand, mand bij het raam.", 6.5)
    v = View(c, 40, 46, 10)
    view_title(c, 40, 140, "Vloerframe, gezien van boven (vloerplaat weg)")
    plan(v, m.Z_DECK0 - 1, only=lambda p: p.group.startswith("A"))
    xs = [84, 322, 366, 604, 648, 910, 954, 1216]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, 860, b, 860, 4, size=5.3)
    dim(v, 40, 40, 1260, 40, -5, "1220", 6)
    v = View(c, 225, 46, 10)
    view_title(c, 225, 140, "Tussenvloer: balken en PIR (bovenplaat weg)")
    plan(v, m.Z_MID_T - 1, only=lambda p: p.group.startswith("G") and "plaat" not in p.name.lower())
    xs = [84, 340, 384, 604, 648, 910, 954, 1216]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, 860, b, 860, 4, size=5.3)
    dim(v, 40, 40, 1260, 40, -5, "1220", 6)
    legend(c, 18, 28)

    # T7 dakplattegronden
    sh.new("Plafond en dak", "1:10")
    v = View(c, 45, 158, 10)
    view_title(c, 40, 262, "Plafond: balken en PIR (van boven)")
    plan(v, m.Z_RAFT - 1, only=lambda p: p.group.startswith("L"))
    xs = [84, 334, 378, 628, 672, 922, 966, 1216]
    for a, b in zip(xs, xs[1:]):
        dim(v, a, 860, b, 860, 4, size=5.3)
    dim(v, 40, 40, 1260, 40, -5, "1220", 6)
    v = View(c, 245, 150, 10)
    view_title(c, 225, 262, "Dak: sporen en overstek (dakplaat weg)")
    plan(v, m.Z_RAFT + 70, only=lambda p: p.group.startswith("M") and p.mat != m.MAT["OSB"])
    dim(v, -100, -150, 1400, -150, -5, "1500", 6)
    dim(v, -100, -150, -100, 1000, -6, "1150", 6)
    dim(v, 0, 1000, 40, 1000, 4, size=5.3)
    v = View(c, 45, 45, 10)
    view_title(c, 40, 62, "Spoor, zijaanzicht (5 stuks)")
    poly(v, [(0, 0), (1150, 0), (1150, m.RAFT_B), (0, m.RAFT_F)], FILL[m.MAT["B69"]], lw=0.4)
    dim(v, 0, 0, 1150, 0, -5, "1150", 6)
    dim(v, 0, 0, 0, m.RAFT_F, -5, str(m.RAFT_F), 5.5)
    dim(v, 1150, 0, 1150, m.RAFT_B, 4, str(m.RAFT_B), 5.5)
    label(c, 110, 36, "Uit balk 44x69: schuine zaagsnede. Afschot 1:40 naar de achterkant. Dakgoot achter met afvoer op grind.", 7)
    legend(c, 18, 28)

    # T8, T9 wanden
    walls_page(sh, "Wandframes beneden", [
        ("B Voorwand beneden", "x", 40, 648, "B  Voorwand beneden, 608 breed (sparing 520 x 540)", False),
        ("C Achterwand beneden", "x", 40, 1260, "C  Achterwand beneden, 1220 lang", False),
        ("D Linkerwand beneden", "y", 84, 816, "D  Linkerwand beneden, 732 lang", False),
        ("E Scheidingswand", "y", 84, 816, "E  Scheidingswand, 732 lang (doorgang 190 x 260)", False),
        ("F Rechterwand beneden", "y", 40, 816, "F  Rechterwand beneden, 776 lang, geheel dicht", False),
    ])
    walls_page(sh, "Wandframes boven", [
        ("H Voorwand boven", "x", 40, 1260, "H  Voorwand boven, 1220 breed (sparing 1020 x 540)", False),
        ("I Achterwand boven", "x", 40, 1260, "I  Achterwand boven, 1220 lang", False),
        ("J Linkerwand boven", "y", 84, 816, "J  Linkerwand boven, 732 lang", False),
        ("K Rechterwand boven", "y", 84, 816, "K  Rechterwand boven, 732 lang", False),
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
        ("LIGHTPLY Multiplex ongegrond 2440x1220x9 (art. 12575686)", n["LP9"], "pl", 22.49, H, "Gecontroleerd; geen reserve: bij een zaagfout een kleine plaat 1220x610 (art. 12575693, €10,25) bijkopen"),
        ("Betonplex Acacia 2500x1250x12 (art. 12628592)", n["BP12"], "pl", 57.49, H, "Gecontroleerd; vloeren, trap en overstek"),
        ("OSB-III 2440x1220x18 T&G (art. 6800343)", n["OSB"], "pl", None, C_, "Artikel gevonden; verkocht per plaat of pak controleren"),
        ("Douglas 18x145x3000 tand-en-groef (art. 10537457), gevel + kader", n["DG"] + n["DK"] + 2, "st", 11.59, H, "Gecontroleerd; werkende breedte ca. 135"),
        ("Isolatie en folie", None, None, None, None, None),
        ("IKO PIR 40 Rd 1,80, pak 12 st = 8,64 m² (art. 10368506)", 1, "pak", 113.84, H, f"Gecontroleerd; {n['PIR']} platen nodig. Alu-cachering in vestiging bevestigen"),
        ("Dampopen waterkerende gevelfolie, Sd ≤ 0,1 m, ca. 10 m²", 1, "rol/stuk", None, C_, "Niet gevonden bij Hornbach; vestiging vragen of bouwmarkt"),
        ("Alu-tape PIR, 50 mm", 1, "rol", None, C_, ""),
        ("RVS insectengaas, maas 3-4 mm", 1, "rol", None, C_, ""),
        ("Compriband passend bij voeg 10 mm", 1, "rol", None, C_, "6 m nodig"),
        ("Dak", None, None, None, None, None),
        ("Premiumfol EPDM 1,2 mm, breedte 2,8 m, per m (art. 10469549)", 1.5, "m", 38.92, H, "Gecontroleerd; maatwerk: geen retour. Reststrook is de goot onder de ramen"),
        ("EPDM-lijm en kit (Premiumfol/Berdal)", 1, "set", None, C_, "Spray 6-8 m² per bus volgens datablad"),
        ("SOLOTRIM daktrim alu 60x55, 2500 (art. 5581276)", 3, "st", 49.95, H, "Gecontroleerd; schroeven en neopreen ringen los"),
        ("Hoekstukken daktrim", 4, "st", None, C_, ""),
        ("Dakgoot 1,5 m met afvoer, hangers en grindbak", 1, "set", None, C_, ""),
        ("Ramen", None, None, None, None, None),
        ("Kelderraam 100x50 draai/kiep links RAL9016 (art. 12074105)", 1, "st", 94.50, H, "Gecontroleerd; geen greep meegeleverd"),
        ("ARON Basic+ 50x50 DK links (art. 12331530)", 1, "st", 109.00, H, "Gecontroleerd; geen greep meegeleverd"),
        ("Afsluitbare raamgreep", 2, "st", None, C_, "Zit buiten, dus afsluitbaar. Passing bij aankoop controleren"),
        ("Kiepbeveiliging voor katten, of kiepstand blokkeren", 2, "st", None, C_, "Zie veiligheid"),
        ("Alu lekdorpel, 1040 en 540 lang, met eindkapjes", 2, "st", None, C_, ""),
        ("Kit voor buitenaansluitingen en glaslatten, buitenkwaliteit", 1, "set", None, C_, "Geschikt voor kunststof"),
        ("Alu kap en 3 RVS consoles voor regenluifel", 1, "set", None, C_, ""),
        ("Fundering", None, None, None, None, None),
        ("Beton 25 kg (6 poeren 300x300x500 = 270 liter)", 24, "zak", None, C_, "Hoeveelheid van verpakking afhankelijk; meer op klei"),
        ("Paalhouder 70x70 verstelbaar 30-150 (GAH Alberts, art. 6424538)", 6, "st", 11.90, "Hornbach, zoekresultaat", "Trekvast in verse poer zetten; prijs controleren"),
        ("Verwarming en elektra", None, None, None, None, None),
        ("Buisverwarming 120 W (of 2x60 W) met maximaalthermostaat, IP44", 1, "st", None, C_, "Geschikt model niet bij Hornbach gevonden"),
        ("Digitale thermostaat, kast IP65, mantelbuis, voeler", 1, "set", None, C_, "Installateur kiest onderdelen"),
        ("Stalen beschermkap voor verwarming (geperforeerd)", 1, "st", None, C_, "Op maat, afhankelijk van model"),
        ("Installateur buitenaansluiting met aardlek", 1, "post", None, "Offerte", "Afhankelijk van afstand tot meterkast"),
        ("Ventilatie en meting", None, None, None, None, None),
        ("PVC-buis Ø75, 30° bocht of afvoerkap, RVS gaas", 1, "set", None, C_, ""),
        ("Regelbaar rooster Ø75", 1, "st", None, C_, ""),
        ("Hygrometer met geheugen", 1, "st", None, C_, ""),
        ("Afwerking en bevestiging", None, None, None, None, None),
        ("Remmers HK-Lazuur (gevel, houtnerf zichtbaar), 2,5 l", 1, "blik", None, C_, "Hoeveelheid volgens verbruik op blik"),
        ("Jotun Demidekk donker (kader), 1 l, plus grondverf", 1, "set", None, C_, ""),
        ("Houtprimer en watergedragen lak voor Lightply", 1, "set", None, C_, "Afwasbaar; veiligheidsblad controleren op geschiktheid"),
        ("Waterdichte bouwlijm PU/D4; randsealer voor plaatmateriaal", 1, "set", None, C_, "Lightply schrijft randen afronden en sealen voor"),
        ("RVS schroeven 3,5x25, 4x40, 4x60; constructieschroeven 5x80, hoekankers", 1, "set", None, C_, "Alles buiten: RVS of A2"),
        ("Kozijnschroeven of raamankers", 1, "set", None, C_, "Via kozijn, schroef min. 60 in hout"),
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
             ["Buitenmaat", f"1300 x 900 x {round(m.Z_TOP)} mm, dak 1500 x 1150 mm"],
             ["Bovenkamer", f"Binnen {m.IN_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H} mm. Raam 100 x 50. Vloer, wanden en plafond geïsoleerd met PIR 40 mm."],
             ["Trapkamer", f"Binnen {m.ROOM_X1-m.IN_X0} x {m.IN_Y1-m.IN_Y0} x {m.ROOM_H} mm. Raam 50 x 50. Niet geïsoleerd. Trap langs de linkerwand, helling 39°, 7 optreden van 90 mm."],
             ["Veranda", f"Kamer met open voorkant, {m.IN_X1-m.VER_X0} x {m.IN_Y1} x {m.ROOM_H} mm. Zijkant dicht. Doorgang naar de trapkamer 190 x 260 mm."],
             ["Toegang", "Via de ramen, die binnenstebuiten zijn gemonteerd en vanaf buiten opengaan. Geen luiken."],
             ["Wandbekleding", "Lightply 9 mm, 2 platen 2440 x 1220 (Hornbach, voor binnen), gelijmd, geschroefd, gegrond en gelakt. Ook plafond en onderkant tussenvloer, beide uit één stuk."],
             ["Vloeren en trap", "Betonplex 12 mm (art. 12628592). Ook de trap en de onderkant van het dakoverstek."],
             ["Verwarming", f"Netstroom met thermostaat, 120 W buisverwarming achter beschermkap. Piek berekend op {round(r['peak'])} W bij -5 °C. Circa {round(r['kwh'])} kWh per winter."],
             ["Ventilatie", "PVC Ø75 met regelbaar rooster, aanvoer via trapgat. Ø40 is te weinig (zie berekening)."],
             ["Fundering", "6 betonpoeren met verzinkte paalhouders; trekvast. Vrije hoogte onder vloer 180 mm."],
             ["Materiaal", "Vooral Hornbach. Gevel Douglas 18 x 145 met Hornbach Hybride houtbeits mahonie, hoeklatten en boeiboorden in Hybride houtbeits RAL 7016 antraciet; dak EPDM."],
             ], [33, 145])]
    A += [P("Jouw keuzes", "h2")]
    for t in (
        "<b>Geen toegangsluiken.</b> De ramen zijn de toegang en zitten binnenstebuiten, gelijk met de gevel.",
        f"<b>Kamers van 540 mm hoog.</b> Raam 500, plus 30 opstand onder en 10 voeg boven. De regels vervallen bij de ramen; vloer en plafond nemen die rol over. Totale hoogte daardoor {round(m.Z_TOP)} mm, onder de 1650-1750 uit de overdracht.",
        f"<b>Zijkant veranda dicht.</b> Toegang alleen via de voorkant. De verandapaal vervalt, waardoor de veranda {m.IN_X1-m.VER_X0} mm breed wordt.",
        "<b>Trap tegen de linkerwand,</b> stijgend van voor naar achter, met het trapgat linksachter. De eerste trede begint 60 mm achter het raam; dat kan, omdat de vleugel nu naar buiten draait.",
        "<b>Lightply 9 mm als wandbekleding en betonplex 12 mm voor de vloeren.</b> Goedkoper dan multiplex 6 mm op bestelling en betonplex 18 mm. Zie 'Plaatmateriaal'.",
    ):
        A.append(B(t))
    A += [P("Mijn adviezen waarmee je akkoord bent", "h2")]
    for t in (
        f"<b>Zonnepaneel en accu niet als hoofdbron.</b> In december is ongeveer {round(r['wh_day_dec'])} Wh per dag nodig, terwijl 100 Wp paneel dan {round(r['pv100'][0])}-{round(r['pv100'][1])} Wh per dag oplevert. Daarvoor is {round(r['wp_needed'][0],-2):.0f}-{round(r['wp_needed'][1],-2):.0f} Wp nodig, plus accu: niet haalbaar binnen €250-500. Netstroom past wel. De mantelbuis houdt een uitbreiding open.",
        f"<b>Ø75 in plaats van Ø40 ventilatie.</b> Bij 5 °C trekt Ø40 op natuurlijke wijze {nl(r['vent'][2][3])} m³/h terwijl minstens {nl(r['vent'][2][1])} m³/h nodig is. Ø75 haalt {nl(r['vent'][2][5])} m³/h. Bij vorst knijp je het rooster om warmte te sparen.",
        "<b>Verankering in de grond.</b> Bij storm is het kantelmoment ongeveer twee keer zo groot als wat het eigen gewicht kan opvangen.",
    ):
        A.append(B(t))
    A += [P("Status van de keuzes", "h2")]
    A += [T([["Onderwerp", "Status", "Keuze en toelichting"],
             ["Ramen binnenstebuiten", "Jouw keuze, afwijkend van de bedoelde montage", "Zie 'Ramen binnenstebuiten'. De garantie zal dit waarschijnlijk niet dekken."],
             ["Bovenraam", "Jouw voorkeur", "Hornbach kelderraam 100 x 50 (art. 12074105). Dubbel glas, Uw 1,3, 15,5 kg. Glasdoorkijk ongeveer 764 x 264 mm."],
             ["Raam trapkamer", "Jouw voorkeur", "ARON Basic+ 50 x 50 (art. 12331530). Triple glas, Uw 0,92, 10,4 kg. Glasdoorkijk ongeveer 298 x 298 mm."],
             ["Maat ramen", "Te controleren", "Jij en ik gaan ervan uit dat 500 de buitenmaat van het kozijn is. Hornbach bevestigt dit niet. Meet na levering; voor die tijd niet zagen."],
             ["Wandbekleding", "Jouw keuze", "Lightply 9 mm, 2440 x 1220 (art. 12575686). Bovenkamer prima. Veranda en trapkamer: goed afwerken, zie 'Plaatmateriaal'."],
             ["Vloeren", "Jouw keuze", "Betonplex 12 mm (art. 12628592). Sterk genoeg voor kat en mand, niet om op te staan of te knielen."],
             ["Isolatie", "Besloten", "PIR 40 mm alu. Past in 44 mm regels, geen vezels voor de kat, één pak van 8,64 m² volstaat."],
             ["Dampopbouw", "Mijn advies", "Alu-PIR met getapete naden als dampscherm, geen extra folie. Buiten dampopen waterkerende folie."],
             ["Dak", "Mijn advies", "Koud dak: PIR op plafondplaat, geventileerde ruimte, OSB-3, EPDM. Afschot 1:40 naar achter."],
             ["Tussenvloer", "Mijn advies", "PIR 40 mm direct onder de bovenplaat. Onderplaat met 6 gaten Ø10 + gaas, zodat de holle ruimte kan drogen."],
             ["Vloer beneden", "Mijn advies", "Niet geïsoleerd, betonplex op geïmpregneerd frame, 5 mm afschot naar voren."],
             ["Verwarming", "Besloten", "Netstroom met thermostaat. Specifiek verwarmingsmodel nog te kiezen; ik vond er geen bij Hornbach."],
             ["Ventilatie", "Besloten", "PVC Ø75 met regelbaar rooster. De werking in de praktijk controleren met een hygrometer."],
             ["Fundering", "Besloten", "6 poeren met trekvaste paalhouders."],
             ["Houtsoort gevel", "Mijn advies", "Douglas 18 x 145 tand-en-groef (Hornbach) met Hornbach Hybride houtbeits mahonie, op primer; hoeklatten en boeiboorden in Hybride houtbeits RAL 7016 antraciet."],
             ["Buitenmaat 1300 x 900", "Aangehouden", "Ontwerpuitgangspunt uit de overdracht."],
             ["Vergunning", "Te controleren", "Niet onderzocht; controleer lokale regels en afspraken met buren."],
             ], [33, 30, 115])]

    A += [PageBreak(), P("Ramen binnenstebuiten", "h1")]
    A += [P("Dit ontwerp volgt jouw keuze. Beide ramen zijn gemaakt om naar binnen open te draaien en Hornbach vermeldt geen buitendraaiende montage. Deze montage is dus niet door de fabrikant bedoeld. Het risico zit vooral in water. De details vangen dat zo goed mogelijk op, maar ik kan niet garanderen dat het volledig dicht blijft. Ik vond geen bron die deze montage bevestigt; de punten hieronder zijn mijn eigen beoordeling op basis van de profieltekening.")]
    A += [T([["Wat verandert", "Gevolg", "Maatregel in dit ontwerp"],
             ["Afwateringssleuven wijzen naar de andere kant", "Water dat achter de eerste rubber komt, loopt aan de binnenzijde uit het kozijn.", "EPDM-goot onder het kozijn met opstand van 30 mm aan de binnenzijde, afschot naar buiten via de lekdorpel."],
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
    A += [P("<b>Buitenkwaliteit is binnen inderdaad niet nodig.</b> In de verwarmde bovenkamer is Lightply prima. De trapkamer en veranda zijn onverwarmd en de veranda staat aan de voorkant open. Hornbach noemt Lightply geschikt voor 'beschut buiten', maar het verwerkingsvoorschrift draagt het label Interieur en een lijmklasse wordt nergens genoemd. Daar ligt dus het enige echte risico.")]
    for t in ("Lightply is Falcata: licht (ongeveer 400 kg/m³) en zacht. Een krabbende kat laat er sneller sporen in achter; een krabplank helpt.",
              "Volg het voorschrift van Lightply: 48 uur acclimatiseren, voorboren, schroeven minstens 15 mm uit de rand, schuren, gronden en in meerdere lagen afwerken. Randen afronden (R3) en sealen: dat is het kwetsbaarste deel.",
              "Lijm met PU- of houtlijm en schroef om de 100 mm op de regels, omdat de platen het chalet stijf houden. Dat geldt vooral voor de wanden rond de open voorkant van de veranda.",
              "Laat de onderrand 3-5 mm boven de vloer stoppen en kit de naad, zodat de plaat geen water optrekt. Controleer de veranda de eerste winter. Blijft de plaat daar nat of trekt hij bol, vervang dan alleen die wanden door betonplex 12 mm.",
              "Alles past uit 2 platen van 2440 x 1220 mm, ongeveer 93 % benut; volg het zaagplan op blad T11. Alle wanden, het plafond en de onderkant van de tussenvloer zijn uit één stuk. Laat de platen bij Hornbach voorzagen langs de eerste lange snede als ze anders niet in de auto passen.",
              "Bevestig zware dingen, zoals de verwarmingskap, in de regels en niet in de plaat.",
              "Betonplex 12 mm is sterk genoeg voor een kat en mand bij deze balkafstand (maximaal 262 mm), maar niet om op te staan of te knielen. Ik gebruik het ook voor de trap en de onderkant van het dakoverstek, omdat die buiten hangt en er restmateriaal van de vloeren is."):
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
            "Een verwarming van 120 W geeft reserve voor strenge vorst en snel opwarmen. Een lichtere 60 W is net te krap. Het raam is met ongeveer 22 % van het verlies een groot deel; als het door de omgekeerde montage minder goed sluit, wordt het verbruik hoger.")]
    A += [P("Oppervlaktetemperatuur en condens", "h2")]
    A += [P(f"Het dauwpunt bij 11 °C en 75 % luchtvochtigheid is {nl(r['dew'])} °C. Bij -5 °C buiten is de wand op de isolatie {nl(r['s_ins'])} °C, op een regel {nl(r['s_wood'])} °C en op het glas {nl(r['s_glass'])} °C. "
            "Dat ligt allemaal boven het dauwpunt. De kozijnrand kan kouder zijn, dus lichte condens onderin het raam is bij strenge vorst mogelijk.")]
    A += [P("Ventilatie op natuurlijke trek", "h2")]
    A += [P("Vochtproductie van de kat is geschat op 5-10 g/h (een aanname: geschaald vanaf mensgegevens). Doel: onder 75 % luchtvochtigheid bij buitenlucht van 90 %. Trekhoogte 0,85 m, stromingscoëfficiënt 0,5. Wind helpt meestal, maar telt niet mee.")]
    rows = [["Buiten °C", "Nodig 5 g/h", "Nodig 10 g/h", "Ø40 (36 binnen)", "Ø50 (46 binnen)", "Ø75 (71 binnen)"]]
    for t, a, b, c, d, e in r["vent"]:
        na = "n.v.t.*" if a == float("inf") else nl(a)
        nb = "n.v.t.*" if b == float("inf") else nl(b)
        rows.append([str(t), na, nb, nl(c), nl(d), f"<b>{nl(e)}</b>"])
    A += [T(rows, [26, 28, 28, 32, 32, 32])]
    A += [P("Waarden in m³/h. *Bij 10 °C en vochtige buitenlucht haalt geen enkele luchtverversing 75 %: de lucht is zelf al zo vochtig. Geen probleem zolang de wanden warmer zijn dan de lucht buiten, en kort van duur.", "s")]
    A += [Spacer(1, 4), P("<b>Conclusie:</b> Ø40 volstaat alleen bij vorst. Ø75 is ook bij 5 °C voldoende voor een kat met de lage schatting, maar niet voor de hoge. De hygrometer moet dit in de praktijk bevestigen; een kleine ventilator is de terugvaloptie.")]
    A += [P("Energievoorziening: waarom geen zonnepaneel als hoofdbron", "h2")]
    A += [T([["Gegeven", "Waarde"],
             ["Benodigd in december", f"Ongeveer {round(r['p_dec'])} W, {round(r['wh_day_dec'])} Wh per dag"],
             ["Opbrengst 100 Wp in december", f"{round(r['pv100'][0])}-{round(r['pv100'][1])} Wh per dag (18-32 kWh per kWp in de maand, geen schaduw)"],
             ["Benodigd paneel", f"{round(r['wp_needed'][0],-2):.0f}-{round(r['wp_needed'][1],-2):.0f} Wp, zonder laadverlies en donkere weken"],
             ["Accu LiFePO4 100 Ah, 12,8 V", f"Ongeveer {round(r['batt_wh'])} Wh bruikbaar, dus ongeveer {round(r['batt_hours'])} uur zonder zon"],
             ], [66, 112])]
    A += [P("Conclusie: een accu overbrugt ruim een etmaal, en in donkere weken laadt een klein paneel die niet op. Netstroom is de enige realistische hoofdbron binnen het budget. Een klein paneel zou wel een ventilator of ledlampje kunnen voeden.")]
    A += [KeepTogether([P("Stabiliteit bij storm", "h2"), P(f"Windkracht op 1,5 x {nl(m.Z_TOP/1000,2)} m bij 0,9 kN/m² (aanname, ruim voor een beschutte tuin): {nl(r['F'])} kN. Kantelmoment {nl(r['M_over'],2)} kNm. Het eigen gewicht van ongeveer {round(r['mass'])} kg geeft {nl(r['M_stab'],2)} kNm tegenwicht. "
            f"Tekort: {nl(r['tension'],1)} kN trek aan de loefzijde, verdeeld over 3 poeren. Eén poer van 300 x 300 x 500 mm weegt ongeveer {round(r['poer_kg'])} kg, samen {round(3*r['poer_kg'])} kg, dat is genoeg. Bevestig de paalhouders dus echt trekvast in de poer en de poten aan het frame.")])]
    A += [P("Sterkte", "h2")]
    A += [P("Plafondrand boven het raam (44 x 69, overspanning 1020 mm): dak plus 70 kg/m² sneeuw geeft ongeveer 0,65 kN/m, buigspanning circa 2,4 MPa en doorbuiging circa 0,7 mm, ruim binnen de voeg van 10 mm. Vloerrand boven de veranda (44 x 69, 568 mm): ruim voldoende. Dit is een eenvoudige controle zonder rekenmodel van een constructeur; vuren van Hornbach is niet als C24 gesorteerd.")]

    A += [Spacer(1, 10), P("Veiligheid voor de kat", "h1")]
    A += [T([["Risico", "Maatregel in dit ontwerp"],
             ["<b>Kiepstand van het raam</b>", "<b>Dit is het grootste risico.</b> Katten raken vast in een kiepraam en kunnen daardoor ernstig gewond raken of sterven. Dat geldt ook als het raam naar buiten kiept. Zet de ramen nooit op kiep als de kat erbij kan, tenzij met een beveiliging."],
             ["Open raam", "Door de omgekeerde montage kan de kat er bij een open raam direct uit, en terug. Sluit het raam tijdens het schoonmaken als de kat binnen is. Greep afsluitbaar."],
             ["Eén uitgang", "Met de dichte zijkant is de voorkant van de veranda de enige uitgang. Een vreemde kat of ander dier kan de jouwe dan in het chalet in het nauw drijven. Let daarop in de eerste weken. Een tweede uitgang kan later in de rechterwand, boven de vloer, als dit een probleem blijkt."],
             ["Isolatie", "PIR volledig achter de wandplaat; geen vezels. Naden gekit, randen afgedekt."],
             ["Elektra en hitte", "Verwarming achter stalen kap, kabels in mantelbuis, thermostaat buiten bereik, maximaalthermostaat, aardlek."],
             ["Brand", "PIR niet bij warmtebron; niet-brandbare plaat achter verwarming; afstand volgens fabrikant. Geen warmtelamp en geen open gloeielement."],
             ["Vastzitten", "Doorgang 190 x 260; trapgat 247 x 367. Ventilatiegaten met RVS gaas. Treden sluiten zonder kier op de trapbomen aan."],
             ["Trap", "Treden met sisal of rubber. Hoek 39°: geschikt voor de meeste katten. De bovenste trede komt tegen de achterwand; de kat stapt daar zijwaarts of vooruit de kamer in."],
             ["Lage kamers", "Vrije hoogte 540 mm: ruim genoeg voor een kat, minder om te klimmen of springen. Mand laag houden, zodat de kat nog door het raam kan kijken."],
             ["Houtbehandeling", "Gebruik de houtbeits alleen buiten. Binnen geen biocide. Lak moet volledig uitgehard zijn voordat de kat erin gaat. Controleer het veiligheidsblad van elk product."],
             ["Tocht", "Dichte zijkant, doorgang achterin, bed bij het raam; lucht loopt achterlangs naar de afvoer."],
             ["Scherpe delen", "Schroeven door de plaat mogen niet uitsteken: verzink ze. Plaatranden licht afronden."],
             ], [38, 140])]
    A += [P("Wat de Hornbach-ramen betekenen", "h2")]
    for t in (
        "<b>Glashoogte.</b> Een profiel van 118 mm rondom laat bij het bovenraam 264 mm glashoogte over, op 148-412 mm boven de vloer. Een kat op een lage mand kijkt er goed doorheen. Je ziet niet het royale panorama uit de inspiratieafbeelding.",
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
    Bd += [P("Zaaglijst", "h1"), P("Maten in mm, L x B x D. Bouwdelen komen overeen met de tekeningen. Bij gevelplanken is B de werkende breedte 135 (plank zelf 145); die planken hoeven dus niet gerift. Deze lijst staat ook, sorteerbaar, in het Excel-bestand.")]
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
        else:
            qt = f"{str(q).replace('.', ',')} {u or ''}"
            if price is None:
                rows.append([name, art or "", qt, "?", "?", st or src or ""])
            else:
                rows.append([name, art or "", qt, f"€{nl(price,2)}", f"€{nl(q*price,2)}", st or src or ""])
    Bd += [T(rows, [66, 19, 16, 15, 17, 45])]
    Bd += [Spacer(1, 6), P("<b>Eerst bij Hornbach controleren:</b> geïmpregneerde balk 44 x 69, spouwlat 22 x 44, gevelfolie, alu-cachering van de PIR en OSB per plaat. Het EPDM wordt op maat gemaakt en kan niet retour, dus bestel het als de dakmaat vaststaat.")]
    Bd += [PageBreak(), P("Stappenplan", "h1")]
    steps = [
        ("Voorbereiding", ["Kies de plek. Houd de voorkant vrij om bij de ramen en de veranda te komen.", "Bespreek met een installateur de voeding, de aardlek en de positie van de thermostaatkast.", "Controleer de gemarkeerde artikelen bij Hornbach en bestel eerst de ramen."]),
        ("Ramen inmeten", ["Meet beide kozijnen na ontvangst op drie plekken in breedte en hoogte. Is een maat anders dan 1000 x 500 of 500 x 500, pas dan het model aan voor je zaagt: de kamerhoogte hangt hiervan af.", "Bekijk de scharnierzijde, glaslatten en afwateringssleuven. Monteer de greep en test kiep- en draaistand met het raam omgekeerd op de werkbank."]),
        ("Hout voorbehandelen", ["Zaag volgens zaaglijst. Laat grote platen in de vestiging voorzagen.", "Hoeklatten: zaag op de tafelzaag eerst tong en groef van de Douglas-plank, dan 4 stroken 58 x 18 en 4 stroken 40 x 18, lang 1350. Zet per hoek de smalle kant van de 40-strook tegen de achterkant van de 58-strook, zodat een L van 58 x 58 ontstaat. Lijm met PU-lijm, schroef RVS 4 x 40 om de 250 mm, voorgeboord, en klem tot de lijm hard is. Daarna gronden en beitsen. De hoeklat ligt in hetzelfde vlak als de gevelplanken, die er stomp tegenaan komen; behandel de kopse kanten van de planken.", "Beits vóór montage, binnen en niet onder +8 °C: alle gevelplanken eerst gronden, kopse kanten met kopshoutverzegeling. Beits 2 lagen, op plekken die veel weer vangen 3; 8 uur tussen de lagen. Maak eerst een proefstuk voor de kleur.", "Laat Lightply 48 uur acclimatiseren. Schuur, grond en lak de zichtzijde vóór montage; randen afronden en sealen. Sla hout droog en plat op."]),
        ("Fundering", ["Graaf 6 poeren op de hartmaten van het vloerframe (blad T6), 500 mm diep; op klei 700 mm om opvriezen te voorkomen. Stort beton met verzinkte paalhouders. Zet ze met een waterpas op gelijke hoogte, op 5 mm afschot naar voren na.", "Laat de poeren minstens enkele dagen uitharden. Leg worteldoek en grind in de zone onder het chalet."]),
        ("Vloerframe", ["Bouw frame A plat, controleer de diagonalen (1470 mm) en plaats het op de poten. Bevestig met hoekankers en constructieschroeven.", "Lijm en schroef de vloerplaat. Verzegel alle randen."]),
        ("Benedenwanden", ["Bouw wanden C, D, E, F plat op de vloer, monteer ze en zet ze waterpas. Plaats de stijlen van wand B met hoekankers op de vloer.", "Lijm en schroef de wandplaten: voorboren, om de 100 mm, minstens 15 mm uit de rand. Dit maakt het geheel stijf; controleer de haaksheid vóór de lijm uithardt.", "Monteer de trap N tegen de linkerwand en proefpas: die is hierna niet meer uit te nemen."]),
        ("Tussenvloer", ["Maak de cassette G: randen, balken, raveel, PIR tegen de bovenplaat, onderplaat met 6 gaten Ø10 en gaas. Tape PIR-naden met alu-tape.", "Hef de cassette met twee personen op de benedenwanden. Schroef hem vast en veranker de raamstijlen boven en onder."]),
        ("Bovenwanden", ["Bouw I, J, K met PIR tussen de regels. Tape alle naden. Monteer ze op de vloer. Plaats de stijlen van wand H met hoekankers.", "Monteer de binnenplaten. Kit de naden en dicht de plaat rond de ventilatiebuis."]),
        ("Plafond en dak", ["Maak de plafondcassette L en schroef die op de wanden. PIR bovenop de plaat.", "Zaag de 5 sporen schuin en schroef ze op de balken. Bevestig de OSB-plaat; rond de hoeken af.", "Lijm de EPDM volgens de Premiumfol-handleiding, bij droog weer boven 5 °C. Bevestig daktrim, boeiboorden, gootje en afvoer.", "<b>Het casco is nu regendicht.</b> Laat het droog nakijken voordat je verdergaat."]),
        ("Folie en spouw", ["Breng de folie aan op alle gevels rond het casco, met minstens 100 mm overlap en boven over onder. Neem de folie mee in de sparingen.", "Spouwlatten volgens bladen T2 en T3. Laat onder en boven open, met RVS gaas."]),
        ("Ramen", ["Lijm de EPDM-goot over de dorpelregel met opstand aan de binnenzijde en afschot naar buiten. Leg daarop lekdorpel en stelblokjes.", "Plaats het raam binnenstebuiten, kozijn gelijk met de gevel, waterpas en haaks. Schroef in de stijlen: max. 150 mm uit de hoeken en max. 600 mm h.o.h. Niet krom trekken.", "Compriband rondom, kit op glaslatten en naden. Controleer bediening en blokkeer of beveilig de kiepstand."]),
        ("Gevel", ["Monteer van onder naar boven, tong omhoog. Hoeklatten en kader volgens blad T2. Plaats de regenluifel boven het lage raam.", "Bevestig met RVS schroeven; voorboren aan de plankeinden. Controleer of de vleugels vrij blijven draaien."]),
        ("Ventilatie en elektra", [f"Boor Ø78 op x = {m.VENT['x']}, z = {m.VENT['z']}. Plaats de PVC-buis met licht afschot naar buiten, kap en gaas. Rooster binnen.", "Installateur: voeding, kast, thermostaat, voeler, verwarming, aardlektest.", "Bescherm de kabels volledig, plaats de kap en controleer de temperatuur van de kap na 2 uur vol vermogen."]),
        ("Watertest", ["Spoel beide ramen 15 minuten met een tuinslang, van boven naar beneden, met de ramen dicht.", "Kijk daarna aan de binnenzijde van het kozijn en in de goot. Lekt het, dan eerst dat oplossen."]),
        ("Inwerken", ["Bekleed de treden, plaats mat, mand, hygrometer. Maak alle schroefpunten aan de kat-zijde onschadelijk.", "Test 3 dagen zonder kat: temperatuur, vocht, condens, kap en roosterstand.", "Laat de kat wennen met de voeding op de veranda. Controleer de eerste weken de hygrometer, de goot en de wanden."]),
    ]
    for i, (t, ss) in enumerate(steps, 1):
        Bd.append(KeepTogether([P(f"{i}. {t}", "h2")] + [B(s) for s in ss]))
    Bd += [PageBreak(), P("Onderhoud", "h1")]
    for t in ("Elk jaar voor de winter: kit, EPDM, trim, gootje, gaas en roosters nakijken; hygrometer vergelijken; verwarming en aardlek testen.",
              "Ramen: elk seizoen de goot en buitennaden controleren, want daar zit het grootste risico. Regelmatig reinigen en het beslag twee keer per jaar smeren.",
              "Gevel: Douglas vraagt om regelmatig bijhouden. Hornbach adviseert onbehandeld Douglas om de 2 jaar te beitsen; voor de Hybride houtbeits noemt Hornbach tot 7 jaar bescherming, afhankelijk van weer en constructie. Controleer jaarlijks en herstel beschadigingen direct.",
              "Binnen: met water en mild schoonmaakmiddel. Lak op tijd bijwerken bij krassen. Geen producten die voor de kat schadelijk zijn."):
        Bd.append(B(t))
    Bd += [P("Bronnen", "h2")]
    for t in (
        "Hornbach-pagina's bekeken op 6-11-2026: kelderraam 12074105, ARON Basic+ 12331530, betonplex 12628592, Lightply 12575686 en 12575693 (met verwerkingsvoorschrift), PIR 10368506, EPDM 10469549, daktrim 5581276, Douglas 10537457, vuren 5185884 en 5185888, antraciet beits 10277101, folie 7049802. Paalhouder 6424538 via zoekresultaat.",
        "ARON Basic+ 70 mm technisch blad en montagerichtlijn (Hornbach, as.187466783, as.187466663); maattekening kelderraam (as.91729658).",
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
    for key, stock in (("R44", 2400), ("B69", 2400), ("I69", 2400), ("P69", 1800), ("LAT", 2400)):
        for i, bar in enumerate(NEST[key], 1):
            ws.append([m.MAT[key], i, stock, " + ".join(str(int(c_[0])) for c_ in bar["cuts"]), int(bar["left"])])
    for key in ("DG", "DK"):
        for i, s in enumerate(NEST[key], 1):
            desc = " + ".join(f"{int(it[2])}x{int(it[3])}" for it in s.items)
            ws.append([m.MAT[key], i, 3000, desc, ""])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = base
    for col, w in zip("ABCDE", (34, 8, 16, 90, 10)):
        ws.column_dimensions[col].width = w
    ws = wb.create_sheet("Platen op maat")
    ws.append(["Plaat", "Plaatnr.", "Onderdeel", "Lengte mm", "Breedte mm", "x vanaf hoek mm", "y vanaf hoek mm"])
    for c in ws[1]:
        c.fill, c.font = head, hf
    for key, label_ in (("LP9", "Lightply 9, 2440x1220"), ("BP12", "Betonplex 12, 2500x1250"), ("OSB", "OSB-3 18, 2440x1220"), ("PIR", "PIR 40, 1200x600")):
        for i, sheet in enumerate(NEST[key], 1):
            for x_, y_, w_, h_, nm in sorted(sheet.items, key=lambda it: (it[1], it[0])):
                ws.append([label_, i, nm.replace(":", " "), round(w_), round(h_), round(x_), round(y_)])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = base
    for col, w in zip("ABCDEFG", (26, 8, 42, 11, 11, 15, 15)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wb.save(path)


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
    for f in (a, b, d):
        os.remove(f)
    os.rmdir(tmp)
    print("OK", {k: len(v) for k, v in NEST.items()}, "pagina's", len(PdfReader(OUT_PDF).pages))


if __name__ == "__main__":
    main()
