#!/usr/bin/env freecadcmd
"""Fit check: every solid of the exported board (case/board.step) against both case halves.
The jack STEP sits 4.1 mm off its footprint (the WRL KiCad renders is right), so the jacks are moved to the
footprint's courtyard first. Also writes case/out/board.stl for the renders."""
import pathlib
import FreeCAD as App, Part, Mesh
V = App.Vector
HERE = pathlib.Path(__file__).resolve().parent
board = Part.read(str(HERE / 'board.step'))
top = Part.read(str(HERE / 'out' / 'case_top.step'))
bot = Part.read(str(HERE / 'out' / 'case_bottom.step'))
solids = []
for s in board.Solids:
    bb = s.BoundBox
    if abs(bb.YMax + 19.5) < 0.05 and abs(bb.YMin + 33.6) < 0.05:      # PJ-320D body: move to its courtyard
        s = s.copy(); s.translate(V(0, -4.1, 0))
    solids.append(s)
hits = 0
for name, case in (('top', top), ('bottom', bot)):
    for s in solids:
        if s.BoundBox.ZLength < 0.05:
            continue
        c = s.common(case)
        if not c.isNull() and c.Volume > 0.01:
            bb = s.BoundBox
            hits += 1
            print(f'  {name} hits part x {bb.XMin:.1f}..{bb.XMax:.1f} y(kicad) {-bb.YMax:.1f}..{-bb.YMin:.1f} z {bb.ZMin:.1f}..{bb.ZMax:.1f}: {c.Volume:.3f} mm3')
print('fit collisions:', hits)
print('top bbox', top.optimalBoundingBox(), '\nbottom bbox', bot.optimalBoundingBox())
Mesh.Mesh(Part.makeCompound(solids).tessellate(0.05)).write(str(HERE / 'out' / 'board.stl'))
