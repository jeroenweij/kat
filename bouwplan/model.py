"""Parametrisch model van het kattenchalet (Rev K).

Alle maten in mm. Assen, gezien vanaf de voorkant:
  x = links -> rechts, y = voorkant -> achterkant, z = omhoog (0 = hoogste terrastegel).
Elk onderdeel is een Part met een positie. De zaaglijst, tekeningen en
botsingscontrole komen allemaal uit deze ene lijst.

De buitenmaat volgt uit het bovenraam (breedte) en IN_DEPTH (diepte).
"""
import math
from dataclasses import dataclass, field
from collections import defaultdict

# --- Hoofdmaten -------------------------------------------------------------
WIN_U_W, WIN_L_W, WIN_H = 1000, 500, 500   # buitenmaat kozijnen (aanname: na levering meten)
WIN_D = 71                    # kozijndiepte
WIN_JOINT = 5                 # montagevoeg boven het kozijn: EPDM en doorbuiging
IN_DEPTH = 600                # binnendiepte: achterkant kozijn -> binnenplaat achterwand
CLAD, BAT = 18, 22            # gevelplank, spouwlat
S, J = 44, 69                 # regel 44x44 en balk 44x69
PLY, PLY_F = 9, 12            # Lightply multiplex wand/plafond, betonplex vloer
OSB_T, SOF_T = 11, 12         # dakplaat, overstekplaat (betonplex)
PIR = J                       # plaat is 70: de 1 mm extra drukt in tegen de folie
PIR_NOM = 70
ROOM_H = WIN_H + WIN_JOINT    # 505: kozijn op de vloer, voeg eronder tegen het plafond

F0 = CLAD + BAT               # 40: buitenkant regelwerk
F1 = F0 + S                   # 84: binnenkant regelwerk voorwand en eerste balk
XL1 = F0 + J                  # 109: binnenkant linkerwand, regelwerk 44x69
WIN_GAP = 1                   # speling per kant tussen kozijn en stijl: stijlen strak tegen het kozijn, 2 mm totaal
W = WIN_U_W + 2 * (XL1 + WIN_GAP)   # 1220: kozijn tussen de stijlen; binnenplaten steken 8 mm voorbij het kozijn
WIN_X0 = XL1 + WIN_GAP        # 110: linkerkant van beide kozijnen
IN_Y0 = WIN_D                 # 71: de achterkant van het kozijn is de voorkant van de kamer
IN_Y1 = IN_Y0 + IN_DEPTH      # 671
YB0 = IN_Y1 + PLY             # 680: achterwand regelwerk
YB1 = YB0 + J                 # 749
D = YB1 + F0                  # 789: buitenmaat gevelbekleding
XR0, XR1 = W - XL1, W - F0    # 1127, 1196: rechterwand regelwerk
XB = XR1 - S                  # 1152: laatste balk of stijl, gelijk met de buitenkant
YR = YB1 - S                  # 705: achterbalk vloer, tussenvloer en plafond 44 x 69 aan de buitenkant; balken lopen tot hier

Z_POST = 30                   # hoogste tegel -> bodem U-paalhouder, onderkant poot
Z_LEG = 180                   # hoogste tegel van het terras -> onderkant vloerframe
Z_DECK0 = Z_LEG + J           # 249
Z_DECK = Z_DECK0 + PLY_F      # 261: vloer beneden
Z_L_TOP = Z_DECK + ROOM_H     # 766
Z_MID_J = Z_L_TOP + PLY       # 775
Z_MID_T = Z_MID_J + J         # 844
Z_UP = Z_MID_T + PLY_F        # 856: vloer bovenkamer
Z_U_TOP = Z_UP + ROOM_H       # 1361
Z_CEIL_J = Z_U_TOP + PLY      # 1370
Z_RAFT = Z_CEIL_J + J         # 1439
RAFT_F, RAFT_B = 57, 28       # spoorhoogte voor / achter (afschot naar achter)
RO_F, RO_B, RO_S = 150, 100, 100   # dakoverstek voor, achter, zijkant
ROOF_Y0, ROOF_Y1 = -RO_F, D + RO_B
ROOF_X0, ROOF_X1 = -RO_S, W + RO_S
ROOF_L, ROOF_W = ROOF_Y1 - ROOF_Y0, ROOF_X1 - ROOF_X0
Z_TOP = Z_RAFT + RAFT_F + OSB_T + 1.2
BOARD = 135                   # werkende breedte gevelplank
CLAD_Z1 = Z_RAFT - SOF_T      # 1427: bovenkant bekleding, onder de overstekplaat
CLAD_Z0 = Z_LEG - 33          # 147: 33 mm over het vloerframe heen
N_BOARD = (CLAD_Z1 - CLAD_Z0) // BOARD     # 9 hele planken, daarboven een gerifte strook
TOP_STRIP = CLAD_Z1 - CLAD_Z0 - N_BOARD * BOARD   # 65

# binnenvlakken
IN_X0, IN_X1 = XL1 + PLY, XR0 - PLY        # bovenkamer links/rechts
PART_X0 = WIN_X0 + WIN_L_W + WIN_GAP   # 611: scheidingswand en raamstijl strak naast het lage raam
PART_X1 = PART_X0 + J         # scheidingswand 44 x 69 met PIR
ROOM_X1 = PART_X0 - PLY       # 602: rechterkant trapkamer (binnenplaat)
VER_X0 = PART_X1 + PLY        # 689: linkerkant veranda
ST_X1 = HOLE_X1 = IN_X0 + 247 # 365: rechterkant trap en trapgat

