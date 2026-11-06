"""Parametrisch model van het kattenchalet (Rev I).

Alle maten in mm. Assen, gezien vanaf de voorkant:
  x = links -> rechts, y = voorkant -> achterkant, z = omhoog (0 = bovenkant poer).
Elk onderdeel is een Part met een positie. De zaaglijst, tekeningen en
botsingscontrole komen allemaal uit deze ene lijst.
"""
from dataclasses import dataclass, field
from collections import defaultdict

# --- Hoofdmaten -------------------------------------------------------------
W, D = 1300, 900              # buitenmaat gevelbekleding
CLAD, BAT = 18, 22            # gevelplank, spouwlat
S, J = 44, 69                 # regel 44x44 en balk 44x69
PLY, PLY_F = 9, 12            # Lightply wand/plafond, betonplex vloer
OSB_T, SOF_T = 18, 12         # dakplaat, overstekplaat (betonplex)
PIR = 40
ROOM_H = 540                  # vrije hoogte: raam 500 + 30 onder (opstand) + 10 boven

Z_LEG = 180                   # bovenkant poer -> onderkant vloerframe
Z_DECK0 = Z_LEG + J           # 249
Z_DECK = Z_DECK0 + PLY_F      # 267: vloer beneden
Z_L_TOP = Z_DECK + ROOM_H     # 807
Z_MID_J = Z_L_TOP + PLY       # 813
Z_MID_T = Z_MID_J + J         # 882
Z_UP = Z_MID_T + PLY_F        # 900: vloer bovenkamer
Z_U_TOP = Z_UP + ROOM_H       # 1440
Z_CEIL_J = Z_U_TOP + PLY      # 1446
Z_RAFT = Z_CEIL_J + J         # 1515
RAFT_F, RAFT_B = 57, 28       # spoorhoogte voor / achter (afschot naar achter)
RO_F, RO_B, RO_S = 150, 100, 100   # dakoverstek voor, achter, zijkant
ROOF_Y0, ROOF_Y1 = -RO_F, D + RO_B
ROOF_X0, ROOF_X1 = -RO_S, W + RO_S
Z_TOP = Z_RAFT + RAFT_F + OSB_T + 1.2
BOARD = 135                   # werkende breedte gevelplank
CLAD_Z1 = Z_RAFT - SOF_T        # 1509: bovenkant bekleding, onder de overstekplaat
CLAD_Z0 = CLAD_Z1 - 10 * BOARD   # 159

# binnenvlakken
IN_X0, IN_X1 = 84 + PLY, 1216 - PLY       # bovenkamer links/rechts
IN_Y0, IN_Y1 = 84 + PLY, 816 - PLY        # voor/achter
PART_X0, PART_X1 = 604, 648   # scheidingswand: regelwerk
ROOM_X1 = PART_X0 - PLY       # 598: rechterkant trapkamer
VER_X0 = PART_X1 + PLY        # 654: linkerkant veranda


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
    "LP9": "Lightply 9 (Falcata, binnen)",
    "BP12": "Betonplex 12",
    "OSB": "OSB-3 18",
    "PIR": "PIR 40 alu",
    "LAT": "Spouwlat 22x44",
    "DG": "Douglas 18x145 (hout zichtbaar)",
    "DK": "Douglas 18x145 (hoek/boei antraciet)",
    "DM": "Douglas 18x145 (kader mahonie)",
}
parts = []


def add(name, group, mat, x0, x1, y0, y1, z0, z1, **kw):
    parts.append(Part(name, group, MAT[mat], (x0, x1, y0, y1, z0, z1), **kw))


# --- Fundering en vloerframe ------------------------------------------------
g = "A Vloerframe"
LEG_X = [(40, 108), (604, 672), (1192, 1260)]
for lx in LEG_X:
    for ly in [(40, 108), (792, 860)]:
        add("Poot", g, "P69", lx[0], lx[1], ly[0], ly[1], 80, Z_LEG)
