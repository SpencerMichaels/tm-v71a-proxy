"""Simplified 3D model of the Molex Micro-Fit 3.0 43045-0200 (2 circuit, dual row, right angle).

KiCad's library has no model for this footprint, so this script makes a visual stand-in for
renders: the housing is the footprint's F.Fab outline extruded to the 10.3 mm mated height,
with two mating cavities and the two pins. It is not a dimensioned Molex model.

Run:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd make_microfit_model.py
Writes Molex_Micro-Fit_3.0_43045-0200_simplified.step next to this file.
Coordinates follow KiCad's model convention: footprint origin (pin 1), X right, Y = -footprint Y.
"""
import os
import FreeCAD as App
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
H = 10.3                     # housing height above the board
# F.Fab outline from Molex_Micro-Fit_3.0_43045-0200_2x01_P3.00mm_Horizontal (footprint Y negated)
outline = [(-3.575, -0.99), (-3.575, 7.92), (-2.575, 8.92), (2.575, 8.92), (3.575, 7.92), (3.575, -0.99)]
wire = Part.makePolygon([V(x, y, 0) for x, y in outline] + [V(*outline[0], 0)])
housing = Part.Face(wire).extrude(V(0, 0, H))
for zc in (3.3, 6.3):        # two mating cavities, open toward the board edge (+Y)
    housing = housing.cut(Part.makeBox(2.9, 7.0, 2.9, V(-1.45, 8.92 - 7.0, zc - 1.45)))
pin = 0.64
pins = Part.makeBox(pin, pin, 3.0 + 3.3, V(-pin / 2, -pin / 2, -3.0))                 # pin 1, lower row
p2v = Part.makeBox(pin, pin, 3.0 + 6.3, V(-pin / 2, -3.0 - pin / 2, -3.0))            # pin 2, rises behind
p2h = Part.makeBox(pin, 3.0 - 0.99 + pin, pin, V(-pin / 2, -3.0 - pin / 2, 6.3 - pin / 2))  # and runs in
shape = housing.fuse([pins, p2v, p2h]).removeSplitter()
shape.exportStep(os.path.join(HERE, 'Molex_Micro-Fit_3.0_43045-0200_simplified.step'))
print('ok', shape.isValid(), shape.Volume)
