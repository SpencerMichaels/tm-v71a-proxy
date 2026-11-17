# Kenwood proxy Rev A enclosure

This is a two-piece printed case for the 54 × 52 mm board. The front wall has openings for **J1 (BODY)**, **J2 (HEAD)** and **J3 (ILL, Micro-Fit)**. J4 (programming) and JP1 are fully enclosed: the board only goes in the case once the firmware is final.

| File | Purpose |
|---|---|
| `kp_case_base.stl` | Tray with four board standoffs. Print floor-down. |
| `kp_case_cover.stl` | Cover, already flipped to print **top-down**. |
| `kp_case.step` | Both parts in assembly position, for CAD. |
| `build_enclosure.py` | Parametric generator. Re-run after changing a dimension (see below). |
| `preview_*.png`, `build_report.txt` | Renders and the fit-check result. |

## Size and fit

- **Outside:** 59 × 57 × 25.6 mm, a plain box with 3 mm rounded corners and nothing sticking out to snag the wiring.
- **Inside:** 0.5 mm clearance around the board.
- **Below the board:** 4 mm, for trimmed leads and connector pegs.
- **Above the board:** 16 mm. The tallest part is the 4P4C jack at 14.5 mm.
- **Openings:** 0.5 mm clearance around each connector face. Connector faces sit 2.5 mm behind the outside of the front wall, which leaves the 4P4C latches and the Micro-Fit release lever outside the case where you can press them.
- **Fit check:** the generator checks the case against envelopes of every tall part, the board outline and each connector face. The result is **PASS** (`build_report.txt`).

## Before printing: measure J3

The J3 opening is sized for a Micro-Fit 43045-0200 header **10.3 mm tall**, from Molex's 10.29 mm mated height, plus 3 mm above it for the plug's latch lever and a fingertip. When the DigiKey parts arrive, measure the real header with calipers. If it differs, change `MICROFIT_H` in `build_enclosure.py` and re-run:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_enclosure.py
```

The 4P4C jack height (14.5 mm) comes from Würth's datasheet.

## Printing (PrusaSlicer)

- **Material:** **PETG or ASA**, not PLA. A dash in summer sun can get hot enough for PLA to soften and creep.
- **Orientation:**
  - Base: floor on the bed.
  - Cover: top on the bed. It's exported that way, so the engraved labels print as the first layers.
- **Supports:** none needed.
- **Settings:** 0.2 mm layers, 3 perimeters, 20–30 % infill.
- **Test print first:** print the cover once and check it against the assembled board before relying on it. The pillars between the openings are 2–3 mm wide and fine in PETG, but don't pry on them.

## Hardware and assembly

- **4 × M3 × 14 mm screws** (pan or socket head). They go in from underneath, through the base standoffs and the board's mounting holes, and thread into 2.6 mm pilot holes in the cover posts, about 6.4 mm of engagement. Ordinary machine screws cut their own thread in PETG, or use thread-forming screws for plastic. There are no counterbores: the heads sit about 2–3 mm proud of the underside, which keeps each standoff joined to a solid floor.
- **Assembly:** set the board on the base standoffs, lower the cover over the connectors (the lip around the base locates it), then screw from below. The cover posts clamp the board onto the standoffs.
- **Mounting:** none needed; it can sit in the wiring bundle. If it rattles, wrap it with the bundle in fabric harness tape, or put thick foam tape or Velcro pads on the base between the screw heads.