# trap, hier al nodig omdat de maat van het trapgat eruit volgt (ontwerp gebruiker, Betonplex_zaagplan_trap.dxf)
# De trap stijgt van achter naar voor (keuze gebruiker 10-11-2026): voet tegen de achterwand, bovenkant 5 mm achter
# het lage kozijn, trapgat linksvoor, ligplek onder de trap bij het raam. Gerekend wordt in een rekenrichting die van
# voor naar achter loopt: daarin staat de voet op ST_Y0 en de bovenkant op ST_Y1. SY spiegelt naar de werkelijke diepte,
# waar de voet op 671 (tegen de achterwand) en de bovenkant op 76 (5 mm achter het kozijn) komt.
ST_Y0 = IN_Y0 + 5                         # 76 in de rekenrichting
ST_Y1 = IN_Y1                             # 671 in de rekenrichting


def SY(y):
    """Diepte in de rekenrichting -> werkelijke diepte."""
    return ST_Y0 + ST_Y1 - y


def SY2(a, b):
    """Bereik in de rekenrichting -> werkelijk bereik (laag, hoog)."""
    return tuple(sorted((SY(a), SY(b))))

N_RISE = 6
RISE = (Z_UP - Z_DECK) / N_RISE           # 99
TREAD = 100                               # aantrede van de middelste treden
TREAD_D = (150, TREAD, TREAD, TREAD, IN_Y1 - ST_Y0 - 150 - 3 * TREAD)   # diepte per trede: 150, 3 x 100, 145
TREAD_Y = tuple(ST_Y0 + sum(TREAD_D[:i]) for i in range(N_RISE - 1))   # voorkant per trede; treden sluiten op elkaar aan
TREAD_AT = tuple(SY2(y, y + d) for y, d in zip(TREAD_Y, TREAD_D))   # werkelijke diepte per trede (voor, achter)
HOLE_L = 343                              # trapgat 343 diep
HOLE_Y0 = F1 + PLY                        # 93: achter de rand voor en zijn dagkant, zodat het kozijn boven op de rand blijft
HOLE_Y1 = HOLE_Y0 + HOLE_L                # 436
TAB_Y0, TAB_Y1 = HOLE_Y0, HOLE_Y0 + 40     # lip vrije boom: vlak achter de dagkant voor, 40 breed
TAB_Z1 = Z_MID_T - 14                     # 830: 14 onder de bovenkant van de balk, vrij van de vloerplaat


def mid(a, b):
    return round((a + b) / 2)


# balk- en stijlposities op gelijke vakken
FLOOR_X = (F0, mid(F0, PART_X0), PART_X0, mid(PART_X1, XB), XB)   # vloerframe en achterwand beneden
MID_X = (F0, HOLE_X1, PART_X0, FLOOR_X[3], XB)                         # tussenvloer
BACK_U = tuple(round(F0 + i * (XB - F0) / 4) for i in range(5))        # achterwand boven, plafond, sporen
SIDE_Y = (F1, mid(F1, IN_Y1 - S), IN_Y1 - S)                                # stijlen zijwanden


def roof_z(y):
    """Bovenkant sporen op positie y."""
    return Z_RAFT + RAFT_F - (y - ROOF_Y0) * (RAFT_F - RAFT_B) / (ROOF_Y1 - ROOF_Y0)


@dataclass
class Part:
    name: str
    group: str
    mat: str
    box: tuple          # x0, x1, y0, y1, z0, z1
    cut: tuple = None   # zaagmaat (l, b, d); None = uit box afleiden
    count: bool = True  # False: extra geometrie van een onderdeel met uitsparing
    note: str = ""
    extra: dict = field(default_factory=dict)

    def dims(self):
        if self.cut:
            return self.cut
        x0, x1, y0, y1, z0, z1 = self.box
        return tuple(sorted((round(x1 - x0), round(y1 - y0), round(z1 - z0)), reverse=True))


MAT = {
    "R44": "Vuren geschaafd 44x44",
    "B69": "Vuren geschaafd 44x69",
    "I69": "Geimpregneerd 44x69",
    "P69": "Geimpregneerde paal 68x68",
    "LP9": "Lightply multiplex 9 (falcata, binnen)",
    "BP12": "Betonplex 12",
    "OSB": "OSB-3 11",
    "PIR": "PIR 70 alu",
    "LAT": "Spouwlat 22x44",
    "DG": "Douglas 18x145 (hout zichtbaar)",
    "DK": "Douglas 18x145 (hoek/boei antraciet)",
    "DM": "Douglas 18x145 (kader grenen beits)",
}
parts = []


def add(name, group, mat, x0, x1, y0, y1, z0, z1, **kw):
    parts.append(Part(name, group, MAT[mat], (x0, x1, y0, y1, z0, z1), **kw))


def add_pir(name, group, x0, x1, y0, y1, z0, z1):
    l, b = sorted((d for d in (x1 - x0, y1 - y0, z1 - z0) if d != PIR), reverse=True)
    add(name, group, "PIR", x0, x1, y0, y1, z0, z1, cut=(round(l), round(b), PIR_NOM))


# --- Fundering en vloerframe ------------------------------------------------
g = "A Vloerframe"
LEG_X = [(F0, F0 + 68), (PART_X0, PART_X0 + 68), (XR1 - 68, XR1)]
LEG_Y = [(F0, F0 + 68), (YB1 - 68, YB1)]
for lx in LEG_X:
    for ly in LEG_Y:
        add("Poot", g, "P69", lx[0], lx[1], ly[0], ly[1], Z_POST, Z_LEG)
add("Langsbalk voor", g, "I69", F0, XR1, F0, F1, Z_LEG, Z_DECK0)
add("Langsbalk achter", g, "I69", F0, XR1, YR, YB1, Z_LEG, Z_DECK0)
for x in FLOOR_X:
    add("Dwarsbalk", g, "I69", x, x + S, F1, YR, Z_LEG, Z_DECK0)
for a, b in zip(FLOOR_X, FLOOR_X[1:]):
    add_pir("PIR vloer", g, a + S, b, F1, YR, Z_LEG, Z_DECK0)
