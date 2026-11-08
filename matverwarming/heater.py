#!/usr/bin/env python3
"""Flexibele verwarming voor de kattenmat: 5 gelijke segmenten die samen een ring vormen.

De vorm komt uit Ontwerp.dxf (de symmetrische polylijn, binnenrand onder): 200 x 200 mm met
de onderhoeken afgeschuind naar de vijfhoek in het midden. Schrijft Gerbers voor JLCPCB Flex
Heater: folie (GTL), coverlay-openingen (GTS), omtrek (GKO). Eenheden mm; oorsprong linksonder
van het omsluitende vierkant, binnenrand (naar het midden van de ring) onderaan.

Ontwerp (aanname, niet getest):
- Folie RVS 304, 50 um, rho 0,75 uOhm.m  ->  Rs = 0,015 Ohm/vierkant. JLCPCB-blog: 0,768 +/-6 %.
- Vermogen zo dat de dichtheid gelijk blijft aan het eerdere voorstel (4 W op 400 cm2).
- Kolommen-meander in twee helften, verbonden over de buitenrand. Langs de binnenrand en de
  schuine kanten loopt de terugweg naar de pads. In het midden een kanaal voor de NTC-sporen.
- Aansluitingen in het midden van de binnenrand: H1, N1, N2, H2 (links naar rechts).
"""
import math, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "gerber")
DXF = os.path.join(HERE, "Ontwerp.dxf")

RHO = 0.75e-6          # Ohm.m
T_FOIL = 50e-6         # m
RS = RHO / T_FOIL      # Ohm/sq
V = 12.0
DENSITY = 4.0 / 400    # W/cm2, zoals 4 W per 20 x 20 cm
EDGE = 1.5             # min. afstand koper tot omtrek (JLCPCB-regel >= 1)

# NTC-sporen en pads
NW = 1.0               # breedte NTC-spoor
NX = 1.25              # halve afstand tussen de NTC-sporen (hart)
NTC_PAD = (1.0, 0.95)  # 0603-pad b x h
NTC_PX = 0.875         # padhart vanaf NTC-midden
NTC_OPEN = (3.4, 2.2)  # een coverlay-opening over beide pads (min. 2 x 2)
CLR = 1.5              # min. afstand heater tot NTC-net (eigen keuze)

# draadpads
HP = 4.0               # heaterpad metaal, vierkant
HP_OPEN = 3.0
NP = 3.0               # NTC-draadpad metaal
NP_OPEN = 2.0


# ---------- vorm uit de DXF ----------
PLATE = None


def read_shape():
    lines = [l.strip() for l in open(DXF)]
    pairs = list(zip(lines[0::2], lines[1::2]))
    start = next(k for k, (c, v) in enumerate(pairs) if c == "2" and v == "ENTITIES")
    polys, cur = [], None
    for c, v in pairs[start + 1:]:
        if c == "0":
            if cur:
                polys.append(cur)
            if v == "ENDSEC":
                break
            cur = [] if v == "LWPOLYLINE" else None
        elif cur is not None and c == "10":
            cur.append([float(v), None])
        elif cur is not None and c == "20":
            cur[-1][1] = float(v)
        elif cur is not None and c == "42" and abs(float(v)) > 1e-9:
            sys.exit("Ontwerp.dxf bevat bogen; dit script kent alleen rechte lijnen")
    # een rechthoek met 4 hoeken is de aluplaat, geen segment
    global PLATE
    rects = [p for p in polys if len(p) == 4]
    PLATE = rects[0] if rects else None
    polys = [p for p in polys if len(p) != 4]
    # het segment dat symmetrisch is rond x = 0 en met de binnenrand onder ligt
    sym = [p for p in polys if abs(sum(x for x, _ in p)) < 1e-6 and min(y for _, y in p) > 0]
    if len(polys) != 5 or len(sym) != 1:
        sys.exit(f"Ontwerp.dxf: verwacht 5 segmenten, waarvan 1 symmetrisch; gevonden {len(polys)}/{len(sym)}")
    p = sym[0]
    x0, y0 = min(x for x, _ in p), min(y for _, y in p)
    pts = [(round(x - x0, 4), round(y - y0, 4)) for x, y in p]
    # tegen de klok in
    a = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    return pts if a > 0 else pts[::-1]


