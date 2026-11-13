"""Mal van de trapboom op ware grootte: A4-liggend, met plakranden, om op het betonplex te plakken en uit te zagen.

Vorm en maten komen uit model.py (rechterboom met lip; de linkerboom is gelijk, zonder lip).
Schrijft Kattenchalet_mal_trapboom.pdf.
"""
import math

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import model as m

FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("D", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DB", FD + "DejaVuSans-Bold.ttf"))

OUT = "Kattenchalet_mal_trapboom.pdf"
PW, PH = 297, 210          # A4 liggend, mm
M = 10                     # marge: wat de printer zeker afdrukt
CW = PW - 2 * M            # 277 mm tekening per blad
OV = 15                    # plakrand
STEP = CW - OV
U_MIN = -8                 # tekening begint 8 mm voor het plaatstuk
Y0 = 42                    # onderkant plaatstuk op het blad
HOLE = 6                   # boorgat in de binnenhoeken

# --- vorm in het assenstelsel van het plaatstuk: u langs de lengte, v omhoog vanaf de rechte onderkant ---
k, n = m.ST_K, m.ST_N


def to_uv(pts):
    return [((y + k * z) / n, (-k * y + z) / n) for y, z in pts]


_ref = to_uv(m.stringer_fwd(free=True))
U0, V0 = min(u for u, _ in _ref), min(v for _, v in _ref)


def uv(pts):
    return [(u - U0, v - V0) for u, v in to_uv(pts)]


RIGHT = uv(m.stringer_fwd(free=True))
LEFT = uv(m.stringer_fwd(free=False))
STRIP = uv(m.strip_fwd())
L, B = m.STRINGER_L, m.STRINGER_W

# binnenhoeken (hol in het hout): daar komt een boorgat
area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(RIGHT, RIGHT[1:] + RIGHT[:1]))
CONCAVE = []
for i, p in enumerate(RIGHT):
    a, c = RIGHT[i - 1], RIGHT[(i + 1) % len(RIGHT)]
    cross = (p[0] - a[0]) * (c[1] - p[1]) - (p[1] - a[1]) * (c[0] - p[0])
    if cross * area < -1e-6:
        CONCAVE.append(p)

# stuk van de linkerboom dat afwijkt: daar zaag je recht door over het bovenste zitvlak
seat_top = [p for p in LEFT if p not in RIGHT]
lip_start = next(p for p in RIGHT if p not in LEFT)
lip_end = RIGHT[RIGHT.index(lip_start) + 3]

U_MAX = max(u for u, _ in RIGHT) + 8
NPAGE = math.ceil((U_MAX - U_MIN - CW) / STEP) + 1

INK = (0, 0, 0)
GREY = (0.55, 0.55, 0.55)
WOOD = (0.96, 0.92, 0.84)
GLUE = (0.88, 0.88, 0.88)
RED = (0.75, 0.1, 0.1)


def run(path=OUT):
    c = canvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle("Mal trapboom, ware grootte")
    for i in range(NPAGE):
        page(c, i)
        c.showPage()
    c.save()
    print(f"{path}: {NPAGE} bladen A4 liggend, plaatstuk {L} x {B}, {len(CONCAVE)} boorgaten")