add("Langsbalk voor", g, "I69", 40, 1260, 40, 84, Z_LEG, Z_DECK0)
add("Langsbalk achter", g, "I69", 40, 1260, 816, 860, Z_LEG, Z_DECK0)
for x in (40, 322, 604, 910, 1216):
    add("Dwarsbalk", g, "I69", x, x + S, 84, 816, Z_LEG, Z_DECK0)
add("Vloerplaat beneden", g, "BP12", 40, 1260, 40, 860, Z_DECK0, Z_DECK)

# --- Benedenverdieping ------------------------------------------------------
Z0, Z1 = Z_DECK, Z_L_TOP
STUD_H = ROOM_H - 2 * S       # 452


def wall_y(group, xa, xb, ya, yb, zb, studs, label=""):
    """Wand in y-richting: regels plus stijlen op y-posities."""
    add(f"Onderregel{label}", group, "R44", xa, xb, ya, yb, zb, zb + S)
    add(f"Bovenregel{label}", group, "R44", xa, xb, ya, yb, zb + ROOM_H - S, zb + ROOM_H)
    for y in studs:
        add("Stijl", group, "R44", xa, xb, y, y + S, zb + S, zb + ROOM_H - S)


def wall_x(group, ya, yb, zb, studs):
    """Doorlopende wand in x-richting: regels plus stijlen op x-posities."""
    add("Onderregel", group, "R44", 40, 1260, ya, yb, zb, zb + S)
    add("Bovenregel", group, "R44", 40, 1260, ya, yb, zb + ROOM_H - S, zb + ROOM_H)
    for x in studs:
        add("Stijl", group, "R44", x, x + S, ya, yb, zb + S, zb + ROOM_H - S)


# dorpelregel: draagt het kozijn, blijft 8 mm onder het raam voor stelblokjes
DORP = BAT                    # 22 hoog
g = "B Voorwand beneden"
for x in (40, PART_X0):
    add("Raamstijl", g, "R44", x, x + S, 40, 84, Z0, Z1, note="geen regels: raam tussen vloer en plafond")
add("Dorpelregel raam", g, "LAT", 84, PART_X0, 40, 84, Z0, Z0 + DORP, note="22 hoog, 44 breed; EPDM-goot erover")
add("Opstand binnen", g, "LP9", 84, PART_X0, 84, IN_Y0, Z0, Z0 + 30, note="opstand 30 mm; EPDM-goot eroverheen")

g = "C Achterwand beneden"
wall_x(g, 816, 860, Z0, (40, 334, PART_X0, 910, 1216))
add("Binnenplaat trapkamer", g, "LP9", IN_X0, ROOM_X1, IN_Y1, 816, Z0, Z1)
add("Binnenplaat veranda", g, "LP9", VER_X0, IN_X1, IN_Y1, 816, Z0, Z1)

g = "D Linkerwand beneden"
wall_y(g, 40, 84, 84, 816, Z0, (84, 428, 772))
add("Binnenplaat", g, "LP9", 84, IN_X0, IN_Y0, IN_Y1, Z0, Z1)

g = "E Scheidingswand"
CAT_Y0, CAT_Y1, CAT_H = 582, 772, 260
add("Onderregel voorste deel", g, "R44", PART_X0, PART_X1, 84, CAT_Y0, Z0, Z0 + S)
add("Onderregel achterste deel", g, "R44", PART_X0, PART_X1, CAT_Y1, 816, Z0, Z0 + S)
add("Bovenregel", g, "R44", PART_X0, PART_X1, 84, 816, Z1 - S, Z1)
for y in (84, 340, CAT_Y0 - S, CAT_Y1):
    add("Stijl", g, "R44", PART_X0, PART_X1, y, y + S, Z0 + S, Z1 - S)
