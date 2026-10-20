#!/usr/bin/env freecadcmd
"""Printable two-part case for the FM-1 MIDI dongle v6, built with FreeCAD's Part workbench (OpenCascade).

Run:  freecadcmd case/gen_case.py      (writes case/out/*.step, *.stl)

Shape: a flat slab, 22.8 x 41.0 x 12.2 mm, every edge rounded 2.0 mm. Top and bottom are flat, so it lies flat on a
desk either way up. Its height is set by the tallest parts: the USB-A receptacle on top (7.7 mm over the board's
bottom) and the SY6280 on the bottom (1.3 mm under it), each with 0.3 mm of air.
Halves: split at the board's top face (z 0.8). The bottom half carries the board on a ledge, with two pins through
the board's side notches. The top half clamps the board's edge with a rim and drops a lip into the bottom half's
wall, with four snap bumps.
Ports: shallow dishes around both USB ports so a plug's overmold reaches the receptacle face; jack noses flush with
the end face, through chamfered holes. LED light pipe; engraved OUT / IN / 5V / USB.

Frame: KiCad board coordinates (x right, y down, mm), z up from the board's bottom face (board top = 0.8).
FreeCAD gets (x, -y, z), the same frame as `kicad-cli pcb export step`, so the exported board drops straight in.
The part positions below were measured on that export (case/board.step).
"""
import pathlib
import FreeCAD as App
import Part
V = App.Vector

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
FONT_DIR, FONT = '/usr/share/fonts/noto/', 'NotoSans-Bold.ttf'

# ---------------------------------------------------------------- board facts (from case/board.step)
BX, BY0, BY1 = 10.0, -1.97, 35.7        # board half width, top edge (USB end), bottom edge (jack end)
BT = 0.8                                # board top
USBA = dict(hw=6.55, y_face=-2.70, z0=1.97, z1=7.69)                    # J1 shell mouth (top face)
USBC = dict(x_face=10.72, yc=15.9, half=4.47, z0=0.84, z1=4.04)         # J2 shell (mouth to +x)
JACK_X, JACK_ZC, NOSE_D = (-5.0, 5.0), BT + 2.51, 5.0                    # J4 IN, J3 OUT; nose axis, nose OD
JACK_BODY = (23.6, 35.7)                # body y span (courtyard), nose 35.7 .. 37.7
LED = (-8.6, 2.1, 1.89)                 # D2 centre and top
NOTCH_Y = 22.2                          # board side notches (r 0.6 + 0.3 fillets), both edges
TOP_MAX, BOT_MIN = 7.70, -1.29          # tallest part over the board (J1), deepest under it (U3)

# ---------------------------------------------------------------- case parameters
AIR = 0.3
W_SIDE, W_TOP, W_BOT = 1.2, 1.3, 1.3
CL = 0.2                                # board to wall
HW = BX + CL + W_SIDE                   # outer half width 11.4
Y_USB, Y_JACK = BY0 - CL - W_SIDE, 37.6 # outer end faces (jack noses end at 37.7: flush within 0.1)
W_END_JACK = 1.7
Z_IN_TOP, Z_IN_BOT = TOP_MAX + AIR, BOT_MIN - AIR        # 8.0 / -1.59
Z_TOP, Z_BOT = Z_IN_TOP + W_TOP, Z_IN_BOT - W_BOT        # 9.3 / -2.89
R_OUT, R_IN = 2.0, 0.8                  # edge rounding outside / inside
SPLIT = BT                              # parting plane


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))


def rounded_box(x0, x1, y0, y1, z0, z1, r):
    b = box(x0, x1, y0, y1, z0, z1)
    return b.makeFillet(r, b.Edges)


def rounded_slot_y(xc, zc, w, h, y0, y1, r):
    """rounded box whose axis is along y (end-face openings): w along x, h along z"""
    b = box(xc - w / 2, xc + w / 2, y0, y1, zc - h / 2, zc + h / 2)
    return b.makeFillet(r, [e for e in b.Edges if abs(e.tangentAt(0).y) > 0.99])


def rounded_slot_x(x0, x1, yc, w, zc, h, r):
    """rounded box whose axis is along x (side openings): w along y, h along z"""
    b = box(x0, x1, yc - w / 2, yc + w / 2, zc - h / 2, zc + h / 2)
    return b.makeFillet(r, [e for e in b.Edges if abs(e.tangentAt(0).x) > 0.99])


def text(s, x, y, z, size, depth):
    chars = Part.makeWireString(s, FONT_DIR, FONT, size, 0.15)
    faces = [Part.makeFace(w, 'Part::FaceMakerBullseye') for w in chars if w]
    comp = Part.makeCompound(faces)
    bb = comp.BoundBox
    comp.translate(V(x - (bb.XMin + bb.XMax) / 2, -y - (bb.YMin + bb.YMax) / 2, z))
    return comp.extrude(V(0, 0, -depth))


