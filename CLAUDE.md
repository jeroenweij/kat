# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A building design project, not a software product: a modern wooden outdoor chalet for a cat that also stays outside at night. The directory is a git repository (origin: github.com/jeroenweij/kat). The user works in Dutch, and all deliverables are in Dutch.

## Files

- `projectoverdracht`: the original handoff document (Dutch). Source of requirements and working rules. Where it conflicts with `bouwplan/`, the later user decisions below win.
- `Inspiratie.png`: concept image for style only. Its dimensions contradict the design, so never use them.
- `bouwplan/Kattenchalet_bouwplan.pdf`: the generated plan (drawings, calculations, cutting list, purchasing, steps). Do not edit by hand.
- `bouwplan/Kattenchalet_zaag_en_inkooplijst.xlsx`: lists, generated once and since edited by the user. Do not regenerate it without asking.
- `bouwplan/model.py`, `berekening.py`, `genereer.py`: the sources.
- `bouwplan/Betonplex_zaagplan_trap.dxf`: the user's own drawing, a puzzle to cut the betonplex more efficiently, with the stairs drawn out piece by piece. Hand-made: the scripts do not read or update it.
- `matverwarming/`: 12 V heated cat mat: 5 JLCPCB flex heater segments forming a ring. The segment shape comes from the user's `Ontwerp.dxf`; `heater.py` reads it, writes the Gerbers and checks clearances; `LEESMIJ.md` has the order settings and the remark.
- `controller/`: ESP32 controller for the mat (5 segments each with NTC and MOSFET, 12 V room heater, fan, INA226, SHT40, DS18B20). `maak_schema.py` generates the KiCad 9 schematic (edit the script, not the schematic); `esphome/` holds the ESPHome config. `LEESMIJ.md` lists the pin map and safety logic.
- `kozijn/`: Hornbach and ARON window documents, git-ignored. Only `as.187466663.pdf` covers mounting.

## Commands

```bash
pip install reportlab openpyxl pypdf     # in a venv; the system Python may lack them
cd bouwplan
python3 model.py          # geometry checks: part count, collisions, window clearance, weight
python3 berekening.py     # heat, ventilation, energy, stability figures
python genereer.py        # writes the PDF and XLSX; aborts on any geometry conflict
```

The Inkoop tab of the XLSX contains the user's own edits and is the source of truth: `genereer.py` reads the PDF purchase list from it and leaves the file alone. `genereer.py --lijsten` rewrites only the tabs that follow from the model (Zaaglijst, Latten op lengte, Platen op maat). Only `genereer.py --xlsx` rewrites the whole workbook, which destroys those edits. Edit Inkoop in place with openpyxl instead. After any openpyxl write, recalculate the workbook (for example a headless LibreOffice convert) and only then generate the PDF, because openpyxl writes formulas without cached values and the PDF reads those values.

## Architecture

`model.py` is the single source of truth. Every physical piece is a `Part` with a position box, in mm: x left to right seen from the front, y front to back, z up from the highest terrace tile. The outer size is derived: width from `WIN_U_W`, depth from `IN_DEPTH`, room height from `WIN_H + WIN_JOINT`. `genereer.py` derives the elevations, sections, plans, wall frames, 3D views, cutting list, sheet layouts and stock quantities from those parts, and `berekening.py` takes the weight from it. Change a dimension in the model and regenerate rather than patching drawings or lists.

Exceptions that need updating by hand when the geometry changes:
- `details_page` in `genereer.py` draws details with hand-entered coordinates.
- Many dimension calls and all narrative text in `write_drawings` and `write_text` contain literal values.
- `purchase()` is only used by `--xlsx` and no longer matches the workbook. After a geometry change, update the quantities in the Inkoop tab from what `genereer.py` prints. `STOCK` in `genereer.py` holds the timber lengths and prices used to choose the cheapest mix, and must follow the Inkoop tab.

## Current design decisions (Rev K, 6-11-2026)