add("Latei kattenopening", g, "R44", PART_X0, PART_X1, CAT_Y0, CAT_Y1, Z0 + CAT_H, Z0 + CAT_H + S)
for lbl, xa in (("trapzijde", ROOM_X1), ("verandazijde", PART_X1)):
    add(f"Plaat {lbl} voor", g, "LP9", xa, xa + PLY, IN_Y0, CAT_Y0, Z0, Z1)
    add(f"Plaat {lbl} achter", g, "LP9", xa, xa + PLY, CAT_Y1, IN_Y1, Z0, Z1)
    add(f"Plaat {lbl} boven opening", g, "LP9", xa, xa + PLY, CAT_Y0, CAT_Y1, Z0 + CAT_H, Z1)

g = "F Rechterwand beneden"
wall_y(g, 1216, 1260, 40, 816, Z0, (40, 84, 428, 772))
add("Binnenplaat", g, "LP9", IN_X1, 1216, 40, IN_Y1, Z0, Z1, note="dicht tot aan de voorzijde")

# --- Tussenvloer ------------------------------------------------------------
g = "G Tussenvloer"
HOLE_X0, HOLE_X1, HOLE_Y0, HOLE_Y1 = IN_X0, 340, 440, IN_Y1
HOLE_NOTE = f"met uitsparing trapgat {HOLE_X1-HOLE_X0}x{HOLE_Y1-HOLE_Y0}"
# bovenplaat: betonplex uit een stuk
z0, z1 = Z_MID_T, Z_UP
add("Vloerplaat bovenkamer", g, "BP12", 40, 1260, 40, HOLE_Y0, z0, z1, cut=(1220, 820, PLY_F), note=HOLE_NOTE)
add("Vloerplaat bovenkamer", g, "BP12", 40, HOLE_X0, HOLE_Y0, 860, z0, z1, count=False)
add("Vloerplaat bovenkamer", g, "BP12", HOLE_X1, 1260, HOLE_Y0, 860, z0, z1, count=False)
add("Vloerplaat bovenkamer", g, "BP12", HOLE_X0, HOLE_X1, HOLE_Y1, 860, z0, z1, count=False)
# onderplaat: Lightply uit een stuk
z0, z1 = Z_L_TOP, Z_MID_J
add("Onderplaat tussenvloer", g, "LP9", 40, 1260, 40, HOLE_Y0, z0, z1, cut=(1220, 820, PLY),
    note=HOLE_NOTE + ", plus 6 ventilatiegaten d10 met gaas")
add("Onderplaat tussenvloer", g, "LP9", 40, HOLE_X0, HOLE_Y0, 860, z0, z1, count=False)
add("Onderplaat tussenvloer", g, "LP9", HOLE_X1, 1260, HOLE_Y0, 860, z0, z1, count=False)
add("Onderplaat tussenvloer", g, "LP9", HOLE_X0, HOLE_X1, HOLE_Y1, 860, z0, z1, count=False)
add("Rand voor", g, "B69", 40, 1260, 40, 84, Z_MID_J, Z_MID_T)
add("Rand achter", g, "B69", 40, 1260, 816, 860, Z_MID_J, Z_MID_T)
MID_X = (40, 340, PART_X0, 910, 1216)
for x in MID_X:
    add("Balk", g, "B69", x, x + S, 84, 816, Z_MID_J, Z_MID_T)
add("Raveelbalk trapgat", g, "B69", 84, 340, HOLE_Y0 - S, HOLE_Y0, Z_MID_J, Z_MID_T)
add("Dagkant trapgat links", g, "LP9", 84, IN_X0, HOLE_Y0, IN_Y1, Z_MID_J, Z_MID_T)
add("Dagkant trapgat achter", g, "LP9", HOLE_X0, HOLE_X1, IN_Y1, 816, Z_MID_J, Z_MID_T)
add("PIR tussenvloer", g, "PIR", 84, 340, 84, HOLE_Y0 - S, Z_MID_T - PIR, Z_MID_T)
for xa, xb in ((384, PART_X0), (PART_X1, 910), (954, 1216)):
    add("PIR tussenvloer", g, "PIR", xa, xb, 84, 816, Z_MID_T - PIR, Z_MID_T)

