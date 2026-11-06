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
- Compact size, replacing the 1300 x 900 from the handoff: the 1000 mm upper window fits exactly between the inner linings of the left and right wall, with no window studs beside it. Outer 1236 x 789, roof 1436 x 1039, total height about 1508 mm. Interior depth 600 mm, measured from the back of the window frame to the rear lining.
- Window frames sit directly on the floor, with no sill batten and no wooden upstand. The frame sides are flush with the linings (9 mm joint to the studs). The model keeps a 5 mm joint above the frame, so rooms are 505 mm clear: the user asked for the frame directly against the ceiling, and this joint is Claude's addition, for the EPDM and sill under the frame and to keep the structure off the frame.
- Window fixing follows the ARON RC recommendation in `kozijn/as.187466663.pdf`, adapted by Claude: wood frame, inside-out mounting and the kelderraam are not covered by it. Max. 150 mm from inner corners, max. 600 mm apart, packed at each fixing, sides and top only because a screw through the bottom pierces the EPDM. Screws 7,5 x 112: the 44 mm stud by the veranda rules out anything longer, so embedment is 36-43 mm rather than the 60 mm the document asks of masonry.
- Water protection without the upstand (Claude's detail, an assumption not tested in practice): EPDM under the frame, a 30 mm EPDM lip glued up behind the frame. Alu sill profile 34 x 17 (art. 10295993, T-shaped) screwed to the face of the band, top flush with the floor, with the EPDM lapped over it, so nothing but EPDM lies under the frame.
- Right side of the veranda is fully closed: a room with an open front. Small passage to the stair room as drawn (190 x 260). Stair room 500 wide, veranda 438 wide.
- Stairs against the left wall, from the user's drawing: 45°, 6 rises of 99 at 99 going, sawtooth stringers (the user's choice, for the look) 850 x 130 with about 60 mm left at the inner corners, the free right one stiffened with a glued 580 x 30 strip along its lower edge, treads 110 x 247 resting on the teeth and overlapping by 11, stairwell 247 x 343. The stringer foot is 5 mm behind the frame, clear of the EPDM lip.
- Wall lining in Elliotis Pine 9 mm, 2440 x 1220 sheets (art. 10000081, C+/C, interior per Hornbach), clear-lacquered with no white primer so the grain shows like `Inspiratie.png`. It replaces Lightply; glue and formaldehyde class not found. Floors in betonplex 12 mm (art. 12628592).
- Claude's extension of those choices: ceiling and mid-floor underside also Elliotis Pine; stairs and roof soffit also betonplex 12.
- Roof deck: OSB-III 11 mm, 2440 x 1220 (art. 10222931), instead of 18 mm. The user chose this after hearing that screws hold poorly in 11 mm, so the plan has the trim screws run into the fascia and says not to stand on the roof.

- Facade stain: Hornbach Hybride houtbeits grenen 2,5 l (art. 5509568) instead of mahogany, closer to `Inspiratie.png`; expected warmer and redder on Douglas, so test first. Interior walls: TENCO Bootlak blank mat (art. 10728553, indoor and outdoor, at least 3 coats, solvent-based, manufacturer names hardwood only).
- Only corner boards, fascias and the canopy are anthracite. The canopy runs between the corner boards between the floors, 1120 x 91 x 18, falling 12 mm towards the front, on 5 stainless brackets, with an EPDM offcut on top: Hornbach Hybride houtbeits RAL 7016 antraciet 750 ml (art. 10277060, about 0,55 l for 3 coats all round) instead of Jotun Demidekk. It is translucent, so the grain stays visible. Window frame, band and front edge have the same stain as the rest of the facade. All these strips are sawn from the same planks and stained afterwards.
- Facade membrane: MIOFOL 125G (art. 7049802), Sd 0,28 m. Water-tightness class and UV exposure limit not found.
- Corner boards are self-made on the user's table saw from Douglas planks: an L of 58 x 58 (58 x 18 plus 40 x 18), flush with the cladding, which butts against it. Not a ready-made profile on top of the planks.
- The top row of cladding is a ripped strip of 65 mm, above 9 full boards.
- The strip sawing layout assumes the full 145 mm plank width. After removing tongue and groove, 130 mm or less needs 6 planks instead of 5; the purchase list has 2 spare planks. Measure a plank, then redo the layout if needed.
- Heating and electrical costs are left out of the purchase list for now; the design still includes them.
- Location: terrace in Rijswijk ZH, in the corner by a fence 1,8 m high whose posts have no concrete. Back to the fence, windows to the terrace. Loose tiles, falling across the chalet. The rear wall stays at least 250 mm from the fence (Claude's figure: 100 mm roof overhang plus gutter).
- Footing: 6 concrete footings 300 x 300 x 500 under the tiles, with KAISERTHAL U post holders (art. 3896646) set in the fresh concrete; the anchor rod passes through a Ø25 hole in the tile. Not screwed to the tiles alone, and not fixed to the fence. Fixed height, so the slope is taken up by the rod length and by cutting the posts. To remove: cut the rods and replace the 6 tiles; the concrete stays hidden in the ground.

Recommendations the user has accepted:
- Alu-faced PIR with no extra vapour foil. The user chose 70 mm (art. 10368509, Rd 3,15, pack of 7 = 5,04 m²) over 40 mm and accepted 5 cm extra width. Side and rear walls are framed in 44 x 69, the partition stays 44 x 44 without PIR. Leftover PIR goes in the outer walls of the stair room and veranda and in the ground floor, for less waste rather than for heat. The ground floor is closed below with 11 mm OSB from the roof sheet offcut, notched around the 6 legs. The 1 mm mesh is not used there: it is too thin against mice. The sheet is 1 mm thicker than the 69 mm framing; the model draws it 69.
- PVC vent of Ø100 (the user has an offcut) with closable grille inside (art. 4152757) and a grille outside (art. 8610839), instead of Ø40. Insect protection for the vent and cavity: 304 stainless mesh, 20 mesh, about 1 mm opening, 40 x 200 cm (Amazon B0DL5P11F2), because Hornbach only has 6,3 mm. The opening is derived from the listing and must be measured on delivery.
- Mains heating as the main source instead of solar and battery.
- Anchored footings with tension-proof post holders.

Still to verify: holder dimensions on delivery (Hornbach gives no tensile strength, embedment or meaning of the sizes; the plan assumes a 100 mm U and a 200 mm rod, with at least 90 mm in the concrete); tile size and pattern; soil under the terrace; window outer sizes and hinge side on delivery; Hornbach availability of impregnated 44 x 69 and the PIR facing; use class of the battens (art. 2094248, 21 x 45 x 2500, 1 mm off the drawn 22 x 44, which the model keeps); a specific heater model.

## Working rules from the handoff

- Label every statement as a final choice, a preference, or an assumption still to be checked.
- Do not invent product specifications or current prices. Verify supplier information before recommending an order, and leave an unverified price blank.
- Check advice on ventilation, condensation, vapour control, insulation and electrical safety carefully, and design for Dutch weather.
- Mains connection and changeover are for a qualified installer.
- Keep the cat safety list in `projectoverdracht` section 10 in view. Tilted windows are a known fatal risk for cats, so the design requires tilt guards.