User decisions:
- Hornbach is the preferred supplier.
- Windows: Hornbach kelderraam 100 x 50 (art. 12074105) upstairs, ARON Basic+ 50 x 50 (art. 12331530) in the stair room. They replace the DHK 80 x 60 in the handoff. The user expects 500 to be the outer frame size; this is unconfirmed until measured on delivery.
- Windows are mounted inside out, flush with the facade and opening outward, to give access from outside. There are no access hatches. Do not reintroduce hatches. The manufacturer does not intend this mounting and water is the main risk; the plan records this and adds a tray, sill and canopy.
- Compact size, replacing the 1300 x 900 from the handoff: the 1000 mm upper window sits between two corner posts. Outer 1220 x 789, roof 1420 x 1039, total height about 1508 mm. Interior depth 600 mm, measured from the back of the window frame to the rear lining.
- Window frames sit directly on the floor, with no sill batten and no wooden upstand. Since 9-11-2026 (user's choice) the posts beside both windows (B and H) go tight against the frame with 1 mm play per side (WIN_GAP), so the chalet is 1220 wide. The posts are fixed for good only after the window is set. The linings stand 8 mm proud of the frame inside, so the upper room is 984 wide and the stair room 484. The side joints get no wedges and no compriband (it needs 5-10 mm), only sealant outside. The user had first misunderstood flush frame and lining as a requirement. The model keeps a 5 mm joint above the frame, so rooms are 505 mm clear: the user asked for the frame directly against the ceiling, and this joint is Claude's addition, for the EPDM and sill under the frame and to keep the structure off the frame.
- Window fixing follows the ARON RC recommendation in `kozijn/as.187466663.pdf`, adapted by Claude: wood frame, inside-out mounting and the kelderraam are not covered by it. Max. 150 mm from inner corners, max. 600 mm apart, packed at each fixing (now only the 5 mm head joint, with 6 mm wedges; at the sides the post is the packing), sides and top only because a screw through the bottom pierces the EPDM. Screws 7,5 x 112: the 44 mm stud by the veranda rules out anything longer, so embedment is 36-43 mm rather than the 60 mm the document asks of masonry.
- Water protection without the upstand (Claude's detail, an assumption not tested in practice): EPDM under the frame, a 30 mm EPDM lip glued up behind the frame. Alu sill profile 34 x 17 (art. 10295993, T-shaped) screwed to the face of the band, top flush with the floor, with the EPDM lapped over it, so nothing but EPDM lies under the frame.
- Right side of the veranda is fully closed: a room with an open front. Small passage to the stair room as drawn (190 x 260). Stair room 484 wide, veranda 413 wide (the thicker partition takes 25 mm from the veranda).
- The rear inner lining runs the full width in one piece on both floors, and the side walls and partition stop against it, so the lining has wood to screw into at the corners (the user's detail).
- Battens: 10 of 2500 are enough with joints (20,3 m needed). The 'Latten op lengte' tab still shows whole pieces (13).
- Stairs against the left wall, from the user's drawing: 45°, 6 rises of 99 at 99 going, sawtooth stringers (the user's choice, for the look) 850 x 130 with about 60 mm left at the inner corners, the free right one stiffened with a glued 580 x 30 strip along its lower edge, treads 110 x 247 resting on the teeth and overlapping by 11, stairwell 247 x 343. The stringer foot is 5 mm behind the frame, clear of the EPDM lip.
- Wall lining in Elliotis Pine 9 mm, 2440 x 1220 sheets (art. 10000081, C+/C, interior per Hornbach), clear-lacquered with no white primer so the grain shows like `Inspiratie.png`. It replaces Lightply; glue and formaldehyde class not found. Floors in betonplex 12 mm (art. 12628592).
- Claude's extension of those choices: ceiling and mid-floor underside also Elliotis Pine; stairs and roof soffit also betonplex 12.
- Roof deck: OSB-III 11 mm, 2440 x 1220 (art. 10222931), instead of 18 mm. The user chose this after hearing that screws hold poorly in 11 mm, so trim screws must land in a rafter, side rafter or fascia, and the plan says not to stand on the roof.
- Roof framing (9-11-2026): rafters and deck sit inside the 18 mm fascias, so rafters are 1003 long; with fascias the outer roof is 1420 x 1039 (deck 1384 x 1003 since the 1220 width). The user added a side rafter of the same sloped shape inside each side fascia, tied to the outer rafter with 3 blocks (rijklossen) of 78 mm, each with a 16 mm vent hole. They carry the deck edge, the trim screws and the side soffit.
- Rear beams (9-11-2026): the rear beam of the floor frame and the rear edges of the mid floor and ceiling are 44 x 69 on the outside (YR in the model), not 69 x 69. Joists run 25 mm further, to 621. Behind the stairwell a 25 mm PIR strip fills the gap.
- Veranda linings (9-11-2026): the plates on the veranda side of wall E and on wall F run to 18 mm behind the front, against the frame post and the wall-end cover, so both are 653 long. On the stair-room side and upstairs the linings stop against the window frame, at 600.
- Wall linings are cut 4 mm short (501) and sit 4 mm above the floor with a sealant joint; the model and cutting list still show 505.
- Stappenplan (rewritten 9-11-2026 after a walk-through as a novice): it sets the build order, including PIR placed only after the walls are screwed together from the open bays, and the vent pipe placed before the cladding. It also holds hand-derived positions: the doorway in wall E, the stairwell, the vent hole and the overhangs. Recheck these after a geometry change.

- Roof materials ordered (9-11-2026, Dakvoordeelshop, invoice FDV021639, delivery week 46, 88,71 incl. VAT; invoice line amounts are incl. VAT): EPDM 1,14 mm 1,52 x 1,30 m, Coverbond contact adhesive 1 l, 2 EPDM sealant 290 ml, 2 alu trims Brute 35 x 28 x 2500 with 3 joining plates, stainless trim screws 4,5 x 35 (25). They replace Premiumfol, the Premiumfol adhesives and the SOLOTRIM 60 x 55. The EPDM is laid with 1520 across the width and 30 mm down the fascias. The rest is about 1520 x 200, enough for the upper-window strip only: the lower-window strip, the canopy top and a possible EPDM flap in the doorway need an extra piece (suggested 1,52 x 0,30 m, not ordered yet).
- Facade stain: Hornbach Hybride houtbeits grenen 2,5 l (art. 5509568) instead of mahogany, closer to `Inspiratie.png`; expected warmer and redder on Douglas, so test first. Interior walls: TENCO Bootlak blank mat (art. 10728553, indoor and outdoor, at least 3 coats, solvent-based, manufacturer names hardwood only).
- Only corner boards, fascias and the canopy are anthracite. The canopy runs between the corner boards between the floors, 1120 x 91 x 18, falling 12 mm towards the front, on 5 stainless brackets, with an EPDM offcut on top: Hornbach Hybride houtbeits RAL 7016 antraciet 750 ml (art. 10277060, about 0,55 l for 3 coats all round) instead of Jotun Demidekk. It is translucent, so the grain stays visible. Window frame, band and front edge have the same stain as the rest of the facade. All these strips are sawn from the same planks and stained afterwards.
- Facade membrane: MIOFOL 125G (art. 7049802), Sd 0,28 m. Water-tightness class and UV exposure limit not found.
- Corner boards are self-made on the user's table saw from Douglas planks: an L of 58 x 58 (58 x 18 plus 40 x 18), flush with the cladding, which butts against it. Not a ready-made profile on top of the planks.
- The top row of cladding is a ripped strip of 65 mm, above 9 full boards.
- The strip sawing layout assumes the full 145 mm plank width. After removing tongue and groove, 130 mm or less needs 6 planks instead of 5; the purchase list has 2 spare planks. Measure a plank, then redo the layout if needed.
- Heating and electrical costs are left out of the purchase list for now; the design still includes them.
- Power (7-11-2026): no 230 V at the chalet; everything runs on a 12 V battery. This overrides the earlier mains heating and the 120 W tube heater in the plan (detail 8, purchase list, `berekening.py` text), which are not yet updated. Heat: the 5-segment heated mat in `matverwarming/` (about 17 W) plus a 12 V 100 W PTC air heater (FABULETTA, Amazon B0GVNRHWS2, 113 x 35 x 26 mm) behind the steel cage, only when the room is below 8 °C; the mat only when the room is below 15 °C. The ESP32 controller in `controller/` sheds the heater first, then the mat, on low supply voltage. The battery part of this decision is superseded by the power supply decision below.
- Power supply (9-11-2026, user's choice; overrides the battery at the chalet in the 7-11 decision): no battery at the chalet. Phase 1 (now): a 24 V mains supply in the shed (preference: LightingWill/HUAKE 24 V 250 W IP67 with plug, Amazon, about 50 euro; the user found the Mean Well GST280A24 too expensive and the 20 euro Jandei IP20 needs mains wiring), helped by a heater soft start in ESPHome (LEDC PWM on GPIO 23, ramp 30-100 % over 60 s, adjustable max power) so 250 W is enough for the cold PTC inrush; it feeds about 10 m of H07RN-F 3G2.5 cable (buy 12-15 m; brown +24 V, blue 0 V, green-yellow cut back and insulated, never used as a conductor; YMvK 3 x 2.5 in conduit if it runs under the tiles) to a plain Victron Orion-Tr 24/12-20 isolated (ORI241224110, no Bluetooth, fixed 12.2 V) in the chalet. The user rejected the Smart version (about 100 euro more) because nothing in the chalet needs to be adjustable or read out. The ESPHome shed thresholds are therefore 11.5 V (heater) and 11.3 V (mat), a safety net below the 12.2 V; the PCB is not changed for 24 V now. Phase 2 (later): a 24 V battery, solar with MPPT and mains backup (diode-OR, mains takes over only when the battery is low and never charges it) all in the shed, so the chalet always gets 24 V over the same cable; then GPIO 33 measures the 24 V (top divider resistor about 220k, 24 V minus tied to GND). Still no 230 V at the chalet. Details, energy figures, rejected options and open points: `controller/VOEDING.md`.
- Location: terrace in Rijswijk ZH, in the corner by a fence 1,8 m high whose posts have no concrete. Back to the fence, windows to the terrace. Loose tiles, falling across the chalet. The rear wall stays at least 250 mm from the fence (Claude's figure: 100 mm roof overhang plus gutter).
- Footing: 6 concrete footings 300 x 300 x 500 under the tiles, with KAISERTHAL U post holders (art. 3896646) set in the fresh concrete; the anchor rod passes through a Ø25 hole in the tile. Not screwed to the tiles alone, and not fixed to the fence. Fixed height, so the slope is taken up by the rod length and by cutting the posts. To remove: cut the rods and replace the 6 tiles; the concrete stays hidden in the ground.

Recommendations the user has accepted:
- Alu-faced PIR with no extra vapour foil. The user chose 70 mm (art. 10368509, Rd 3,15, pack of 7 = 5,04 m²) over 40 mm and accepted 5 cm extra width. Side and rear walls are framed in 44 x 69. Since 9-11-2026 the partition E and its window post are 44 x 69 too, with PIR (user's choice); no 44 x 44 is bought any more. PIR also goes in the outer walls of the stair room and veranda and in the ground floor; all 7 sheets of the pack are used, with no spare, for less waste rather than for heat. The ground floor is closed below with 11 mm OSB from the roof sheet offcut, notched around the 6 legs. The 1 mm mesh is not used there: it is too thin against mice. The sheet is 1 mm thicker than the 69 mm framing; the model draws it 69.
- PVC vent of Ø100 (the user has an offcut) with closable grille inside (art. 4152757) and a grille outside (art. 8610839), instead of Ø40. Insect protection for the vent and cavity: 304 stainless mesh, 20 mesh, about 1 mm opening, 40 x 200 cm (Amazon B0DL5P11F2), because Hornbach only has 6,3 mm. The opening is derived from the listing and must be measured on delivery.
- Anchored footings with tension-proof post holders.

Still to verify: holder dimensions on delivery (Hornbach gives no tensile strength, embedment or meaning of the sizes; the plan assumes a 100 mm U and a 200 mm rod, with at least 90 mm in the concrete); tile size and pattern; soil under the terrace; window outer sizes and hinge side on delivery; Hornbach availability of impregnated 44 x 69 and the PIR facing; use class of the battens (art. 2094248, 21 x 45 x 2500, 1 mm off the drawn 22 x 44, which the model keeps); a specific heater model.

## Working rules from the handoff

- Label every statement as a final choice, a preference, or an assumption still to be checked.
- Do not invent product specifications or current prices. Verify supplier information before recommending an order, and leave an unverified price blank.
- Check advice on ventilation, condensation, vapour control, insulation and electrical safety carefully, and design for Dutch weather.
- Mains connection and changeover are for a qualified installer.
- Keep the cat safety list in `projectoverdracht` section 10 in view. Tilted windows are a known fatal risk for cats, so the design requires tilt guards.