def board_ring(off_in, off_out, z0, z1):
    """ring between the board outline offset by off_in and off_out (rounded rectangle approximation)"""
    def rr(off):
        s = box(-BX - off, BX + off, BY0 - off, BY1 + off, z0, z1)
        return s.makeFillet(max(0.3, 1.0 + off), [e for e in s.Edges if abs(e.tangentAt(0).z) > 0.99])
    return rr(off_out).cut(rr(off_in))


def part_boxes(top):
    """bounding boxes (grown by AIR) of the board's parts above (top=True) or below the board"""
    out = []
    for s in Part.read(str(HERE / 'board.step')).Solids:
        b = s.BoundBox
        if b.XLength > 19 or b.ZLength < 0.05:           # the board itself, flat pads
            continue
        if abs(b.YMax + 19.5) < 0.05 and abs(b.YMin + 33.6) < 0.05:     # PJ-320D STEP sits 4.1 mm off
            b = App.BoundBox(b.XMin, b.YMin - 4.1, b.ZMin, b.XMax, b.YMax - 4.1, b.ZMax)
        if (top and b.ZMax > BT + 0.05) or (not top and b.ZMin < -0.05):
            out.append(Part.makeBox(b.XLength + 2 * AIR, b.YLength + 2 * AIR, 30,
                                    V(b.XMin - AIR, b.YMin - AIR, BT if top else -30)))
    return out


def chk(name, shp):
    print(f'  [{name}] valid {shp.isValid()} solids {len(shp.Solids)} vol {shp.Volume:.1f}')
    return shp