add("Vloerplaat beneden", g, "BP12", F0, XR1, F0, YB1, Z_DECK0, Z_DECK)
# onderplaat: restant OSB uit een stuk, uitgespaard rond de poten
za, zb = Z_LEG - OSB_T, Z_LEG
ya, yb = LEG_Y[0][1], LEG_Y[1][0]         # 108, 681: tussen de pootrijen
add("Onderplaat vloer", g, "OSB", F0, XR1, ya, yb, za, zb, cut=(XR1 - F0, YB1 - F0, OSB_T),
    note="uit de dakplaat-rest, 90 graden gedraaid; 6 sparingen 68x68 rond de poten")
for y0, y1 in ((F0, ya), (yb, YB1)):
    for x0, x1 in ((LEG_X[0][1], LEG_X[1][0]), (LEG_X[1][1], LEG_X[2][0])):
        add("Onderplaat vloer", g, "OSB", x0, x1, y0, y1, za, zb, count=False)

# --- Benedenverdieping ------------------------------------------------------
Z0, Z1 = Z_DECK, Z_L_TOP
STUD_H = ROOM_H - 2 * S       # 417


def wall_y(group, xa, xb, ya, yb, zb, studs, label=""):
    """Wand in y-richting: regels plus stijlen op y-posities."""
    add(f"Onderregel{label}", group, "B69", xa, xb, ya, yb, zb, zb + S)
    add(f"Bovenregel{label}", group, "B69", xa, xb, ya, yb, zb + ROOM_H - S, zb + ROOM_H)
    for y in studs:
        add("Stijl", group, "B69", xa, xb, y, y + S, zb + S, zb + ROOM_H - S)


def wall_x(group, ya, yb, zb, studs):
    """Doorlopende wand in x-richting: regels plus stijlen op x-posities."""
    add("Onderregel", group, "B69", F0, XR1, ya, yb, zb, zb + S)
    add("Bovenregel", group, "B69", F0, XR1, ya, yb, zb + ROOM_H - S, zb + ROOM_H)
    for x in studs:
        add("Stijl", group, "B69", x, x + S, ya, yb, zb + S, zb + ROOM_H - S)


g = "B Voorwand beneden"
add("Raamstijl", g, "B69", F0, XL1, F0, F1, Z0, Z1, note="geen regels: kozijn direct op de vloer")
add("Raamstijl", g, "B69", PART_X0, PART_X1, F0, F1, Z0, Z1, note="geen regels: kozijn direct op de vloer")

g = "C Achterwand beneden"
wall_x(g, YB0, YB1, Z0, FLOOR_X)
for a, b in zip(FLOOR_X, FLOOR_X[1:]):
    add_pir("PIR wand", g, a + S, b, YB0, YB1, Z0 + S, Z1 - S)
add("Binnenplaat", g, "LP9", F0, XR1, IN_Y1, YB0, Z0, Z1, note="volle breedte, uit een stuk: geeft houvast in de hoeken")

g = "D Linkerwand beneden"
wall_y(g, F0, XL1, F1, IN_Y1, Z0, SIDE_Y)
for a, b in zip(SIDE_Y, SIDE_Y[1:]):
    add_pir("PIR wand", g, F0, XL1, a + S, b, Z0 + S, Z1 - S)
add("Binnenplaat", g, "LP9", XL1, IN_X0, IN_Y0, IN_Y1, Z0, Z1)

g = "E Scheidingswand"
CAT_Y1 = IN_Y1 - S            # 627
CAT_Y0 = CAT_Y1 - 200         # 427: 200 tussen de stijlen; luikframe 198 breed, zonder binnenframe
FLAP_W, FLAP_H, FLAP_Z = 158, 185, 120     # zaagmaat PetSafe 700 S (breed x hoog); onderkant uitsparing op buikhoogte
CAT_H = FLAP_Z + FLAP_H + 5   # 310: latei net boven het luik; trapzijde open, verandazijde dicht met kattenluik
VENT_W, VENT_H, VENT_Z = 140, 70, 15   # luchtinlaat laag onder het luik: koude lucht blijft beneden, trapkamer houdt warmte
FLAP_FW, FLAP_FH = 198, 236                  # buitenmaat frame (bol, nameten)
FLAP_Y0 = mid(CAT_Y0, CAT_Y1) - FLAP_W // 2
FLAP_Y1 = FLAP_Y0 + FLAP_W
VENT_E = (mid(CAT_Y0, CAT_Y1) - VENT_W // 2, mid(CAT_Y0, CAT_Y1) + VENT_W // 2,
          Z0 + VENT_Z, Z0 + VENT_Z + VENT_H)


def plate(name, group, x0, x1, y0, y1, z0, z1, holes, **kw):
    """Plaat in het y-z-vlak met rechthoekige gaten (y0, y1, z0, z1); eerste stuk telt voor de zaaglijst."""
    ys = sorted({y0, y1} | {e for h in holes for e in h[:2] if y0 < e < y1})
    first = True
    for a, b in zip(ys, ys[1:]):
        zs = [(z0, z1)]
        for h in holes:
            if h[0] <= a and b <= h[1]:
                zs = [s for za, zb in zs for s in ((za, min(zb, h[2])), (max(za, h[3]), zb)) if s[1] - s[0] > 0.01]
        for za, zb in zs:
            if first:
                add(name, group, "LP9", x0, x1, a, b, za, zb, cut=(round(y1 - y0), round(z1 - z0), PLY), **kw)
                first = False
            else:
                add(name, group, "LP9", x0, x1, a, b, za, zb, count=False)


add("Onderregel voorste deel", g, "B69", PART_X0, PART_X1, F1, CAT_Y0, Z0, Z0 + S)
add("Bovenregel", g, "B69", PART_X0, PART_X1, F1, IN_Y1, Z1 - S, Z1)
for y in (F1, CAT_Y0 - S):
    add("Stijl", g, "B69", PART_X0, PART_X1, y, y + S, Z0 + S, Z1 - S)
