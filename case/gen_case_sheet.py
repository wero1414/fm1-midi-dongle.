#!/usr/bin/env freecadcmd
"""Sheet-metal case for the FM-1 MIDI dongle v6.1: two bent 0.8 mm 5052 aluminium parts.

Run:  freecadcmd case/gen_case_sheet.py      (case/out/sheet_*.step, *.stl)

  - base:  bottom + both long sides (one U, bent along y). The right side has the USB-C opening.
  - cover: top + both ends (one U, bent along x), dropped in between the base's sides. The ends carry the jack holes
    and the USB-A opening; the top the LED hole. Each end has two tabs bent 90 deg inward against the base's sides,
    with an M2 clinch nut (PEM S-M2-0 class); 4 x M2 x 4 low-head screws through the sides hold the cover.
  - board: on the base floor with an M1.6 nut + washer as a 1.6 mm spacer under H2, M1.6 x 6 screw from below, nut on
    top. H1 sits between the jack pads and has no room for a nut; the jack noses in their holes hold that end.
Bent parts can't hold a connector in a half hole (bending is +-0.3 mm), so every wall stands 0.1 mm clear of the
connector faces: the jacks, USB-A and USB-C sit 0.9 mm behind the outside face. Both parts and the board go together
straight down.
Bends: inside radius = sheet thickness (0.8), outside 1.6.

Frame: KiCad board coordinates (x right, y down, mm), z up from the board's bottom face; FreeCAD gets (x, -y, z).
"""
import pathlib
import FreeCAD as App
import Part
V = App.Vector

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- board facts (from case/board.step)
USBA = dict(hw=6.55, y_face=-2.70, z0=1.97, z1=7.69)
USBC = dict(x_face=10.72, yc=15.9, half=4.47, z0=0.84, z1=4.04)
JACK_X, JACK_ZC, JACK_FACE = (-5.0, 5.0), 3.31, 37.7
LED = (-8.6, 2.1, 1.89)
H2 = (8.3, 3.0)

# ---------------------------------------------------------------- sheet and box
T = 0.8                                  # 5052-H32
RI, RO = T, 2 * T                        # bend radii inside / outside
GAP = 0.1                                # wall to connector face
XI = USBC['x_face'] + GAP                # inside half width 10.82
YI0, YI1 = USBA['y_face'] - GAP, JACK_FACE + GAP     # inside ends -2.80 / 37.80
ZI0, ZI1 = -1.59, 8.1                    # inside floor (U3 -1.29 - 0.3), inside ceiling (J1 7.70 + 0.4: bend radius)
FIT = 0.1                                # cover to base sides
TAB_L, TAB_Z = 4.4, (1.0, 7.2)           # cover tabs: length along y, height span (above the board)
NUT_R, NUT_H = 2.1, 1.5                  # M2 clinch nut body inside the tab (S-M2-0 class: approx. 4.2 x 1.5)
SCREW_Z = 4.1


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))


def round_edges(s, r, test):
    return s.makeFillet(r, [e for e in s.Edges if test(e)])


def along(axis):
    return lambda e: abs(getattr(e.tangentAt(e.FirstParameter), axis)) > 0.99


def at(axis, val):
    return lambda e: all(abs(getattr(v.Point, axis) - val) < 1e-6 for v in e.Vertexes)


def chk(name, s):
    print(f'  [{name}] valid {s.isValid()} solids {len(s.Solids)} vol {s.Volume:.1f}')
    return s