# --- Bovenverdieping --------------------------------------------------------
Z0, Z1 = Z_UP, Z_U_TOP
g = "H Voorwand boven"
for x, nm in ((40, "Hoekstijl"), (96, "Raamstijl"), (1160, "Raamstijl"), (1216, "Hoekstijl")):
    add(nm, g, "R44", x, x + S, 40, 84, Z0, Z1, note="geen regels: raam tussen vloer en plafond")
add("Dorpelregel raam", g, "LAT", 140, 1160, 40, 84, Z0, Z0 + DORP, note="22 hoog, 44 breed; EPDM-goot erover")
add("Opstand binnen", g, "LP9", 140, 1160, 84, IN_Y0, Z0, Z0 + 30, note="opstand 30 mm; EPDM-goot eroverheen")
add("Binnenplaat links raam", g, "LP9", IN_X0, 140, 84, IN_Y0, Z0, Z1)
add("Binnenplaat rechts raam", g, "LP9", 1160, IN_X1, 84, IN_Y0, Z0, Z1)

g = "I Achterwand boven"
BACK_U = (40, 334, 628, 922, 1216)
wall_x(g, 816, 860, Z0, BACK_U)
for a, b in zip(BACK_U, BACK_U[1:]):
    add("PIR wand", g, "PIR", a + S, b, 820, 860, Z0 + S, Z1 - S)
add("Binnenplaat", g, "LP9", IN_X0, IN_X1, IN_Y1, 816, Z0, Z1, note="gat d78 voor ventilatiebuis")

for g, xa, xb, pa, pb, plya, plyb in (("J Linkerwand boven", 40, 84, 40, 80, 84, IN_X0),
                                      ("K Rechterwand boven", 1216, 1260, 1220, 1260, IN_X1, 1216)):
    wall_y(g, xa, xb, 84, 816, Z0, (84, 428, 772))
    add("PIR wand", g, "PIR", pa, pb, 128, 428, Z0 + S, Z1 - S)
    add("PIR wand", g, "PIR", pa, pb, 472, 772, Z0 + S, Z1 - S)
    add("Binnenplaat", g, "LP9", plya, plyb, IN_Y0, IN_Y1, Z0, Z1)

# --- Plafond en dak ---------------------------------------------------------
g = "L Plafond"
add("Plafondplaat", g, "LP9", 40, 1260, 40, 860, Z_U_TOP, Z_CEIL_J)
add("Rand voor", g, "B69", 40, 1260, 40, 84, Z_CEIL_J, Z_RAFT)
add("Rand achter", g, "B69", 40, 1260, 816, 860, Z_CEIL_J, Z_RAFT)
CEIL_X = (40, 334, 628, 922, 1216)
for x in CEIL_X:
    add("Balk", g, "B69", x, x + S, 84, 816, Z_CEIL_J, Z_RAFT)
for a, b in zip(CEIL_X, CEIL_X[1:]):
    add("PIR plafond", g, "PIR", a + S, b, 84, 816, Z_CEIL_J, Z_CEIL_J + PIR)

g = "M Dak"
for x in CEIL_X:
    add("Spoor afschot", g, "B69", x, x + S, ROOF_Y0, ROOF_Y1, Z_RAFT, Z_RAFT + RAFT_F,
        cut=(1150, 69, 44), note=f"schuin zagen: voor {RAFT_F}, achter {RAFT_B} hoog", extra={"slope": "raft"})
add("Dakplaat", g, "OSB", ROOF_X0, ROOF_X1, ROOF_Y0, ROOF_Y1, Z_RAFT + RAFT_F, Z_RAFT + RAFT_F + OSB_T,
    cut=(1500, 1150, 18), extra={"slope": "deck"})
BOEI0 = Z_RAFT - 33
add("Boeiboord links", g, "DK", ROOF_X0, ROOF_X0 + 18, ROOF_Y0, ROOF_Y1, BOEI0, Z_RAFT + RAFT_F + 18,
    cut=(1150, 108, 18), note="bovenrand schuin volgens dak", extra={"trim": 1})
