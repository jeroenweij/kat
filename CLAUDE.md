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

## Commands

```bash
pip install reportlab openpyxl pypdf     # in a venv; the system Python may lack them
cd bouwplan
python3 model.py          # geometry checks: part count, collisions, window clearance, weight
python3 berekening.py     # heat, ventilation, energy, stability figures
python genereer.py        # writes the PDF and XLSX; aborts on any geometry conflict
```

The Inkoop tab of the XLSX contains the user's own edits and is the source of truth: `genereer.py` reads the PDF purchase list from it and leaves the file alone. Only `genereer.py --xlsx` rewrites the workbook, which destroys those edits. Edit the workbook in place with openpyxl instead, then recalculate it, because openpyxl writes formulas without cached values.

## Architecture

`model.py` is the single source of truth. Every physical piece is a `Part` with a position box, in mm: x left to right seen from the front, y front to back, z up from the top of the footing. `genereer.py` derives the elevations, sections, plans, wall frames, 3D views, cutting list, sheet layouts and stock quantities from those parts, and `berekening.py` takes the weight from it. Change a dimension in the model and regenerate rather than patching drawings or lists.

Exceptions that need updating by hand when the geometry changes:
- `details_page` in `genereer.py` draws details with hand-entered coordinates.
- Many dimension calls and all narrative text in `write_drawings` and `write_text` contain literal values.
- `heat()` in `berekening.py` has some hand-entered areas.
- `purchase()` is only used by `--xlsx` and no longer matches the workbook. The timber lengths in the workbook were optimised by hand; after a geometry change, redo them.

## Current design decisions (Rev I, 6-11-2026)

User decisions:
- Hornbach is the preferred supplier.
- Windows: Hornbach kelderraam 100 x 50 (art. 12074105) upstairs, ARON Basic+ 50 x 50 (art. 12331530) in the stair room. They replace the DHK 80 x 60 in the handoff. The user expects 500 to be the outer frame size; this is unconfirmed until measured on delivery.
- Windows are mounted inside out, flush with the facade and opening outward, to give access from outside. There are no access hatches. Do not reintroduce hatches. The manufacturer does not intend this mounting and water is the main risk; the plan records this and adds a tray, upstand, sill and canopy.
- Rooms about 500 mm high: the model uses 540 mm clear (window 500, 30 upstand, 10 joint), with no wall plates at the windows. Total height is about 1585 mm.
- Right side of the veranda is fully closed: a room with an open front. Small passage to the stair room as drawn (190 x 260).
- Stairs against the left wall.
- Wall lining in Lightply 9 mm, 2440 x 1220 sheets (art. 12575686, interior grade), using as little material as possible, because exterior grade is unnecessary indoors. Floors in betonplex 12 mm (art. 12628592).
- Claude's extension of those choices: ceiling and mid-floor underside also Lightply; stairs and roof soffit also betonplex 12.

- Facade stain: Hornbach Hybride houtbeits mahonie 2,5 l (art. 5509572) instead of Remmers HK-Lazuur.
- Only corner boards and fascias are anthracite: Hornbach Hybride houtbeits RAL 7016 antraciet 375 ml (art. 10277101) instead of Jotun Demidekk. It is translucent, so the grain stays visible. Window frame, band, front edge and canopy are mahogany like the rest of the facade. All these strips are sawn from the same planks and stained afterwards.
- Facade membrane: MIOFOL 125G (art. 7049802), Sd 0,28 m. Water-tightness class and UV exposure limit not found.
- Corner boards are self-made on the user's table saw from Douglas planks: an L of 58 x 58 (58 x 18 plus 40 x 18), flush with the cladding, which butts against it. Not a ready-made profile on top of the planks.
- The strip sawing layout assumes the full 145 mm plank width. After removing tongue and groove, 130 mm or less needs 6 planks instead of 5; the purchase list has 2 spare planks. Measure a plank, then redo the layout if needed.
- Heating and electrical costs are left out of the purchase list for now; the design still includes them.

Recommendations the user has accepted:
- Alu-faced PIR 40 mm throughout, with no extra vapour foil.
- PVC vent of Ø75 with adjustable grille instead of Ø40.
- Mains heating as the main source instead of solar and battery.
- Anchored footings with tension-proof post holders.

Still to verify: window outer sizes and hinge side on delivery; Hornbach availability of impregnated 44 x 69, 22 x 44 battens and the PIR facing; a specific heater model.

## Working rules from the handoff

- Label every statement as a final choice, a preference, or an assumption still to be checked.
- Do not invent product specifications or current prices. Verify supplier information before recommending an order, and leave an unverified price blank.
- Check advice on ventilation, condensation, vapour control, insulation and electrical safety carefully, and design for Dutch weather.
- Mains connection and changeover are for a qualified installer.
- Keep the cat safety list in `projectoverdracht` section 10 in view. Tilted windows are a known fatal risk for cats, so the design requires tilt guards.