add("Stijl achter doorgang", g, "B69", PART_X0, PART_X1, CAT_Y1, IN_Y1, Z0, Z1 - S, note="tot op de vloer: geen los stukje onderregel")
add("Latei kattenopening", g, "B69", PART_X0, PART_X1, CAT_Y0, CAT_Y1, Z0 + CAT_H, Z0 + CAT_H + S)
add_pir("PIR wand", g, PART_X0, PART_X1, F1 + S, CAT_Y0 - S, Z0 + S, Z1 - S)
add_pir("PIR boven doorgang", g, PART_X0, PART_X1, CAT_Y0, CAT_Y1, Z0 + CAT_H + S, Z1 - S)
plate("Plaat trapzijde", g, ROOM_X1, ROOM_X1 + PLY, IN_Y0, IN_Y1, Z0, Z1,
      [(CAT_Y0, CAT_Y1, Z0, Z0 + CAT_H)],
      note=f"uit een stuk; doorgang {CAT_Y1 - CAT_Y0}x{CAT_H} uitzagen, randen afronden")
plate("Plaat verandazijde", g, PART_X1, PART_X1 + PLY, CLAD, IN_Y1, Z0, Z1,
      [(FLAP_Y0, FLAP_Y1, Z0 + FLAP_Z, Z0 + FLAP_Z + FLAP_H), VENT_E],
      note=f"uit een stuk; kattenluik {FLAP_W}x{FLAP_H} op {FLAP_Z} boven de vloer en luchtinlaat {VENT_W}x{VENT_H} op {VENT_Z} uitzagen")
plate("Versterking kattenluik", g, PART_X1 - PLY, PART_X1, CAT_Y0, CAT_Y1, Z0, Z0 + CAT_H,
      [(FLAP_Y0, FLAP_Y1, Z0 + FLAP_Z, Z0 + FLAP_Z + FLAP_H), VENT_E],
      note="restplaat, achter de verandaplaat gelijmd tussen de stijlen; uitsparing na het lijmen, door beide platen")

g = "F Rechterwand beneden"
F_STUD = (F0, mid(F0, IN_Y1 - S), IN_Y1 - S)   # voorste stijl op de voorrand, middenstijl precies in het midden
wall_y(g, XR0, XR1, F0, IN_Y1, Z0, F_STUD)
for a, b in zip(F_STUD, F_STUD[1:]):
    add_pir("PIR wand", g, XR0, XR1, a + S, b, Z0 + S, Z1 - S)
add("Binnenplaat", g, "LP9", IN_X1, XR0, CLAD, IN_Y1, Z0, Z1, note="loopt door tot achter de afdekking wandkop")

# --- Tussenvloer ------------------------------------------------------------
g = "G Tussenvloer"
HOLE_X0 = IN_X0
HOLE_NOTE = f"met uitsparing trapgat {HOLE_X1-HOLE_X0}x{HOLE_Y1-HOLE_Y0}"


def plate_with_hole(name, mat, z0, z1, t):
    """Plaat uit één stuk over de hele tussenvloer, met het trapgat eruit: vier vakken rond het gat."""
    boxes = [(F0, XR1, F0, HOLE_Y0), (F0, XR1, HOLE_Y1, YB1), (F0, HOLE_X0, HOLE_Y0, HOLE_Y1), (HOLE_X1, XR1, HOLE_Y0, HOLE_Y1)]
    boxes = [b for b in boxes if b[1] - b[0] > 0.5 and b[3] - b[2] > 0.5]
    for i, b in enumerate(boxes):
        if i == 0:
            add(name, g, mat, *b, z0, z1, cut=(XR1 - F0, YB1 - F0, t), note=HOLE_NOTE)
        else:
            add(name, g, mat, *b, z0, z1, count=False)


plate_with_hole("Vloerplaat bovenkamer", "BP12", Z_MID_T, Z_UP, PLY_F)        # betonplex uit een stuk
plate_with_hole("Onderplaat tussenvloer", "LP9", Z_L_TOP, Z_MID_J, PLY)       # Lightply uit een stuk
add("Rand voor", g, "B69", F0, XR1, F0, F1, Z_MID_J, Z_MID_T)
add("Rand achter", g, "B69", F0, XR1, YR, YB1, Z_MID_J, Z_MID_T)
for x in MID_X:
    add("Balk", g, "B69", x, x + S, F1, YR, Z_MID_J, Z_MID_T)
add("Opvulstrook trapgat", g, "B69", F1, XL1, F1, YR, Z_MID_J, Z_MID_T, note="44x69 rifen: steunt de plaat tot aan het trapgat")
add("Dagkant trapgat links", g, "LP9", XL1, IN_X0, HOLE_Y0, HOLE_Y1, Z_MID_J, Z_MID_T)
add("Raveelbalk trapgat", g, "B69", XL1, HOLE_X1, HOLE_Y1, HOLE_Y1 + S, Z_MID_J, Z_MID_T)
add("Dagkant trapgat voor", g, "LP9", HOLE_X0, HOLE_X1, F1, HOLE_Y0, Z_MID_J, Z_MID_T)
add_pir("PIR tussenvloer", g, XL1, HOLE_X1, HOLE_Y1 + S, YR, Z_MID_T - PIR, Z_MID_T)
for xa, xb in ((HOLE_X1 + S, PART_X0), (PART_X0 + S, MID_X[3]), (MID_X[3] + S, XB)):
    add_pir("PIR tussenvloer", g, xa, xb, F1, YR, Z_MID_T - PIR, Z_MID_T)

# --- Bovenverdieping --------------------------------------------------------
Z0, Z1 = Z_UP, Z_U_TOP
g = "H Voorwand boven"
for x in (F0, XR0):
    add("Hoekstijl", g, "B69", x, x + J, F0, F1, Z0, Z1, note="strak tegen het kozijn, 1 mm speling per kant")

