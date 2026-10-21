#!/usr/bin/env freecadcmd
"""Two-part case for the FM-1 MIDI dongle v6.1: CNC-milled aluminium, or 3D printed from the same geometry.

Run:  freecadcmd case/gen_case.py                 (aluminium: case/out/alu_*.step, *.stl)
      CASE=print freecadcmd case/gen_case.py      (printed:   case/out/print_*.stl, *_print.stl)

Shape: a flat slab, 22.8 x 41.0 x 12.2 mm. Top edges and corners rounded 2.0 mm, bottom edges 1.5 mm (room for the
screw heads on the flat). Lies flat on a desk either way up.

Split at the jacks' axis (z 3.31), not at the board: every port opening (jacks, USB-A, USB-C) is then half in each
half and open toward the seam, so
  - the board drops straight into the bottom half and the top half closes straight down (a rigid case can't
    flex over the jack noses; the v6 snap case split at the board face needed exactly that),
  - each half is milled in two setups (seam side, outer side) with no side operations: every port is a trough
    cut from the seam face.
Held by two M1.6 x 6 countersunk screws from the bottom, through the board's case holes H1 / H2, into tapped pins
on the top half. The screws also locate the board, so the board edge has 0.25 mm all round.
Pockets hug the parts (their 3D models + 0.3 mm air), stepped by height, so most of the case is solid. Every pocket
is shaped as the cutter leaves it: concave corners rounded to the tool radius (1.0 mm over the board, 0.5 mm
under it), the dish floors 0.5 mm.
Seam: a 0.3 x 0.3 mm reveal on each half (a 0.6 mm shadow line), so a slight mismatch doesn't show.
LED: a 1.6 mm hole over D2 for a 1.5 mm PMMA rod (light pipe), 7.1 mm long.

Frame: KiCad board coordinates (x right, y down, mm), z up from the board's bottom face (board top = 0.8).
FreeCAD gets (x, -y, z), the frame of `kicad-cli pcb export step`, so case/board.step drops straight in.
"""
import json, os, pathlib, subprocess
import FreeCAD as App
import Part
V = App.Vector

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
MODE = os.environ.get('CASE', 'alu')            # 'alu' or 'print'

# ---------------------------------------------------------------- board facts (from case/board.step)
BX, BY0, BY1, BT = 10.0, -1.97, 35.7, 0.8      # board half width, USB-end edge, jack-end edge, board top
USBA = dict(hw=6.55, y_face=-2.70, z0=1.97, z1=7.69)                    # J1 shell mouth
USBC = dict(x_face=10.72, yc=15.9, half=4.47, z0=0.84, z1=4.04)         # J2 shell (mouth to +x)
JACK_X, JACK_ZC, NOSE_D = (-5.0, 5.0), BT + 2.51, 5.0                    # J4 IN, J3 OUT: nose axis, nose OD
LED = (-8.6, 2.1, 1.89)                                                  # D2 centre and top
HOLES = {'H1': (0.0, 34.4), 'H2': (8.3, 3.0)}                            # tools/gen_pcb.py MOUNT_HOLES
# top-face labels (text, x, y, height): engraved 0.45 mm on the printed case, laser marked on the anodised one
# (case/out/alu_marking.svg)
LABELS = (('OUT', 5.0, 31.0, 2.2), ('IN', -5.0, 31.0, 2.2), ('5V', 6.6, USBC['yc'], 2.2), ('USB', 0.0, 4.0, 2.2))
FONT_DIR, FONT = '/usr/share/fonts/noto/', 'NotoSans-Bold.ttf'