SHAPE = read_shape()
W_BOX = max(x for x, _ in SHAPE)
H_BOX = max(y for _, y in SHAPE)
CX = W_BOX / 2
AREA = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(SHAPE, SHAPE[1:] + SHAPE[:1]))) / 2
CEN_Y = sum((y1 + y2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(SHAPE, SHAPE[1:] + SHAPE[:1])) / (6 * AREA)
P_TARGET = round(DENSITY * AREA / 100, 1)
R_TARGET = V * V / P_TARGET
NTC_Y = round(CEN_Y, 1)        # NTC op het zwaartepunt van het segment
PAD_Y = EDGE + HP / 2
H1X, H2X = CX - 9.0, CX + 9.0
N1X, N2X = CX - 2.25, CX + 2.25

# onderste randen (binnenrand en schuine kanten) als lijnen y = a x + b, alleen voor de linkerhelft nodig
BOTTOM = []
for (x1, y1), (x2, y2) in zip(SHAPE, SHAPE[1:] + SHAPE[:1]):
    if abs(x2 - x1) > 1e-6 and min(y1, y2) < H_BOX - 1e-6:   # niet verticaal, niet de buitenrand
        BOTTOM.append(((x1, y1), (x2, y2)))


def bottom_y(x, d):
    """Laagste y op hoogte x die afstand d tot alle onderranden houdt (vorm is convex)."""
    best = 0.0
    for (x1, y1), (x2, y2) in BOTTOM:
        L = math.dist((x1, y1), (x2, y2))
        a = (y2 - y1) / (x2 - x1)
        b = y1 - a * x1
        best = max(best, a * x + b + d * L / abs(x2 - x1))   # evenwijdige lijn op loodrechte afstand d
    return best


def offset_path_left(d, x_from, x_to):
    """Pad langs de onderranden op afstand d, van x_from naar x_to (links), met de knikpunten."""
    xs = [x_from, x_to]
    for i in range(len(BOTTOM)):
        for j in range(i + 1, len(BOTTOM)):
            (p1, p2), (q1, q2) = BOTTOM[i], BOTTOM[j]
            a1 = (p2[1] - p1[1]) / (p2[0] - p1[0]); a2 = (q2[1] - q1[1]) / (q2[0] - q1[0])
            if abs(a1 - a2) < 1e-9:
                continue
            b1 = p1[1] - a1 * p1[0] + d * math.dist(p1, p2) / abs(p2[0] - p1[0])
            b2 = q1[1] - a2 * q1[0] + d * math.dist(q1, q2) / abs(q2[0] - q1[0])
            x = (b2 - b1) / (a1 - a2)
            if x_to < x < x_from and abs(a1 * x + b1 - bottom_y(x, d)) < 1e-6:
                xs.append(x)
    xs = sorted(set(xs), reverse=True)
    return [(x, bottom_y(x, d)) for x in xs]


def layout(w, n):
    """Middenlijn van de heater (H1 -> H2). n = kolommen per helft (oneven)."""
    d0 = EDGE + w / 2
    ytop = H_BOX - d0
    xl = d0                                  # buitenste kolom links
    xin = CX - NX - NW / 2 - CLR - w / 2     # binnenste kolom links
    p = (xin - xl) / (n - 1)
    # terugweg: van H1 langs binnenrand en schuine kant naar de buitenste kolom
    dr = PAD_Y                               # terugweg op padhoogte
    ret = offset_path_left(dr, H1X, xl)
    left = ret + [(xl, ytop)]
    for i in range(1, n):
        x = xl + i * p
        yb = bottom_y(x, dr + p)
        left += [(x, ytop), (x, yb)] if i % 2 == 1 else [(x, yb), (x, ytop)]
    right = [(2 * CX - x, y) for (x, y) in reversed(left)]
    pts = left + right
    clean = [pts[0]]
    for q in pts[1:]:
        if math.dist(q, clean[-1]) > 1e-6:
            clean.append(q)
    return clean, p


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def resistance(pts, w):
    corners = len(pts) - 2
    sq = length(pts) / w - corners * (1 - 0.56)   # haaks hoekje telt ~0,56 vierkant
    return RS * sq


def design():
    best = None
    for n in range(9, 41, 2):
        w = 2.5
        for _ in range(60):
            pts, p = layout(w, n)
            w *= resistance(pts, w) / R_TARGET
        pts, p = layout(w, n)
        s = p - w
        if w < 0.25 or s < 0.25:
            continue
        score = abs(s / w - 1.05)
        if best is None or score < best[0]:
            best = (score, n, w)
    _, n, w = best
    w = round(w, 2)
    pts, p = layout(w, n)
    return n, w, p, pts


def ntc_net():
    segs = []
    for sgn, nx in ((-1, N1X), (1, N2X)):
        xt = CX + sgn * NX
        ya = PAD_Y + NP / 2 + 0.5
        yb = ya + abs(xt - nx)
        path = [(nx, PAD_Y), (nx, ya), (xt, yb), (xt, NTC_Y - 0.2)]   # overlapt het 0603-pad
        segs += list(zip(path, path[1:]))
    return segs


# ---------- geometrie-check ----------
def pt_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def crosses(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def seg_dist(a, b, c, d):
    if crosses(a, b, c, d):
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def rect_segs(cx, cy, wx, hy):
    pts = [(cx - wx / 2, cy - hy / 2), (cx + wx / 2, cy - hy / 2), (cx + wx / 2, cy + hy / 2), (cx - wx / 2, cy + hy / 2)]
    return list(zip(pts, pts[1:] + pts[:1]))


def inside(p):
    return all((x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) >= 0
               for (x1, y1), (x2, y2) in zip(SHAPE, SHAPE[1:] + SHAPE[:1]))


def check(w, pts):
    heat = [(a, b, w / 2) for a, b in zip(pts, pts[1:])]
    hpads = [(a, b, 0) for x in (H1X, H2X) for a, b in rect_segs(x, PAD_Y, HP, HP)]
    ntc = [(a, b, NW / 2) for a, b in ntc_net()]
    for x in (N1X, N2X):
        ntc += [(a, b, 0) for a, b in rect_segs(x, PAD_Y, NP, NP)]
    for x in (CX - NTC_PX, CX + NTC_PX):
        ntc += [(a, b, 0) for a, b in rect_segs(x, NTC_Y, *NTC_PAD)]
    worst = min(seg_dist(a, b, c, d) - ra - rc for a, b, ra in heat + hpads for c, d, rc in ntc)
    gap = min(seg_dist(*heat[i][:2], *heat[j][:2]) - w
              for i in range(len(heat)) for j in range(i + 2, len(heat)))
    outline = list(zip(SHAPE, SHAPE[1:] + SHAPE[:1]))
    edge = min(seg_dist(a, b, c, d) - r for a, b, r in heat + hpads + ntc for c, d in outline)
    allin = all(inside(q) for q in pts)
    nl = [s for s in ntc_net() if s[0][0] < CX]
    nr = [s for s in ntc_net() if s[0][0] > CX]
    ngap = min(seg_dist(*a, *b) for a in nl for b in nr) - NW
    return worst, gap, edge, ngap, allin


# ---------- Gerber ----------
def fmt(v):
    return f"{round(v * 1e6):d}"


def header(f, name):
    f.write("G04 Gegenereerd door heater.py (kattenchalet)*\n")
    f.write(f"G04 {name}*\n%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n")


def move(f, p, op):
    f.write(f"X{fmt(p[0])}Y{fmt(p[1])}D0{op}*\n")


def write_gerbers(w, pts):
    os.makedirs(OUT, exist_ok=True)
    for fn in os.listdir(OUT):
        os.remove(os.path.join(OUT, fn))
    with open(os.path.join(OUT, "heater-F_Cu.gtl"), "w") as f:
        header(f, "Copper,L1,Top")
        f.write(f"%ADD10C,{w:.3f}*%\n%ADD11C,{NW:.3f}*%\n")
        f.write(f"%ADD12R,{HP:.3f}X{HP:.3f}*%\n%ADD13R,{NP:.3f}X{NP:.3f}*%\n")
        f.write(f"%ADD14R,{NTC_PAD[0]:.3f}X{NTC_PAD[1]:.3f}*%\n")
        f.write("G01*\nD10*\n")
        move(f, pts[0], 2)
        for q in pts[1:]:
            move(f, q, 1)
        f.write("D11*\n")
        for a, b in ntc_net():
            move(f, a, 2); move(f, b, 1)
        f.write("D12*\n")
        for x in (H1X, H2X):
            move(f, (x, PAD_Y), 3)
        f.write("D13*\n")
        for x in (N1X, N2X):
            move(f, (x, PAD_Y), 3)
        f.write("D14*\n")
        for x in (CX - NTC_PX, CX + NTC_PX):
            move(f, (x, NTC_Y), 3)
        f.write("M02*\n")
    with open(os.path.join(OUT, "heater-F_Mask.gts"), "w") as f:
        header(f, "Soldermask,Top")
        f.write(f"%ADD10R,{HP_OPEN:.3f}X{HP_OPEN:.3f}*%\n%ADD11R,{NP_OPEN:.3f}X{NP_OPEN:.3f}*%\n")
        f.write(f"%ADD12R,{NTC_OPEN[0]:.3f}X{NTC_OPEN[1]:.3f}*%\n")
        f.write("D10*\n")
        for x in (H1X, H2X):
            move(f, (x, PAD_Y), 3)
        f.write("D11*\n")
        for x in (N1X, N2X):
            move(f, (x, PAD_Y), 3)
        f.write("D12*\n")
        move(f, (CX, NTC_Y), 3)
        f.write("M02*\n")
    with open(os.path.join(OUT, "heater-Edge_Cuts.gko"), "w") as f:
        header(f, "Profile,NP")
        f.write("%ADD10C,0.100*%\nG01*\nD10*\n")
        c = SHAPE + [SHAPE[0]]
        move(f, c[0], 2)
        for q in c[1:]:
            move(f, q, 1)
        f.write("M02*\n")
    for old in ("heater_200x200_gerber.zip",):
        if os.path.exists(os.path.join(HERE, old)):
            os.remove(os.path.join(HERE, old))
    zp = os.path.join(HERE, "heater_segment_gerber.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(OUT)):
            z.write(os.path.join(OUT, fn), fn)
    return zp


def main():
    n, w, p, pts = design()
    R = resistance(pts, w)
    worst, gap, edge, ngap, allin = check(w, pts)
    rn = RS * 2 * sum(math.dist(a, b) for a, b in ntc_net()[:3]) / NW
    print(f"Vorm uit Ontwerp.dxf: {W_BOX:.1f} x {H_BOX:.1f} mm, {len(SHAPE)} hoeken, oppervlak {AREA / 100:.0f} cm2")
    print(f"Doel {P_TARGET} W bij {V:.0f} V = {R_TARGET:.1f} Ohm; NTC op y = {NTC_Y} mm (zwaartepunt)")
    print(f"Kolommen per helft {n}, spoor {w:.2f} mm, steek {p:.2f} mm, tussenruimte {p - w:.2f} mm")
    print(f"Spoorlengte {length(pts) / 1000:.2f} m, R = {R:.1f} Ohm, P = {V * V / R:.2f} W, I = {V / R:.2f} A")
    print(f"5 stuks parallel: {5 * V * V / R:.1f} W, {5 * V / R:.2f} A")
    print(f"Min. afstanden: heater-heater {gap:.2f}, heater-NTC-net {worst:.2f}, koper-rand {edge:.2f}, NTC-sporen {ngap:.2f} mm")
    print(f"Serieweerstand NTC-sporen samen ca. {rn:.1f} Ohm (verwaarloosbaar t.o.v. 10 kOhm)")
    ok = allin and gap >= 0.25 and worst >= CLR - 1e-6 and edge >= 1.0 - 1e-6 and ngap >= 0.25
    if not ok:
        sys.exit("ONTWERPREGEL GESCHONDEN")
    print("Geschreven:", write_gerbers(w, pts))


if __name__ == "__main__":
    main()
