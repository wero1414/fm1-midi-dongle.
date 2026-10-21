#!/usr/bin/env freecadcmd
"""Fit and assembly check of the case (CASE=alu default, CASE=print, or CASE=sheet) against case/board.step:
  1. every 3D part of the board vs both halves (closed), and the halves vs each other
  2. assembly: the board drops straight into the bottom half, the top half closes straight down (swept 0.25 mm steps)
  3. the M1.6 x 6 screws: through the board's holes, clear of every part
The jack STEP sits 4.1 mm off its footprint (the WRL KiCad renders is right), so the jacks are moved to the
footprint's courtyard first. Also writes case/out/board.stl for the renders."""
import os, pathlib
import FreeCAD as App, Part, Mesh
V = App.Vector
HERE = pathlib.Path(__file__).resolve().parent
MODE = os.environ.get('CASE', 'alu')
HOLES = {'H1': (0.0, 34.4), 'H2': (8.3, 3.0)}
board = Part.read(str(HERE / 'board.step'))
top = Part.read(str(HERE / 'out' / f'{MODE}_top.step'))
bot = Part.read(str(HERE / 'out' / f'{MODE}_bottom.step'))
solids = []
for s in board.Solids:
    bb = s.BoundBox
    if abs(bb.YMax + 19.5) < 0.05 and abs(bb.YMin + 33.6) < 0.05:      # PJ-320D body: move to its courtyard
        s = s.copy(); s.translate(V(0, -4.1, 0))
    solids.append(s)
parts = [s for s in solids if s.BoundBox.ZLength >= 0.05]


def hits(case, moved=V(0, 0, 0), against=parts):
    c = case.copy(); c.translate(moved)
    out = []
    for s in against:
        if not s.BoundBox.intersect(c.BoundBox):
            continue
        q = s.common(c)
        if not q.isNull() and q.Volume > 0.001:
            bb = s.BoundBox
            out.append(f'x {bb.XMin:.1f}..{bb.XMax:.1f} y {-bb.YMax:.1f}..{-bb.YMin:.1f} z {bb.ZMin:.1f}..{bb.ZMax:.1f}'
                       f' ({q.Volume:.3f} mm3)')
    return out


n = 0
for name, case in (('top', top), ('bottom', bot)):
    for h in hits(case):
        n += 1; print(f'  closed: {name} hits part {h}')
q = top.common(bot)
if q.Volume > 0.001:
    n += 1; print(f'  halves overlap {q.Volume:.3f} mm3')
print('fit collisions:', n)

# assembly sweeps: top half from above, board out of the bottom half upward (= dropping it in)
m = 0
for i in range(1, 41):
    d = 0.25 * i
    for h in hits(top, V(0, 0, d)):
        m += 1; print(f'  top half {d:.2f} mm above its seat hits {h}')
    for h in hits(bot, V(0, 0, -d)):
        m += 1; print(f'  board {d:.2f} mm above its seat: bottom half hits {h}')
print('assembly collisions (straight down, 0.25..10 mm):', m)

if MODE == 'sheet':                     # board hardware at H2 (nut + washer spacer, nut on top) vs parts and case
    hw = Part.read(str(HERE / 'out' / 'sheet_hardware.step'))
    k = sum(1 for h in hits(hw, against=[s for s in parts if s.BoundBox.XLength < 19]) if print('  H2 hardware hits', h) or True)
    for name, case in (('top', top), ('bottom', bot)):
        q = hw.common(case)
        if q.Volume > 0.001:
            k += 1; print(f'  H2 hardware hits {name}: {q.Volume:.3f}')
    print('hardware collisions:', k)
    print('top bbox', top.optimalBoundingBox(), '\nbottom bbox', bot.optimalBoundingBox())
else:
    # screws: M1.6 x 6 countersunk, head flush with the bottom face (z -2.89), tip at z 3.11
    k = 0
    for ref, (x, y) in HOLES.items():
        screw = Part.makeCylinder(0.8, 6.0, V(x, -y, -2.89))
        for s in solids:
            q = s.common(screw)
            if not q.isNull() and q.Volume > 0.001:
                k += 1; bb = s.BoundBox
                print(f'  screw {ref} hits x {bb.XMin:.1f}..{bb.XMax:.1f} z {bb.ZMin:.2f}..{bb.ZMax:.2f}: {q.Volume:.3f}')
        thread = top.common(Part.makeCylinder(0.8, 6.0, V(x, -y, -2.89)))
        print(f'  screw {ref}: thread engagement in the top pin ~{thread.BoundBox.ZLength if not thread.isNull() else 0:.2f} mm')
    print('screw collisions:', k)
    print('top bbox', top.optimalBoundingBox(), '\nbottom bbox', bot.optimalBoundingBox())
Mesh.Mesh(Part.makeCompound(solids).tessellate(0.05)).write(str(HERE / 'out' / 'board.stl'))