def main():
    xo, y0o, y1o, zbo, zto = XI + T, YI0 - T, YI1 + T, ZI0 - T, ZI1 + T
    # ---- base: U along y (bottom + sides), bends on the two long bottom edges
    outer = box(-xo, xo, y0o, y1o, zbo, zto)
    outer = round_edges(outer, RO, lambda e: along('y')(e) and at('z', zbo)(e))
    inner = box(-XI, XI, y0o - 1, y1o + 1, ZI0, zto + 1)
    inner = round_edges(inner, RI, lambda e: along('y')(e) and at('z', ZI0)(e))
    base = outer.cut(inner)
    zc = (USBC['z0'] + USBC['z1']) / 2
    win = box(XI - 1, xo + 1, USBC['yc'] - USBC['half'] - 0.3, USBC['yc'] + USBC['half'] + 0.3,
              zc - 1.6 - 0.3, zc + 1.6 + 0.3)
    base = base.cut(round_edges(win, 1.6 + 0.3 - 0.01, along('x')))
    base = base.cut(Part.makeCylinder(0.9, 5, V(H2[0], -H2[1], zbo - 1)))           # M1.6 board screw
    for sx in (-1, 1):                                                                # cover screws
        for yc in (YI0 + TAB_L / 2, YI1 - TAB_L / 2):
            base = base.cut(Part.makeCylinder(1.1, 3, V(sx * (XI - 0.5), -yc, SCREW_Z), V(sx, 0, 0)))
    base = chk('base', base)

    # ---- cover: U along x (top + ends) between the base's sides, bends on the two short top edges
    xc = XI - FIT
    outer = box(-xc, xc, y0o, y1o, ZI0, zto)
    outer = round_edges(outer, RO, lambda e: along('x')(e) and at('z', zto)(e))
    inner = box(-xc - 1, xc + 1, YI0, YI1, ZI0 - 1, ZI1)
    inner = round_edges(inner, RI, lambda e: along('x')(e) and at('z', ZI1)(e))
    cover = outer.cut(inner)
    for x0, x1 in ((xc - 1.0, xc + 1.5), (-xc - 1.5, -xc + 1.0)):    # end walls' bottom corners clear the
        cover = cover.cut(box(x0, x1, y0o - 1, y1o + 1, ZI0 - 1, ZI0 + 1.0))   # base's bend radius (1 x 1 notch)
    # tabs: bent in from each end's vertical edges, against the base's sides, clinch nut on the inside
    for sx in (-1, 1):
        for ya, yb in ((YI0, YI0 + TAB_L), (YI1 - TAB_L, YI1)):
            xa, xb = (xc - T, xc) if sx > 0 else (-xc, -xc + T)
            tab = box(xa, xb, ya - 0.01 if ya == YI0 else ya, yb + 0.01 if yb == YI1 else yb, *TAB_Z)
            yc = (ya + yb) / 2
            nut = Part.makeCylinder(NUT_R, NUT_H, V(sx * (xc - T), -yc, SCREW_Z), V(-sx, 0, 0))
            cover = cover.fuse(tab).fuse(nut)
            cover = cover.cut(Part.makeCylinder(0.8, 10, V(sx * (xc + 1), -yc, SCREW_Z), V(-sx, 0, 0)))
    # openings: jack holes (end), USB-A (end), LED (top)
    for x in JACK_X:
        cover = cover.cut(Part.makeCylinder(2.7, 3, V(x, -(YI1 - 1), JACK_ZC), V(0, -1, 0)))
    zc = (USBA['z0'] + USBA['z1']) / 2
    mouth = box(-USBA['hw'] - 0.3, USBA['hw'] + 0.3, y0o - 1, YI0 + 1, zc - (USBA['z1'] - USBA['z0']) / 2 - 0.3,
                zc + (USBA['z1'] - USBA['z0']) / 2 + 0.3)
    cover = cover.cut(round_edges(mouth, 0.8, along('y')))
    cover = cover.cut(Part.makeCylinder(0.8, 5, V(LED[0], -LED[1], ZI1 - 1)))
    cover = chk('cover', cover.removeSplitter())

    # ---- board hardware at H2 (for the fit check and renders): nut + washer spacer under, nut on top
    hw = Part.makeCylinder(1.85, 1.6, V(H2[0], -H2[1], ZI0)).fuse(Part.makeCylinder(1.85, 1.3, V(H2[0], -H2[1], 0.8)))
    hw = hw.cut(Part.makeCylinder(0.8, 10, V(H2[0], -H2[1], -3)))

    for name, shp in (('sheet_bottom', base), ('sheet_top', cover), ('sheet_hardware', hw)):
        print(name, 'valid', shp.isValid(), 'vol', round(shp.Volume, 1))
        shp.exportStep(str(OUT / f'{name}.step'))
        import Mesh
        Mesh.Mesh(shp.tessellate(0.02)).write(str(OUT / f'{name}.stl'))
    Part.makeCompound([base, cover]).exportStep(str(OUT / 'sheet_assembly.step'))
    print(f'outside: {2 * xo:.2f} x {y1o - y0o:.2f} x {zto - zbo:.2f} mm, '
          f'{(base.Volume + cover.Volume) * 2.68e-3:.1f} g (5052)')


import traceback
try:
    main()
except Exception:
    traceback.print_exc()
    raise