def main():
    outer = rounded_box(-HW, HW, Y_USB, Y_JACK, Z_BOT, Z_TOP, R_OUT)
    inner = rounded_box(-HW + W_SIDE, HW - W_SIDE, Y_USB + W_SIDE, Y_JACK - W_END_JACK, Z_IN_BOT, Z_IN_TOP, R_IN)
    shell = chk('shell', outer.cut(inner))

    # ---- USB-A (J1) mouth in the USB end, and a dish so a plug's overmold reaches the receptacle face
    zc = (USBA['z0'] + USBA['z1']) / 2
    shell = shell.cut(rounded_slot_y(0, zc, 2 * (USBA['hw'] + 0.25), USBA['z1'] - USBA['z0'] + 0.5,
                                     Y_USB - 1, BY0 + 0.5, 0.6))
    shell = shell.cut(rounded_slot_y(0, zc, 15.6, 7.8, Y_USB - 1, USBA['y_face'] - 0.02, 1.6))

    # ---- USB-C (J2) window in the right wall, and a dish around it whose floor is flush with the receptacle face
    # (the wall behind the dish is 0.5 mm)
    zc2 = (USBC['z0'] + USBC['z1']) / 2
    shell = shell.cut(rounded_slot_x(BX - 1.5, HW + 1, USBC['yc'], 2 * USBC['half'] + 0.4, zc2,
                                     USBC['z1'] - USBC['z0'] + 0.4, 1.4))
    shell = shell.cut(rounded_slot_x(USBC['x_face'], HW + 1, USBC['yc'], 12.8, zc2, 6.7, 2.6))

    # ---- jack noses: flush holes with a soft chamfer for the plug
    for x in JACK_X:
        cyl = Part.makeCylinder(NOSE_D / 2 + 0.2, 4.0, V(x, -JACK_BODY[1] + 0.3, JACK_ZC), V(0, -1, 0))
        cone = Part.makeCone(NOSE_D / 2 + 0.2, NOSE_D / 2 + 0.8, 0.6, V(x, -(Y_JACK - 0.6), JACK_ZC), V(0, -1, 0))
        shell = shell.cut(cyl).cut(cone)

    # ---- inside features, fused into the whole shell before the split (the split halves fuse badly):
    # ledge under the board's edge (bottom half), rim over it (top half), LED light pipe (top half).
    # Both stop short of every part (its bounding box + 0.3 mm).
    ledge = board_ring(-0.8, CL + 0.05, Z_BOT, 0.0).common(outer)   # overlaps the floor: no coincident faces
    for k in part_boxes(top=False):
        ledge = ledge.cut(k)
    rim = board_ring(-0.35, CL + 0.05, SPLIT, Z_TOP).common(outer)  # overlaps the ceiling: no coincident faces
    rim_out = part_boxes(top=True)
    rim_out.append(box(BX - 2.5, BX + 2, USBC['yc'] - 6.0, USBC['yc'] + 6.0, 0, 20))      # USB-C dish
    for sx in (-1, 1):
        rim_out.append(Part.makeCylinder(0.75, 20, V(sx * BX, -NOTCH_Y, 0)))
    for k in rim_out:
        rim = rim.cut(k)
    lx, ly, lz = LED
    tube = Part.makeCylinder(1.3, 20, V(lx, -ly, lz + 0.3)).common(outer)
    shell = chk('shell+inside', shell.multiFuse([ledge, rim, tube]).removeSplitter())
    shell = shell.cut(Part.makeCylinder(0.8, 20, V(lx, -ly, lz + 0.3)))

    # ---- pry notch on the seam (left side near the jack end): a fingernail or a flat screwdriver opens the case
    shell = shell.cut(rounded_slot_x(-HW - 1, -HW + 0.7, 31.0, 4.0, SPLIT, 1.2, 0.5))

    # ---- split
    big = 200
    top = chk('top split', shell.common(Part.makeBox(big, big, big, V(-big / 2, -big / 2 - 20, SPLIT))))
    bot = chk('bot split', shell.common(Part.makeBox(big, big, big, V(-big / 2, -big / 2 - 20, SPLIT - big))))

    # ---- lip: inner 0.55 mm of the wall from z -0.2 to the split belongs to the top half; none along the USB-C
    # dish and at the notch pins
    lip = board_ring(CL + 0.02, CL + 0.55, -0.2, SPLIT + 0.01)
    clear = board_ring(CL - 0.05, CL + 0.65, -0.3, SPLIT)
    no_lip = [box(BX - 1, BX + 3, USBC['yc'] - 7.0, USBC['yc'] + 7.0, -1, SPLIT + 0.1)]
    for sx in (-1, 1):
        no_lip.append(Part.makeCylinder(1.0, 3, V(sx * BX, -NOTCH_Y, -1)))
    for n in no_lip:
        lip = lip.cut(n); clear = clear.cut(n)
    # snap bumps on the lip's outer face (4x, 0.25 mm proud), dimples in the bottom half's skin
    caps, dimples = [], []
    ring_b = board_ring(CL + 0.5, CL + 0.85, -0.2, SPLIT)
    for sx in (-1, 1):
        for y in (3.0, 29.0):
            c = V(sx * (BX + CL + 0.55 + 0.25 - 0.8), -y, 0.3)
            caps.append(Part.makeSphere(0.8, c).common(ring_b))
            dimples.append(Part.makeSphere(0.88, c))
    lip = lip.multiFuse(caps).removeSplitter()
    top = chk('top+lip', top.fuse(lip))
    bot = bot.cut(clear)
    for d in dimples:
        bot = bot.cut(d)

    # ---- notch pins (bottom half) and their sockets (top half)
    for sx in (-1, 1):
        pin = Part.makeCylinder(0.5, 1.6 + 1.0, V(sx * BX, -NOTCH_Y, -1.0))
        pin = pin.fuse(Part.makeCone(0.5, 0.3, 0.3, V(sx * BX, -NOTCH_Y, 1.6)))
        bot = bot.fuse(pin)
        top = top.cut(Part.makeCylinder(0.7, 1.4, V(sx * BX, -NOTCH_Y, SPLIT - 0.01)))

    # ---- engraving on the top face (0.45 mm): OUT / IN over the jacks, 5V beside the USB-C, USB at the USB end
    for s, x, y, h in (('OUT', 5.0, 31.0, 2.2), ('IN', -5.0, 31.0, 2.2), ('5V', 6.6, USBC['yc'], 2.2),
                       ('USB', 0.0, 4.0, 2.2)):
        top = top.cut(text(s, x, y, Z_TOP + 0.01, h, 0.45))

    for name, shp, flip in (('case_top', top, True), ('case_bottom', bot, False)):
        shp = shp.removeSplitter()
        specks = [x for x in shp.Solids if x.Volume < 0.1]       # boolean leftovers at rim corners
        if specks:
            shp = max(shp.Solids, key=lambda x: x.Volume)
            print(f'  {name}: dropped {len(specks)} specks < 0.1 mm3')
        print(name, 'valid', shp.isValid(), 'solids', len(shp.Solids), 'vol', round(shp.Volume, 1), 'bbox', shp.BoundBox)
        shp.exportStep(str(OUT / f'{name}.step'))
        import Mesh, MeshPart
        Mesh.Mesh(shp.tessellate(0.02)).write(str(OUT / f'{name}.stl'))
        # print orientation: the flat outer face on the bed (top half upside down)
        pr = shp.copy()
        if flip:
            pr.rotate(V(0, 0, 0), V(0, 1, 0), 180)
        bb = pr.optimalBoundingBox()
        pr.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
        MeshPart.meshFromShape(Shape=pr, LinearDeflection=0.01, AngularDeflection=0.1, Relative=False).write(
            str(OUT / f'{name}_print.stl'))
    top, bot = [max(x.Solids, key=lambda q: q.Volume) for x in (top, bot)]
    Part.makeCompound([top, bot]).exportStep(str(OUT / 'case_assembly.step'))
    return top, bot


import traceback
try:
    main()
except Exception:
    traceback.print_exc()
    raise