g = "I Achterwand boven"
wall_x(g, YB0, YB1, Z0, BACK_U)
for a, b in zip(BACK_U, BACK_U[1:]):
    add_pir("PIR wand", g, a + S, b, YB0, YB1, Z0 + S, Z1 - S)
add("Binnenplaat", g, "LP9", F0, XR1, IN_Y1, YB0, Z0, Z1, note="volle breedte: houvast in de hoeken; gat d102 voor ventilatiebuis, op buismaat aanpassen")

for g, xa, xb, plya, plyb in (("J Linkerwand boven", F0, XL1, XL1, IN_X0),
                              ("K Rechterwand boven", XR0, XR1, IN_X1, XR0)):
    wall_y(g, xa, xb, F1, IN_Y1, Z0, SIDE_Y)
    add_pir("PIR wand", g, xa, xb, SIDE_Y[0] + S, SIDE_Y[1], Z0 + S, Z1 - S)
    add_pir("PIR wand", g, xa, xb, SIDE_Y[1] + S, SIDE_Y[2], Z0 + S, Z1 - S)
    add("Binnenplaat", g, "LP9", plya, plyb, IN_Y0, IN_Y1, Z0, Z1)

# --- Plafond en dak ---------------------------------------------------------
g = "L Plafond"
add("Plafondplaat", g, "LP9", F0, XR1, F0, YB1, Z_U_TOP, Z_CEIL_J)
add("Rand voor", g, "B69", F0, XR1, F0, F1, Z_CEIL_J, Z_RAFT)
add("Rand achter", g, "B69", F0, XR1, YR, YB1, Z_CEIL_J, Z_RAFT)
CEIL_X = BACK_U
for x in CEIL_X:
    add("Balk", g, "B69", x, x + S, F1, YR, Z_CEIL_J, Z_RAFT)
for a, b in zip(CEIL_X, CEIL_X[1:]):
    add_pir("PIR plafond", g, a + S, b, F1, YR, Z_CEIL_J, Z_CEIL_J + PIR)

g = "M Dak"
BOEI_T = 18                   # boeiboord rondom; sporen en dakplaat zitten erbinnen
RAFT_Y0, RAFT_Y1 = ROOF_Y0 + BOEI_T, ROOF_Y1 - BOEI_T     # -132, 871
RAFT_L = RAFT_Y1 - RAFT_Y0    # 1003
RAFT_H0, RAFT_H1 = round(roof_z(RAFT_Y0) - Z_RAFT), round(roof_z(RAFT_Y1) - Z_RAFT)
SIDE_RAFT = (ROOF_X0 + BOEI_T, ROOF_X1 - BOEI_T - S)        # zijsporen tegen de binnenkant van het zijboeiboord
RAFT_NOTE = f"schuin zagen: voor {RAFT_H0}, achter {RAFT_H1} hoog"
for x in CEIL_X:
    add("Spoor afschot", g, "B69", x, x + S, RAFT_Y0, RAFT_Y1, Z_RAFT, Z_RAFT + RAFT_F,
        cut=(RAFT_L, J, S), note=RAFT_NOTE, extra={"slope": "raft"})
for x in SIDE_RAFT:
    add("Zijspoor", g, "B69", x, x + S, RAFT_Y0, RAFT_Y1, Z_RAFT, Z_RAFT + RAFT_F,
        cut=(RAFT_L, J, S), note=RAFT_NOTE + "; draagt plaatrand, trim en zij-onderplaat", extra={"slope": "raft"})