add("Boeiboord rechts", g, "DK", ROOF_X1 - 18, ROOF_X1, ROOF_Y0, ROOF_Y1, BOEI0, Z_RAFT + RAFT_F + 18,
    cut=(1150, 108, 18), note="bovenrand schuin volgens dak", extra={"trim": 1})
add("Boeiboord voor", g, "DK", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y0, ROOF_Y0 + 18, BOEI0, Z_RAFT + RAFT_F + 18, cut=(1464, 108, 18))
add("Boeiboord achter", g, "DK", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y1 - 18, ROOF_Y1, BOEI0, Z_RAFT + RAFT_B + 18, cut=(1464, 79, 18))
SOF = Z_RAFT - SOF_T
add("Onderplaat overstek voor", g, "BP12", ROOF_X0 + 18, ROOF_X1 - 18, ROOF_Y0 + 18, -15, SOF, SOF + SOF_T)
add("Onderplaat overstek achter", g, "BP12", ROOF_X0 + 18, ROOF_X1 - 18, D + 15, ROOF_Y1 - 18, SOF, SOF + SOF_T)
add("Onderplaat overstek links", g, "BP12", ROOF_X0 + 18, -15, -15, D + 15, SOF, SOF + SOF_T)
add("Onderplaat overstek rechts", g, "BP12", W + 15, ROOF_X1 - 18, -15, D + 15, SOF, SOF + SOF_T)

# --- Trap: tegen de linkerwand, stijgt van voor naar achter -------------------
g = "N Trap"
ST_X0, ST_X1, ST_Y0, ST_Y1 = IN_X0, 340, 150, IN_Y1
N_RISE = 7
RISE = (Z_UP - Z_DECK) / N_RISE      # 90,4
TREAD = (ST_Y1 - ST_Y0) / (N_RISE - 1)   # 110
STRINGER_L = round(((ST_Y1 - ST_Y0) ** 2 + (Z_UP - Z_DECK) ** 2) ** 0.5 + 20)
for x in (ST_X0, ST_X1 - PLY_F):
    add("Trapboom", g, "BP12", x, x + PLY_F, ST_Y0, ST_Y1, Z_DECK, Z_UP,
        cut=(STRINGER_L, 130, PLY_F), note="schuin, zie detailblad", extra={"stringer": 1})
for i in range(N_RISE - 1):
    z = Z_DECK + RISE * (i + 1)
    ya = ST_Y0 + TREAD * i
    add("Trede", g, "BP12", ST_X0 + PLY_F, ST_X1 - PLY_F, ya, ya + TREAD - 4, z - PLY_F, z, note="anti-slip bekleden")

# --- Spouwlatten ---------------------------------------------------------------
g = "P Spouwlatten"
ZC0, ZC1 = CLAD_Z0, CLAD_Z1
for x in BACK_U:
    add("Lat achter", g, "LAT", x, x + S, 860, 882, ZC0, ZC1)
for y in (40, 428, 816):
    add("Lat links", g, "LAT", 18, 40, y, y + S, ZC0, ZC1)
    add("Lat rechts", g, "LAT", 1260, 1282, y, y + S, ZC0, ZC1)
for x in (40, 1216):
    add("Lat voor hoek", g, "LAT", x, x + S, 18, 40, ZC0, ZC1)
add("Lat voor beneden", g, "LAT", PART_X0, PART_X1, 18, 40, ZC0, Z_L_TOP)
BAND_T = Z_L_TOP + S
for x in (96, 1160):
    add("Lat voor boven", g, "LAT", x, x + S, 18, 40, BAND_T, ZC1)
add("Lat kop raam boven", g, "LAT", 140, 1160, 18, 40, Z_U_TOP, Z_U_TOP + S, note="10 mm onderbreken voor ventilatie")
add("Lat dorpel raam boven", g, "LAT", 140, 1160, 18, 40, Z_UP, Z_UP + DORP, note="op de platte kant, 22 hoog")
add("Lat dorpel raam beneden", g, "LAT", 84, PART_X0, 18, 40, Z_DECK, Z_DECK + DORP, note="op de platte kant, 22 hoog")
add("Lat band boven raam", g, "LAT", 84, PART_X0, 18, 40, Z_L_TOP, BAND_T)
add("Lat band veranda", g, "LAT", PART_X1, 1216, 18, 40, Z_L_TOP, BAND_T)
for xa, xb in ((84, PART_X0), (PART_X1, 1216)):
    add("Lat voorrand vloer", g, "LAT", xa, xb, 18, 40, 185, 229)