# ---------------------------------------------------------------- case parameters
AIR = 0.3                               # air around every part
CL = 0.25                               # board edge to wall (the screws locate the board)
HW, Y_USB, Y_JACK = 11.4, -3.37, 37.6   # outer half width, USB end face, jack end face (noses end at 37.7)
Z_TOP, Z_BOT = 9.3, -2.89               # 1.3 mm over the tallest part (J1 7.70 + air), 1.3 under the deepest
R_V, R_TOP, R_BOT = 2.0, 2.0, 1.5       # outer rounding: vertical corners, top edges, bottom edges
SPLIT = JACK_ZC                         # parting plane 3.31
TOOL_TOP, TOOL_BOT = 1.0, 0.5           # cutter radius over / under the board
REVEAL = 0.3
PIN_R, PIN_Z0 = 1.2, BT + 0.1           # top-half screw pins: radius, end (0.1 mm over the board)
SCREW = dict(clear=1.75, csk=3.2, tap=1.25 if MODE == 'alu' else 1.35, tap_depth=4.0)
#   alu: M1.6 x 0.35 tapped 3.5 deep (drill 1.25 x 4.0); print: 1.35 pilot, the screw cuts its own thread


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))


def vert_round(s, r):
    return s.makeFillet(r, [e for e in s.Edges if abs(e.tangentAt(e.FirstParameter).z) > 0.99])


def rr_face(x0, x1, y0, y1, r):
    """rounded rectangle face at z 0"""
    s = vert_round(box(x0, x1, y0, y1, 0, 1), r)
    return [f for f in s.Faces if f.BoundBox.ZMax < 1e-6][0]


def rect_face(x0, x1, y0, y1):
    return [f for f in box(x0, x1, y0, y1, 0, 1).Faces if f.BoundBox.ZMax < 1e-6][0]


def disk_face(x, y, r):
    return Part.Face(Part.Wire(Part.makeCircle(r, V(x, -y, 0))))


# 2D regions are kept as 1 mm thick plates (z 0..1): solid booleans merge cleanly, faces don't
def plate(faces):
    sol = [f.extrude(V(0, 0, 1)) for f in faces if f is not None]
    if not sol:
        return None
    s = sol[0] if len(sol) == 1 else sol[0].fuse(sol[1:])
    return s.removeSplitter()


def base(region):
    return [f for f in region.Faces if f.BoundBox.ZMax < 1e-6]


def union(faces):
    return plate(faces)


def offset(region, d):
    """2D offset with round joins; a piece that vanishes under a negative offset is dropped"""
    out = []
    for f in base(region):
        try:
            out += f.makeOffset2D(d, join=0).Faces
        except Exception:
            pass
    return plate(out)


def machinable(req, r, inner, bosses=()):
    """smallest pocket a cutter of radius r leaves that still holds `req`: grow it by r, clip to the walls, take out
    the bosses, then an opening (shrink, grow) rounds every concave corner to r"""
    q = offset(req, r + 0.02).common(plate([inner]))
    for b in bosses:
        q = q.cut(plate([b]))
    return offset(offset(q.removeSplitter(), -r), r)


def prism(region, z0, z1):
    sol = [f.extrude(V(0, 0, z1 - z0)) for f in base(region)]
    s = sol[0] if len(sol) == 1 else sol[0].fuse(sol[1:])
    s.translate(V(0, 0, z0))
    return s


def rounded_slot_y(xc, zc, w, h, y0, y1, r):
    b = box(xc - w / 2, xc + w / 2, y0, y1, zc - h / 2, zc + h / 2)
    return b.makeFillet(r, [e for e in b.Edges if abs(e.tangentAt(e.FirstParameter).y) > 0.99])


def rounded_slot_x(x0, x1, yc, w, zc, h, r):
    b = box(x0, x1, yc - w / 2, yc + w / 2, zc - h / 2, zc + h / 2)
    return b.makeFillet(r, [e for e in b.Edges if abs(e.tangentAt(e.FirstParameter).x) > 0.99])


def floor_round(dish, axis, at, r):
    """round the floor edges of a dish cutter (its face at axis == at) to the cutter radius r"""
    edges = [e for e in dish.Edges if all(abs(getattr(v.Point, axis) - at) < 1e-4 for v in e.Vertexes)]
    return dish.makeFillet(r, edges)