def page(c, i):
    us = U_MIN + i * STEP
    X = lambda u: (M + u - us) * mm
    Y = lambda v: (Y0 + v) * mm

    def text(x, y, s, size=8, font="D", color=INK, anchor="l"):
        c.setFillColorRGB(*color)
        c.setFont(font, size)
        {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](x, y, s)

    # kop
    text(M * mm, (PH - 12) * mm, f"Mal trapboom, ware grootte (1:1)  -  blad {i + 1} van {NPAGE}", 11, "DB")
    text(M * mm, (PH - 18) * mm, "Afdrukken op 100 % / werkelijke grootte, NIET 'aanpassen aan pagina'. "
         "Controleer de meetlat van 100 mm voor je gaat plakken.", 8, color=RED)

    # alles van de tekening binnen het tekenvlak houden
    c.saveState()
    p = c.beginPath()
    p.rect(M * mm, 0, CW * mm, PH * mm)
    c.clipPath(p, stroke=0, fill=0)

    # plakrand rechts: hier komt het volgende blad overheen
    if i < NPAGE - 1:
        gx = X(us + STEP)
        c.setFillColorRGB(*GLUE)
        c.rect(gx, (Y0 - 30) * mm, (M + CW) * mm - gx, (B + 55) * mm, stroke=0, fill=1)
        c.saveState()
        c.translate(gx + OV * mm / 2 + 1.2 * mm, (Y0 + B / 2) * mm)
        c.rotate(90)
        text(0, 0, f"PLAKRAND: leg de knipkant van blad {i + 2} op de lijn", 7, "DB", GREY, "c")
        c.restoreState()

    # plaatstuk
    c.setStrokeColorRGB(*GREY)
    c.setLineWidth(0.4)
    c.setDash(3, 2)
    c.rect(X(0), Y(0), L * mm, B * mm, stroke=1, fill=0)
    c.setDash()

    # boom (rechterboom met lip)
    path = c.beginPath()
    path.moveTo(X(RIGHT[0][0]), Y(RIGHT[0][1]))
    for u, v in RIGHT[1:]:
        path.lineTo(X(u), Y(v))
    path.close()
    c.setFillColorRGB(*WOOD)
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.8)
    c.drawPath(path, stroke=1, fill=1)

    # versterkingsstrook
    c.setDash(1.5, 1.5)
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0.45, 0.3, 0.15)
    sp = c.beginPath()
    sp.moveTo(X(STRIP[0][0]), Y(STRIP[0][1]))
    for u, v in STRIP[1:]:
        sp.lineTo(X(u), Y(v))
    sp.close()
    c.drawPath(sp, stroke=1, fill=0)
    # linkerboom: recht door over het bovenste zitvlak
    c.setStrokeColorRGB(*RED)
    c.setLineWidth(0.6)
    c.setDash(4, 2)
    c.line(X(lip_start[0]), Y(lip_start[1]), X(lip_end[0]), Y(lip_end[1]))
    c.setDash()

    # boorgaten
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.3)
    for u, v in CONCAVE:
        c.circle(X(u), Y(v), HOLE / 2 * mm, stroke=1, fill=0)
        c.line(X(u) - 4.5 * mm, Y(v), X(u) + 4.5 * mm, Y(v))
        c.line(X(u), Y(v) - 4.5 * mm, X(u), Y(v) + 4.5 * mm)

    # meetlat langs de onderkant (u vanaf de linkerkop van het plaatstuk) en paskruisjes
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.25)
    ry = Y(-10)
    c.line(X(max(0, us)), ry, X(min(L, us + CW)), ry)
    for t in range(0, L + 1, 10):
        if us - 1 <= t <= us + CW + 1:
            h = 4 if t % 50 == 0 else 2
            c.line(X(t), ry, X(t), ry + h * mm)
            if t % 50 == 0:
                text(X(t), ry - 3.5 * mm, str(t), 6, anchor="c")
    for t in range(0, L + 1, 50):
        for v in (-20, B + 12):
            c.line(X(t) - 3 * mm, Y(v), X(t) + 3 * mm, Y(v))
            c.line(X(t), Y(v) - 3 * mm, X(t), Y(v) + 3 * mm)

    # opschriften
    lab = [((RIGHT[0][0] + 3, B * 0.35), "VOET", "l"),
           ((300, 3), "onderkant = rechte kant van het plaatstuk: niet zagen", "c"),
           ((560, 18), f"versterkingsstrook {m.STRIP_L} x {m.STRIP_W} (alleen rechterboom, trapkant)", "l"),
           ((lip_end[0] - 4, B + 3), "LIP (alleen rechterboom)", "r"),
           ((lip_start[0] - 2, lip_start[1] - 22), "linkerboom: recht door", "r")]
    seats = [(a, b) for a, b in zip(LEFT, LEFT[1:]) if a[1] > b[1] + 50 and a[0] < b[0]]
    for j, (a, b) in enumerate(seats):
        lab.append((((a[0] + b[0]) / 2 + 4, (a[1] + b[1]) / 2 + 4), f"trede {j + 1}", "l"))
    for (u, v), s, anc in lab:
        col = RED if "linkerboom" in s else INK
        text(X(u), Y(v), s, 7, color=col, anchor=anc)

    # knipkant links (vanaf blad 2)
    c.restoreState()
    if i > 0:
        c.setStrokeColorRGB(*RED)
        c.setLineWidth(0.5)
        c.setDash(5, 2)
        c.line(M * mm, (Y0 - 30) * mm, M * mm, (Y0 + B + 25) * mm)
        c.setDash()
        c.saveState()
        c.translate((M - 2) * mm, (Y0 + B / 2) * mm)
        c.rotate(90)
        text(0, 0, f"KNIP HIER en leg op de plakrand van blad {i}", 7, "DB", RED, "c")
        c.restoreState()

    # meetlat 100 mm op elk blad
    bx, by = M * mm + (6 if i else 0) * mm, 9 * mm
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.5)
    c.line(bx, by, bx + 100 * mm, by)
    for t in range(0, 101, 10):
        c.line(bx + t * mm, by, bx + t * mm, by + (4 if t % 50 == 0 else 2) * mm)
    text(bx + 102 * mm, by, "meet na: 100 mm", 7)

    if i == NPAGE - 1:
        tx, ty = X(U_MAX) + 14 * mm, (PH - 30) * mm
        lines = [
            ("Werkwijze", "DB"),
            ("1. Print op 100 % en meet de meetlat na.", "D"),
            ("2. Knip blad 2, 3 en 4 links af op de rode stippellijn.", "D"),
            ("3. Leg elk blad op de grijze plakrand van het vorige:", "D"),
            ("   paskruisjes, meetlat en lijnen moeten gelijk lopen. Plakband.", "D"),
            ("4. Leg de grijze stippelrechthoek (plaatstuk " + f"{L} x {B})", "D"),
            ("   op het plaatstuk: onderkant op de rechte lange kant,", "D"),
            ("   linkerkant op de kopse kant (voet).", "D"),
            ("5. Plak vast met spuitlijm of dubbelzijdige tape.", "D"),
            (f"6. Boor eerst de {len(CONCAVE)} gaten Ø{HOLE} (kruisjes = hart).", "D"),
            ("7. Zaag op de dikke lijn, aan de afvalkant, naar de", "D"),
            ("   gaten toe, nooit erlangs (ca. 60 mm hout over).", "D"),
            ("8. Rechterboom met lip eerst; daarna als mal voor de", "D"),
            ("   linkerboom, die recht doorloopt (rode stippellijn).", "D"),
            ("Treden: optrede 99, zitvlakken " + "/".join(str(d) for d in m.TREAD_D) + ";", "D"),
            ("trede 1 steekt 50 mm voorbij zijn tand.", "D"),
            ("Bron: model.py; papier kan iets krimpen of rekken,", "D"),
            ("dus controleer de totale lengte " + f"{L} op het hout.", "D"),
        ]
        for s, f in lines:
            text(tx, ty, s, 8, f)
            ty -= 4.2 * mm


if __name__ == "__main__":
    run()