# rijklossen tussen zijspoor en buitenste spoor: boven voorwand, midden, boven achterwand
KLOS_Y = (F0, mid(F0, YB1) - S // 2, YB1 - S)
for xa, xb in ((SIDE_RAFT[0] + S, CEIL_X[0]), (CEIL_X[-1] + S, SIDE_RAFT[1])):
    for y in KLOS_Y:
        add("Rijklos", g, "B69", xa, xb, y, y + S, Z_RAFT, Z_RAFT + RAFT_F, cut=(xb - xa, J, S),
            note="bovenkant schuin, gelijk met de sporen: aftekenen; gat d16 voor ventilatie", extra={"slope": "raft"})
add("Dakplaat", g, "OSB", ROOF_X0 + BOEI_T, ROOF_X1 - BOEI_T, RAFT_Y0, RAFT_Y1, Z_RAFT + RAFT_F, Z_RAFT + RAFT_F + OSB_T,
    cut=(ROOF_W - 2 * BOEI_T, RAFT_L, OSB_T), note="tussen de boeiboorden", extra={"slope": "deck"})
BOEI0 = Z_RAFT - 33
BOEI_F, BOEI_B = RAFT_F + OSB_T + 33, RAFT_B + OSB_T + 33   # 101, 72
add("Boeiboord links", g, "DK", ROOF_X0, ROOF_X0 + 18, ROOF_Y0, ROOF_Y1, BOEI0, Z_RAFT + RAFT_F + OSB_T,
    cut=(ROOF_L, BOEI_F, 18), note="bovenrand schuin volgens dak", extra={"trim": 1})
add("Boeiboord rechts", g, "DK", ROOF_X1 - 18, ROOF_X1, ROOF_Y0, ROOF_Y1, BOEI0, Z_RAFT + RAFT_F + OSB_T,
    cut=(ROOF_L, BOEI_F, 18), note="bovenrand schuin volgens dak", extra={"trim": 1})
add("Boeiboord voor", g, "DK", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y0, ROOF_Y0 + 18, BOEI0, Z_RAFT + RAFT_F + OSB_T, cut=(ROOF_W - 36, BOEI_F, 18))
add("Boeiboord achter", g, "DK", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y1 - 18, ROOF_Y1, BOEI0, Z_RAFT + RAFT_B + OSB_T, cut=(ROOF_W - 36, BOEI_B, 18))
SOF = Z_RAFT - SOF_T
add("Onderplaat overstek voor", g, "BP12", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y0 + 18, -15, SOF, SOF + SOF_T)
add("Onderplaat overstek achter", g, "BP12", ROOF_X0 + 18, ROOF_X1 - 18, D + 15, ROOF_Y1 - 18, SOF, SOF + SOF_T)
add("Onderplaat overstek links", g, "BP12", ROOF_X0 + 18, -15, -15, D + 15, SOF, SOF + SOF_T)
add("Onderplaat overstek rechts", g, "BP12", W + 15, ROOF_X1 - 18, -15, D + 15, SOF, SOF + SOF_T)

# --- Trap: tegen de linkerwand, stijgt van voor naar achter -------------------
g = "N Trap"
ST_X0 = IN_X0
STRINGER_W = 130     # breedte van het plaatstuk, haaks op de helling
STRIP_W = 30
ST_K = RISE / TREAD                       # helling van de tandlijn
ST_N = (1 + ST_K ** 2) ** 0.5             # verticale maat per mm haaks op de helling


def _outer(y):
    """Lijn door de buitenhoeken van de tanden (begin van elk zitvlak)."""
    return Z_DECK + 2 * RISE - PLY_F + ST_K * (y - TREAD_Y[1])


def _bottom(y):
    """Rechte onderkant van de boom, evenwijdig aan de tandlijn."""
    return _outer(y) - STRINGER_W * ST_N


ST_FOOT = TREAD_Y[0] + (Z_DECK - _bottom(TREAD_Y[0])) / ST_K   # waar de onderkant de vloer raakt


def _stringer_fwd():
    """Zijaanzicht trapboom (y, z) in de rekenrichting: rechte voet, schuine voorkant tot het eerste zitvlak, zaagtanden, rechte onderkant."""
    seat = [Z_DECK + RISE * (i + 1) - PLY_F for i in range(N_RISE - 1)]
    b = TREAD_Y[1:]
    pts = [(ST_Y0, Z_DECK), (ST_Y0, _outer(ST_Y0)), (b[0] - TREAD, seat[0])]
    for i, y in enumerate(b):
        pts += [(y, seat[i]), (y, seat[i + 1])]
    pts += [(ST_Y1, seat[-1]), (ST_Y1, _bottom(ST_Y1)), (ST_FOOT, Z_DECK)]
    return pts


def _tab_fwd():
    """Lip aan de bovenkant van de vrije (rechter)boom, in de rekenrichting: steekt in het trapgat omhoog langs de balk
    rechts van het trapgat en wordt daarin geschroefd."""
    return SY(TAB_Y1), SY(TAB_Y0)


def stringer_fwd(free=False):
    """Trapboom in de rekenrichting (voor het plaatstuk). free: de rechterboom, met de lip bovenaan."""
    pts = _stringer_fwd()
    if free:
        seat = Z_DECK + RISE * (N_RISE - 1) - PLY_F
        i = next(k for k in range(len(pts) - 1) if pts[k][1] == seat and pts[k + 1] == (ST_Y1, seat))
        a, b = _tab_fwd()
        pts = pts[:i + 1] + [(a, seat), (a, TAB_Z1), (b, TAB_Z1), (b, seat)] + pts[i + 1:]
    return pts


def stringer_outline(free=False):
    """Zijaanzicht trapboom (y, z) zoals hij staat. free: de rechterboom, met de lip bovenaan."""
    return [(SY(y), z) for y, z in stringer_fwd(free)]


def strip_fwd():
    """Versterkingsstrook in de rekenrichting: rechthoek langs de rechte onderkant van de rechterboom, haakse uiteinden."""
    a, b = (ST_FOOT, Z_DECK), (ST_Y1, _bottom(ST_Y1))
    dy, dz = -STRIP_W * ST_K / ST_N, STRIP_W / ST_N
    return [a, b, (b[0] + dy, b[1] + dz), (a[0] + dy, a[1] + dz)]


def strip_outline():
    """Zijaanzicht versterkingsstrook zoals hij zit."""
    return [(SY(y), z) for y, z in strip_fwd()]


def _blank_length():
    proj = [(y + ST_K * z) / ST_N for y, z in stringer_fwd(free=True)]   # met de lip: beide bomen uit hetzelfde maatstuk
    return max(proj) - min(proj)


assert all(d == TREAD for d in TREAD_D[1:-1]) and ST_Y0 < TREAD_Y[1] - TREAD
STRINGER_L = math.ceil((_blank_length() + 3) / 5) * 5                   # 815: plaatstuk met lip, 3 mm marge
STRIP_L = math.floor((ST_Y1 - ST_FOOT) * ST_N / 10) * 10                # 630: langs de onderkant
ST_CORNER = STRINGER_W - RISE / ST_N      # hout dat bij de binnenhoeken overblijft, ca. 60
# de lip moet binnen de breedte van het plaatstuk blijven: onder de lijn door de buitenhoeken
assert TAB_Z1 <= _outer(SY(TAB_Y1)) - 1, ("lip steekt buiten het plaatstuk", TAB_Z1, _outer(SY(TAB_Y1)))

add("Trapboom", g, "BP12", ST_X0, ST_X0 + PLY_F, *SY2(ST_Y0, ST_Y1), Z_DECK, Z_UP,
    cut=(STRINGER_L, STRINGER_W, PLY_F), note="zaagtanden, zie detail 6", extra={"stringer": 1})
add("Trapboom", g, "BP12", ST_X1 - PLY_F, ST_X1, *SY2(ST_Y0, ST_Y1), Z_DECK, Z_UP,
    cut=(STRINGER_L, STRINGER_W, PLY_F), extra={"stringer": 3},
    note=f"zaagtanden en lip {TAB_Y1 - TAB_Y0} breed bovenaan, zie detail 6")
add("Versterkingsstrook trapboom", g, "BP12", ST_X1 - 2 * PLY_F, ST_X1 - PLY_F, *SY2(ST_FOOT - STRIP_W, ST_Y1),
    Z_DECK, _bottom(ST_Y1) + STRIP_W * ST_N, cut=(STRIP_L, STRIP_W, PLY_F),
    note="binnenkant rechterboom, langs de onderkant; uit de reststrook", extra={"stringer": 2})
for i in range(N_RISE - 1):
    z = Z_DECK + RISE * (i + 1)
    notch = i == N_RISE - 2
    add("Trede", g, "BP12", ST_X0, ST_X1, *TREAD_AT[i], z - PLY_F, z,
        note=f"op de tanden; rechts inkeping {PLY_F} x {TAB_Y1 - TAB_Y0} voor de lip, {TAB_Y0 - TREAD_AT[i][0]} uit de voorkant; anti-slip bekleden"
        if notch else "op de tanden; anti-slip bekleden")

# --- Spouwlatten ---------------------------------------------------------------
g = "P Spouwlatten"
ZC0, ZC1 = CLAD_Z0, CLAD_Z1
for x in BACK_U:
    add("Lat achter", g, "LAT", x, x + S, YB1, YB1 + BAT, ZC0, ZC1)
for y in (F0, SIDE_Y[1], YB0):
    add("Lat links", g, "LAT", CLAD, F0, y, y + S, ZC0, ZC1)
    add("Lat rechts", g, "LAT", XR1, XR1 + BAT, y, y + S, ZC0, ZC1)
for x in (XL1 - S, XR0):
    add("Lat voor hoek", g, "LAT", x, x + S, CLAD, F0, ZC0, ZC1)
add("Lat voor beneden", g, "LAT", PART_X0 + (J - S) // 2, PART_X0 + (J + S) // 2, CLAD, F0, ZC0, Z_UP - S)
add("Lat kop raam boven", g, "LAT", XL1, XR0, CLAD, F0, Z_U_TOP, Z_U_TOP + S, note="10 mm onderbreken voor ventilatie")
add("Lat band tussenvloer", g, "LAT", XL1, XR0, CLAD, F0, Z_UP - S, Z_UP, note="bovenkant gelijk met vloer: kozijn steunt erop")
for xa, xb in ((XL1, PART_X0), (PART_X1, XR0)):
    add("Lat voorrand vloer", g, "LAT", xa, xb, CLAD, F0, Z_DECK - S, Z_DECK, note="bovenkant gelijk met vloer")

# --- Gevelbekleding ------------------------------------------------------------
g = "Q Gevelbekleding"
ROWS_Z = [(ZC0 + BOARD * k, ZC0 + BOARD * (k + 1)) for k in range(N_BOARD)] + [(ZC1 - TOP_STRIP, ZC1)]
for za, zb in ROWS_Z:
    note = "" if zb - za == BOARD else "bovenste rij: plank rifen, tong eraf"
    add("Plank achter", g, "DG", 58, W - 58, D - CLAD, D, za, zb, note=note)
    add("Plank links", g, "DG", 0, CLAD, 58, D - 58, za, zb, note=note)
    add("Plank rechts", g, "DG", W - CLAD, W, 58, D - 58, za, zb, note=note)
for x, y0 in ((0, 0), (W - 58, 0), (0, D - CLAD), (W - 58, D - CLAD)):
    add("Hoeklat frontbreed", g, "DK", x, x + 58, y0, y0 + CLAD, ZC0, ZC1)
for x, y0 in ((0, CLAD), (W - CLAD, CLAD), (0, D - 58), (W - CLAD, D - 58)):
    add("Hoeklat zijkant", g, "DK", x, x + CLAD, y0, y0 + F0, ZC0, ZC1)
# voorkant: kader rond de ramen, dezelfde beits als de gevel. De kaderdelen sluiten op het kozijn aan.
add("Kaderstijl boven links", g, "DM", 58, WIN_X0, 0, CLAD, Z_UP, ZC1)
add("Kaderstijl boven rechts", g, "DM", WIN_X0 + WIN_U_W, W - 58, 0, CLAD, Z_UP, ZC1)
add("Kader boven raam", g, "DM", WIN_X0, WIN_X0 + WIN_U_W, 0, CLAD, Z_U_TOP, ZC1)
add("Band tussenvloer", g, "DM", 58, W - 58, 0, CLAD, Z_L_TOP, Z_UP)
add("Kaderstijl beneden links", g, "DM", 58, WIN_X0, 0, CLAD, Z_DECK, Z_L_TOP)
add("Kaderstijl beneden rechts", g, "DM", WIN_X0 + WIN_L_W, VER_X0, 0, CLAD, Z_DECK, Z_L_TOP)
add("Voorrand vloer", g, "DM", 58, W - 58, 0, CLAD, ZC0, Z_DECK)
add("Afdekking wandkop veranda", g, "DM", IN_X1, W - 58, 0, CLAD, Z_DECK, Z_L_TOP, note="dekt de open wandkop af")
CANOPY_DROP = 12              # luifel loopt over 90 mm dit stuk af naar voren
add("Regenluifel", g, "DK", 58, W - 58, -90, 0, Z_L_TOP + 12 - CANOPY_DROP, Z_L_TOP + 30,
    cut=(W - 116, 91, 18), note="tussen de hoeklatten, 12 mm aflopend naar voren; op 5 RVS consoles, EPDM met druiprand",
    extra={"slope": "canopy"})

# Niet-houten onderdelen die wel in de tekeningen moeten staan.
# Ramen binnenstebuiten: de kozijnkant die normaal binnen zit, is gelijk met de gevel.
# De vleugel steekt 19 mm naar buiten uit en draait naar buiten open.
WIN_U = dict(x0=WIN_X0, x1=WIN_X0 + WIN_U_W, y0=0, y1=WIN_D, z0=Z_UP, z1=Z_UP + WIN_H)
WIN_L = dict(x0=WIN_X0, x1=WIN_X0 + WIN_L_W, y0=0, y1=WIN_D, z0=Z_DECK, z1=Z_DECK + WIN_H)
SIGHT_U, SIGHT_L = 118, 101
VENT = dict(x=mid(BACK_U[3] + S, BACK_U[4]), z=Z_U_TOP - S - 60, d=100)


# --- Controles ---------------------------------------------------------------
def overlap(a, b, tol=0.01):
    return all(min(a[i + 1], b[i + 1]) - max(a[i], b[i]) > tol for i in (0, 2, 4))


def collisions():
    out = []
    for i, p in enumerate(parts):
        if p.extra.get("slope") or p.extra.get("stringer") or p.extra.get("trim"):
            continue   # schuine delen: bounding box is geen werkelijke vorm
        for q in parts[i + 1:]:
            if q.extra.get("slope") or q.extra.get("stringer") or q.extra.get("trim"):
                continue
            if overlap(p.box, q.box):
                out.append((p.group, p.name, q.group, q.name))
    return out


def _inside(pt, poly):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _cross(p1, p2, q1, q2):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(p1, p2, q1) * d(p1, p2, q2) < 0 and d(q1, q2, p1) * d(q1, q2, p2) < 0


def stringer_clashes(tol=0.5):
    """Botsingen van de werkelijke vorm van de trapbomen (zijaanzicht) met andere onderdelen in hun breedte."""
    out = []
    for p in parts:
        k = p.extra.get("stringer")
        if k not in (1, 3):
            continue
        poly = stringer_outline(free=(k == 3))
        for q in parts:
            if q is p or q.extra.get("stringer") or q.extra.get("slope") or q.extra.get("trim"):
                continue
            if min(p.box[1], q.box[1]) - max(p.box[0], q.box[0]) <= tol:
                continue
            y0, y1, z0, z1 = q.box[2] + tol, q.box[3] - tol, q.box[4] + tol, q.box[5] - tol
            if y1 <= y0 or z1 <= z0:
                continue
            if q.name == "Trede" and k == 3 and "inkeping" in q.note:
                continue        # de lip gaat door de inkeping van de bovenste trede
            rc = [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]
            hit = any(y0 < a < y1 and z0 < b < z1 for a, b in poly) or any(_inside(c_, poly) for c_ in rc) or \
                any(_cross(a, b, c_, d_) for a, b in zip(poly, poly[1:] + poly[:1]) for c_, d_ in zip(rc, rc[1:] + rc[:1]))
            if hit:
                out.append((p.group, p.name + (" rechts" if k == 3 else " links"), q.group, q.name))
    return out


def window_clearance():
    """Raamkozijnen mogen niets raken; meld wat overlapt."""
    res = []
    for label, w in (("raam boven", WIN_U), ("raam beneden", WIN_L)):
        b = (w["x0"], w["x1"], w["y0"], w["y1"], w["z0"], w["z1"])
        for p in parts:
            if not (p.extra.get("slope") or p.extra.get("trim")) and overlap(p.box, b):
                res.append((label, p.group, p.name))
    return res


def stair_headroom():
    """Kleinste vrije hoogte tussen een trede en de onderkant van de tussenvloer vóór het trapgat."""
    best = None
    for i in range(N_RISE - 1):
        ya, yb = TREAD_AT[i]
        if ya < HOLE_Y0 - S or yb > HOLE_Y1 + S:   # deze trede ligt nog onder de dichte vloer
            best = ROOM_H - RISE * (i + 1)
    return best


def cutlist():
    rows = defaultdict(int)
    for p in parts:
        if p.count:
            rows[(p.group, p.name, p.mat, p.dims(), p.note)] += 1
    return [dict(group=k[0], name=k[1], mat=k[2], dims=k[3], note=k[4], qty=v) for k, v in sorted(rows.items())]


DENS = {"R44": 480, "B69": 480, "I69": 520, "P69": 520, "LP9": 400, "BP12": 700, "OSB": 620, "PIR": 35, "LAT": 480, "DG": 530, "DK": 530, "DM": 530}


def weight():
    inv = {v: k for k, v in MAT.items()}
    total = 0
    for p in parts:
        if p.count:
            d = p.dims()
            f = 0.6 if p.extra.get("slope") == "raft" else 1
            total += d[0] * d[1] * d[2] * 1e-9 * DENS[inv[p.mat]] * f
    return total + 15.5 + 10.42 + 6.0 + 8.0   # ramen, EPDM + beslag, verwarming/elektra


if __name__ == "__main__":
    c = collisions()
    print("onderdelen:", len(parts), "zaagregels:", len(cutlist()))
    print("hoogte:", Z_TOP, "binnen boven:", IN_X1 - IN_X0, IN_Y1 - IN_Y0, ROOM_H)
    print("trapkamer:", ROOM_X1 - IN_X0, "veranda:", IN_X1 - VER_X0, "voet bekleding:", CLAD_Z0)
    print("buiten:", W, D, "dak:", ROOF_W, ROOF_L, "opening boven:", XR0 - XL1, "beneden:", PART_X0 - XL1)
    print("trap: optrede", round(RISE, 1), "treden", TREAD_D, "boom", STRINGER_L, "x", STRINGER_W, "strook", STRIP_L, "binnenhoek", round(ST_CORNER), "vrije hoogte onder dichte vloer:", round(stair_headroom()))
    print("botsingen:", len(c), "trapbomen:", stringer_clashes())
    for row in c:
        print("  ", row)
    print("raamconflicten:", window_clearance())
    print("gewicht kg:", round(weight()))