# ---------------------------------------------------------------- the board's parts
def part_pieces():
    """bounding boxes of the board's 3D parts, long parts cut into 1 mm bands along y so L shapes stay tight.
    Returns (x0, x1, y0, y1, z0, z1) in board coordinates."""
    out = []
    for s in Part.read(str(HERE / 'board.step')).Solids:
        b = s.BoundBox
        if b.XLength > 19 or b.ZLength < 0.05:           # the board itself, flat pads
            continue
        if abs(b.YMax + 19.5) < 0.05 and abs(b.YMin + 33.6) < 0.05:     # the PJ-320D STEP sits 4.1 mm off
            s = s.copy(); s.translate(V(0, -4.1, 0)); b = s.BoundBox
        if b.YLength <= 3:
            out.append((b.XMin, b.XMax, -b.YMax, -b.YMin, b.ZMin, b.ZMax))
            continue
        # 1 mm bands along y from the mesh (booleans on vendor STEP models fail now and then): every triangle's
        # bounding box goes into each band it crosses, so a band is never smaller than the part in it
        pts, tris = s.tessellate(0.05)
        y0 = -b.YMax
        n = int((-b.YMin - y0) // 1.0) + 1
        bands = [None] * n
        for t in tris:
            p3 = [pts[i] for i in t]
            xs, ys, zs = [q.x for q in p3], [-q.y for q in p3], [q.z for q in p3]
            for k in range(max(0, int((min(ys) - y0) // 1.0)), min(n - 1, int((max(ys) - y0) // 1.0)) + 1):
                lo, hi = y0 + k, y0 + k + 1.0
                bb = (min(xs), max(xs), max(lo, min(ys)), min(hi, max(ys)), min(zs), max(zs))
                c = bands[k]
                bands[k] = bb if c is None else (min(c[0], bb[0]), max(c[1], bb[1]), min(c[2], bb[2]),
                                                  max(c[3], bb[3]), min(c[4], bb[4]), max(c[5], bb[5]))
        out += [c for c in bands if c]
    return out


def bottom_pads():
    """copper on the board's bottom face (SMD pads, THT rings, test pads): the case must not touch it"""
    code = ("import pcbnew,json;b=pcbnew.LoadBoard(%r);print(json.dumps([[p.GetBoundingBox().GetLeft()/1e6,"
            "p.GetBoundingBox().GetTop()/1e6,p.GetBoundingBox().GetRight()/1e6,p.GetBoundingBox().GetBottom()/1e6]"
            " for f in b.GetFootprints() for p in f.Pads() if p.IsOnLayer(pcbnew.B_Cu) and"
            " p.GetAttribute()!=pcbnew.PAD_ATTRIB_NPTH]))") % str(HERE.parent / 'fm1-midi-dongle.kicad_pcb')
    res = subprocess.run(['python3', '-c', code], capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': ''})
    return json.loads(res.stdout.strip().splitlines()[-1])


def stepped_pocket(boxes, inner, r, z_seam, up, bosses=()):
    """pocket from the seam face (z_seam) into the half: each part box needs room to its own height. Levels are
    merged within 0.2 mm; each step is a machinable profile, nested (deeper steps are smaller)."""
    lv = sorted({round(b[5 if up else 4] + (AIR if up else -AIR), 2) for b in boxes}, reverse=not up)
    levels = []
    for z in lv:                                        # merge levels closer than 0.2 (keep the farther one)
        if levels and abs(z - levels[-1]) < 0.2:
            levels[-1] = z
        else:
            levels.append(z)
    cav, prev = None, z_seam
    for z in levels:
        need = [b for b in boxes if (b[5] + AIR > prev + 1e-6 if up else b[4] - AIR < prev - 1e-6)]
        if not need:
            break
        req = union([rect_face(b[0] - AIR, b[1] + AIR, b[2] - AIR, b[3] + AIR) for b in need])
        prof = machinable(req, r, inner, bosses)
        p = prism(prof, prev, z) if up else prism(prof, z, prev)
        cav = p if cav is None else cav.fuse(p)
        prev = z
    return cav


def text(s, x, y, z, size, depth):
    chars = Part.makeWireString(s, FONT_DIR, FONT, size, 0.15)
    faces = [Part.makeFace(w, 'Part::FaceMakerBullseye') for w in chars if w]
    comp = Part.makeCompound(faces)
    bb = comp.BoundBox
    comp.translate(V(x - (bb.XMin + bb.XMax) / 2, -y - (bb.YMin + bb.YMax) / 2, z))
    return comp.extrude(V(0, 0, -depth))


def marking_svg(path):
    """laser-marking artwork for the anodised top face: outline + labels, 1:1 in mm, seen from above"""
    w, h = 2 * HW, Y_JACK - Y_USB
    rows = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="{-HW} {Y_USB} {w} {h}">',
            f'<rect x="{-HW}" y="{Y_USB}" width="{w}" height="{h}" rx="{R_V}" fill="none" stroke="#999" '
            'stroke-width="0.05"/>',
            f'<circle cx="{LED[0]}" cy="{LED[1]}" r="0.8" fill="none" stroke="#999" stroke-width="0.05"/>']
    for t, x, y, size in LABELS:
        rows.append(f'<text x="{x}" y="{y}" font-family="Noto Sans" font-weight="bold" font-size="{size * 1.36:.2f}" '
                    f'text-anchor="middle" dominant-baseline="central">{t}</text>')
    pathlib.Path(path).write_text('\n'.join(rows + ['</svg>']) + '\n')


def chk(name, s):
    print(f'  [{name}] valid {s.isValid()} solids {len(s.Solids)} vol {s.Volume:.1f}')
    return s


def main():
    # ---- outer: vertical corners, then top edges, then bottom edges
    outer = vert_round(box(-HW, HW, Y_USB, Y_JACK, Z_BOT, Z_TOP), R_V)
    outer = outer.makeFillet(R_TOP, [e for e in outer.Edges if all(abs(v.Point.z - Z_TOP) < 1e-6 for v in e.Vertexes)])
    outer = chk('outer', outer.makeFillet(R_BOT, [e for e in outer.Edges
                                                 if all(abs(v.Point.z - Z_BOT) < 1e-6 for v in e.Vertexes)]))
    inner = rr_face(-BX - CL, BX + CL, BY0 - CL, BY1 + CL, 1.0 + CL)        # board slot, board corners r 0.75..1.0
    pieces = part_pieces()
    tops = [p for p in pieces if p[5] + AIR > SPLIT]
    bots = [p for p in pieces if p[4] < -0.02]
    print(f'  {len(pieces)} part pieces: {len(tops)} reach over the seam, {len(bots)} under the board')

    # ---- ports, cut through the whole slab before the split (both halves get their half)
    shell = outer
    zc = (USBA['z0'] + USBA['z1']) / 2
    shell = shell.cut(rounded_slot_y(0, zc, 2 * (USBA['hw'] + 0.25), USBA['z1'] - USBA['z0'] + 0.5,
                                     Y_USB - 1, BY0 + 0.5, 0.6))
    dish = rounded_slot_y(0, zc, 15.6, 7.8, Y_USB - 1, USBA['y_face'] - 0.02, 1.6)
    shell = shell.cut(floor_round(dish, 'y', -(USBA['y_face'] - 0.02), 0.5))     # FreeCAD y = -board y
    zc2 = (USBC['z0'] + USBC['z1']) / 2
    shell = shell.cut(rounded_slot_x(BX - 1.5, HW + 1, USBC['yc'], 2 * USBC['half'] + 0.4, zc2,
                                     USBC['z1'] - USBC['z0'] + 0.4, 1.4))
    dish = rounded_slot_x(USBC['x_face'], HW + 1, USBC['yc'], 12.8, zc2, 6.7, 2.6)
    shell = shell.cut(floor_round(dish, 'x', USBC['x_face'], 0.5))
    for x in JACK_X:
        shell = shell.cut(Part.makeCylinder(NOSE_D / 2 + 0.2, 4.0, V(x, -(BY1 - 0.3), JACK_ZC), V(0, -1, 0)))
        shell = shell.cut(Part.makeCone(NOSE_D / 2 + 0.2, NOSE_D / 2 + 0.8, 0.6, V(x, -(Y_JACK - 0.6), JACK_ZC),
                                        V(0, -1, 0)))
    lx, ly, _ = LED
    shell = chk('ports', shell.cut(Part.makeCylinder(0.8, 20, V(lx, -ly, SPLIT - 1))))

    # ---- reveal at the seam
    ring = vert_round(box(-HW - 1, HW + 1, Y_USB - 1, Y_JACK + 1, SPLIT - REVEAL, SPLIT + REVEAL), R_V + 1)
    ring = ring.cut(vert_round(box(-HW + REVEAL, HW - REVEAL, Y_USB + REVEAL, Y_JACK - REVEAL,
                                   SPLIT - 1, SPLIT + 1), R_V - REVEAL))
    shell = shell.cut(ring)

    big = 200
    top = shell.common(box(-big, big, -big, big, SPLIT, big))
    bot = shell.common(box(-big, big, -big, big, -big, SPLIT))

    # ---- top half: stepped pocket over the parts, screw pins down to 0.1 mm over the board
    pins = [disk_face(x, y, PIN_R) for x, y in HOLES.values()]
    cav = stepped_pocket(tops, inner, TOOL_TOP, SPLIT, up=True, bosses=pins)
    top = chk('top', top.cut(cav))
    for x, y in HOLES.values():
        top = top.fuse(Part.makeCylinder(PIN_R, SPLIT - PIN_Z0 + 0.01, V(x, -y, PIN_Z0)))
        top = top.cut(Part.makeCylinder(SCREW['tap'] / 2, SCREW['tap_depth'], V(x, -y, PIN_Z0 - 0.01)))
        top = top.cut(Part.makeCone(SCREW['tap'] / 2 + 0.2, SCREW['tap'] / 2, 0.2, V(x, -y, PIN_Z0 - 0.01)))
    if MODE == 'print':
        for t, x, y, size in LABELS:
            top = top.cut(text(t, x, y, Z_TOP + 0.01, size, 0.45))
    else:
        marking_svg(OUT / 'alu_marking.svg')
    top = chk('top+pins', top.removeSplitter())

    # ---- bottom half: board slot, stepped pocket under the parts, reliefs over the bottom copper, screw holes
    bot = bot.cut(prism(plate([inner]), 0.0, SPLIT + 0.01))
    cav = stepped_pocket(bots, inner, TOOL_BOT, 0.0, up=False)
    bot = bot.cut(cav)
    pads = union([rect_face(x0 - 0.25, x1 + 0.25, y0 - 0.25, y1 + 0.25) for x0, y0, x1, y1 in bottom_pads()])
    bot = bot.cut(prism(machinable(pads, TOOL_BOT, inner), -0.3, 0.01))
    for x, y in HOLES.values():
        bot = bot.cut(Part.makeCylinder(SCREW['clear'] / 2, 10, V(x, -y, Z_BOT - 1)))
        bot = bot.cut(Part.makeCone(SCREW['csk'] / 2 + 0.01, SCREW['clear'] / 2, (SCREW['csk'] - SCREW['clear']) / 2,
                                    V(x, -y, Z_BOT - 0.01)))
    bot = chk('bottom', bot.removeSplitter())

    tag = MODE
    for name, shp, flip in ((f'{tag}_top', top, True), (f'{tag}_bottom', bot, False)):
        if len(shp.Solids) > 1:
            print(f'  {name}: dropped {len(shp.Solids) - 1} specks')
            shp = max(shp.Solids, key=lambda q: q.Volume)
        print(name, 'valid', shp.isValid(), 'vol', round(shp.Volume, 1), 'mm3, bbox', shp.BoundBox)
        shp.exportStep(str(OUT / f'{name}.step'))
        import Mesh, MeshPart
        Mesh.Mesh(shp.tessellate(0.02)).write(str(OUT / f'{name}.stl'))
        if MODE == 'print':                     # print orientation: the flat outer face on the bed
            pr = shp.copy()
            if flip:
                pr.rotate(V(0, 0, 0), V(0, 1, 0), 180)
            bb = pr.BoundBox
            pr.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
            MeshPart.meshFromShape(Shape=pr, LinearDeflection=0.01, AngularDeflection=0.1, Relative=False).write(
                str(OUT / f'{name}_print.stl'))
    top, bot = [Part.read(str(OUT / f'{tag}_{n}.step')) for n in ('top', 'bottom')]
    Part.makeCompound([top, bot]).exportStep(str(OUT / f'{tag}_assembly.step'))


import traceback
try:
    main()
except Exception:
    traceback.print_exc()
    raise