# --- Gevelbekleding ------------------------------------------------------------
g = "Q Gevelbekleding"
K = lambda k: ZC0 + BOARD * k
for k in range(10):
    add("Plank achter", g, "DG", 58, 1242, 882, 900, K(k), K(k + 1))
    add("Plank links", g, "DG", 0, 18, 58, 842, K(k), K(k + 1))
    add("Plank rechts", g, "DG", 1282, 1300, 58, 842, K(k), K(k + 1))
for x, y0 in ((0, 0), (1242, 0), (0, 882), (1242, 882)):
    add("Hoeklat frontbreed", g, "DK", x, x + 58, y0, y0 + 18, ZC0, ZC1)
for x, y0 in ((0, 18), (1282, 18), (0, 842), (1282, 842)):
    add("Hoeklat zijkant", g, "DK", x, x + 18, y0, y0 + 40, ZC0, ZC1)
# voorkant: kader rond de ramen, mahonie zoals de gevel
add("Kaderstijl boven links", g, "DM", 58, 140, 0, 18, Z_UP, ZC1)
add("Kaderstijl boven rechts", g, "DM", 1160, 1242, 0, 18, Z_UP, ZC1)
add("Kader boven raam", g, "DM", 140, 1160, 0, 18, Z_U_TOP, ZC1)
add("Kader onder raam", g, "DM", 140, 1160, 0, 18, Z_UP, Z_UP + DORP)
add("Band tussenvloer", g, "DM", 58, 1242, 0, 18, Z_L_TOP, Z_UP)
add("Kaderstijl beneden links", g, "DM", 58, 84, 0, 18, Z_DECK, Z_L_TOP)
add("Kaderstijl beneden rechts", g, "DM", PART_X0, VER_X0, 0, 18, Z_DECK, Z_L_TOP)
add("Kader onder raam beneden", g, "DM", 84, PART_X0, 0, 18, Z_DECK, Z_DECK + DORP)
add("Voorrand vloer", g, "DM", 58, 1242, 0, 18, ZC0, Z_DECK)
add("Afdekking wandkop veranda", g, "DM", IN_X1, 1242, 0, 18, Z_DECK, Z_L_TOP, note="dekt de open wandkop af")
add("Regenluifel raam beneden", g, "DM", 64, 624, -90, 0, Z_L_TOP + 12, Z_L_TOP + 30,
    note="op 3 RVS consoles, alu kap, afschot naar voren")

# Niet-houten onderdelen die wel in de tekeningen moeten staan.
# Ramen binnenstebuiten: de kozijnkant die normaal binnen zit, is gelijk met de gevel.
# De vleugel steekt 19 mm naar buiten uit en draait naar buiten open.
WIN_U = dict(x0=150, x1=1150, y0=0, y1=71, z0=Z_UP + 30, z1=Z_UP + 530)
WIN_L = dict(x0=94, x1=594, y0=0, y1=71, z0=Z_DECK + 30, z1=Z_DECK + 530)
SIGHT_U, SIGHT_L = 118, 101
VENT = dict(x=1069, z=Z_U_TOP - S - 50, d=75)


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
        ya = ST_Y0 + TREAD * i
        if ya < HOLE_Y0 - S:              # deze trede ligt nog onder de dichte vloer
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
    print("trap: optrede", round(RISE, 1), "aantrede", TREAD, "vrije hoogte onder dichte vloer:", round(stair_headroom()))
    print("botsingen:", len(c))
    for row in c:
        print("  ", row)
    print("raamconflicten:", window_clearance())
    print("gewicht kg:", round(weight()))
