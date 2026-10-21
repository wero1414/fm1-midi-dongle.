#!/usr/bin/env python3
"""Regenerate the silkscreen of the routed board (run after tools/route.py; safe to re-run).

The library silk (EasyEDA and KiCad styles mixed, lines off the edge and on the plug body, no designators) is
replaced by one consistent set, sized for JLCPCB's standard legend (line >= 0.153 mm, text >= 1.0 mm high,
>= 0.15 mm from pads):
  - part outlines from the body (EasyEDA courtyard = body, KiCad F.Fab), clipped 0.2 mm from mask openings and
    holes and 0.3 mm inside the board edge; none on J1 (USB-A) or on R/C (designator only)
  - everything on the face its part sits on (v6 has parts on both faces); back-face text is mirrored
  - pin-1 dot on the ICs, cathode bracket on D1/D2
  - every designator visible, 1.0 x 1.0 mm, placed next to its part where it hits no pad, body, edge or text;
    test pads get their signal name instead
  - board labels (name, revision, MIDI OUT / MIDI IN, 5V IN, USB HOST): each searched near a wanted spot
Old silk graphics are stripped from the file text (removing them through the SWIG API corrupts the heap).

Run: python3 tools/silk.py
"""
import math, pathlib, re
import pcbnew
from pcbnew import ToMM, FromMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

HERE = pathlib.Path(__file__).resolve().parent.parent
PCB = HERE / 'fm1-midi-dongle.kicad_pcb'
LINE = 0.15              # silk stroke
TEXT_H, TEXT_W = 1.0, 0.15   # back labels
REF_H = 0.8                   # designators: owner's choice, below JLC's 1.0 mm standard minimum
PAD_GAP = 0.2            # silk to mask opening (JLC removes silk closer than 0.15)
EDGE_GAP = 0.3           # silk to board edge
LABELS = {'TP1': '3V3', 'TP2': 'DIO', 'TP3': 'GND'}
REV = 'v6 2026-10'
EASYEDA_BODY = ('U1', 'U2', 'U3', 'U4', 'J3', 'J4')   # their courtyard is the body outline
INSIDE_OK = ('U4',)            # outline big enough to carry its designator inside when nothing fits outside
SILK_LAYERS = ('"F.SilkS"', '"B.SilkS"')


def strip_silk(text):
    """Drop every footprint graphic (fp_line/arc/circle/rect/poly) and board graphic/text on a silk layer."""
    out, i, n = [], 0, len(text)
    pat = re.compile(r'\((fp_line|fp_arc|fp_circle|fp_rect|fp_poly|gr_line|gr_arc|gr_circle|gr_rect|gr_poly|gr_text)\b')
    removed = 0
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:]); break
        depth, j = 0, m.start()
        while True:                            # balanced end of this node (strings hold no parentheses here)
            c = text[j]
            if c == '"':
                j = text.index('"', j + 1)
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        node = text[m.start():j + 1]
        layer = re.search(r'\(layer ("[^"]+")', node)
        if layer and layer.group(1) in SILK_LAYERS:
            k = m.start()
            while k > i and text[k - 1] in ' \t':
                k -= 1
            out.append(text[i:k]); removed += 1
            i = j + 1
            if text[i:i + 1] == '\n':
                i += 1
        else:
            out.append(text[i:j + 1]); i = j + 1
    return ''.join(out), removed


def r4(bb):
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def text_ink(t):
    """Box of the drawn strokes (GetBoundingBox pads the text by ~50 % of its height)."""
    return r4(t.GetEffectiveTextShape().BBox())


def grow(r, d):
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def union(rs):
    rs = list(rs)
    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))


class Edge:
    """Board outline polygon: inside test and distance to the edge."""
    def __init__(self, b):
        ps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(ps, True)
        o = ps.Outline(0)
        self.pts = [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]

    def inside(self, x, y, gap):
        c, n = False, len(self.pts)
        for k in range(n):
            (x1, y1), (x2, y2) = self.pts[k], self.pts[(k + 1) % n]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        if not c:
            return False
        for k in range(n):
            (x1, y1), (x2, y2) = self.pts[k], self.pts[(k + 1) % n]
            dx, dy = x2 - x1, y2 - y1
            t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
            if math.hypot(x - x1 - t * dx, y - y1 - t * dy) < gap:
                return False
        return True

    def rect_inside(self, r, gap):
        x0, y0, x1, y1 = r
        pts = [(x0 + (x1 - x0) * i / 4, y) for i in range(5) for y in (y0, y1)]
        pts += [(x, y0 + (y1 - y0) * i / 4) for i in range(1, 4) for x in (x0, x1)]
        if any(x0 - gap < px < x1 + gap and y0 - gap < py < y1 + gap for px, py in self.pts):
            return False                        # an outline corner (plug notch) pokes into the box
        return all(self.inside(x, y, gap) for x, y in pts)


def main():
    text, removed = strip_silk(PCB.read_text())
    PCB.write_text(text)
    b = pcbnew.LoadBoard(str(PCB))
    edge = Edge(b)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints() if not fp.IsBoardOnly()}      # board-only: case screw holes H1, H2

    # keepouts per silk side: mask openings and holes
    opens = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    holes = []
    for fp in fps.values():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                holes.append(grow(r4(p.GetBoundingBox()), PAD_GAP + LINE / 2))
            for mask, silk in ((pcbnew.F_Mask, pcbnew.F_SilkS), (pcbnew.B_Mask, pcbnew.B_SilkS)):
                if p.IsOnLayer(mask):
                    opens[silk].append(grow(r4(p.GetBoundingBox()), PAD_GAP + LINE / 2))
    # vias are tented on both sides (board setup), so silk may cross them
    for k in opens:
        opens[k] += holes

    def body(ref):
        fp = fps[ref]
        back = fp.IsFlipped()
        if ref in EASYEDA_BODY:
            return r4(fp.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd).BBox())
        fab = [r4(g.GetBoundingBox()) for g in fp.GraphicalItems()
               if g.GetLayer() == (pcbnew.B_Fab if back else pcbnew.F_Fab) and g.GetClass() != 'PCB_TEXT']
        return union(fab) if fab else None
    bodies = {r: body(r) for r in fps if r != 'J1'}
    SILK = {r: (pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS) for r, fp in fps.items()}
    FAB = {r: (pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab) for r, fp in fps.items()}

    def ok(x, y, side):
        if not edge.inside(x, y, EDGE_GAP + LINE / 2):
            return False
        return not any(o[0] <= x <= o[2] and o[1] <= y <= o[3] for o in opens[side])

    drawn = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}   # silk line bboxes per side, for text placement

    def add_line(fp, x1, y1, x2, y2, side=pcbnew.F_SilkS, step=0.02):
        """Draw a segment, keeping only the runs that clear pads, holes and the edge."""
        L = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(L / step))
        run = None
        pts = [(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n + 1)]
        for k, (x, y) in enumerate(pts):
            good = (x, y) if ok(x, y, side) else None
            if good and run is None:
                run = [good, good]
            elif good:
                run[1] = good
            if (not good or k == n) and run is not None:
                (ax, ay), (bx, by) = run
                if math.hypot(bx - ax, by - ay) >= 0.3:          # no specks
                    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
                    s.SetStart(pcbnew.VECTOR2I(FromMM(ax), FromMM(ay)))
                    s.SetEnd(pcbnew.VECTOR2I(FromMM(bx), FromMM(by)))
                    s.SetLayer(side); s.SetWidth(FromMM(LINE)); fp.Add(s)
                    drawn[side].append(grow((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)), LINE / 2))
                run = None

    def add_rect(fp, r, side=pcbnew.F_SilkS):
        x0, y0, x1, y1 = r
        for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            add_line(fp, *a, *c, side=side)

    def add_dot(fp, x, y, r=0.2, side=pcbnew.F_SilkS):
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))
        s.SetEnd(pcbnew.VECTOR2I(FromMM(x + r / 2), FromMM(y)))
        s.SetLayer(side); s.SetWidth(FromMM(r)); s.SetFilled(True); fp.Add(s)
        drawn[side].append((x - r, y - r, x + r, y + r))

    # ---- outlines
    for ref, fp in fps.items():
        if ref == 'J1' or ref[0] in 'RC' or ref.startswith('TP'):
            continue
        bb = bodies[ref]
        side = SILK[ref]
        if not bb:
            continue
        if ref in ('D1', 'D2'):                 # cathode bracket: pad 1 is K on the KiCad diode/LED footprints
            k = fp.FindPadByNumber('1')
            kx = ToMM(k.GetPosition().x)
            pads = union(r4(p.GetBoundingBox()) for p in fp.Pads())
            r = grow(pads, PAD_GAP + LINE / 2 + 0.05)
            xe = r[0] if kx < ToMM(fp.GetPosition().x) else r[2]
            xm = (r[0] + r[2]) / 2
            for y in (r[1], r[3]):
                add_line(fp, xe, y, xm, y, side=side)
            add_line(fp, xe, r[1], xe, r[3], side=side)
            continue
        add_rect(fp, grow(bb, -LINE / 2) if ref in EASYEDA_BODY else bb, side=side)
        if ref.startswith('U'):                 # pin-1 dot just outside the body, beside pad 1
            p1 = fp.FindPadByNumber('1')
            px, py = ToMM(p1.GetPosition().x), ToMM(p1.GetPosition().y)
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            pr = grow(r4(p1.GetBoundingBox()), PAD_GAP + 0.25)
            cands = [(pr[0], py), (pr[2], py), (px, pr[1]), (px, pr[3])]
            kx = bb[0] - 0.35 if px < cx else bb[2] + 0.35
            ky = bb[1] - 0.35 if py < cy else bb[3] + 0.35
            cands.append((kx, ky))
            cands = [c for c in cands if not (bb[0] < c[0] < bb[2] and bb[1] < c[1] < bb[3])]
            cands = [c for c in cands if ok(c[0], c[1], side)
                     and not any(o[0] <= c[0] <= o[2] and o[1] <= c[1] <= o[3] for o in
                                 [grow(r4(q.GetBoundingBox()), PAD_GAP + 0.1) for q in fp.Pads()])]
            tight = []
            if not cands:                       # boxed in: a 0.3 mm dot 0.2 mm off the pad's outer side
                tr = grow(r4(p1.GetBoundingBox()), 0.35)
                tight = [c for c in [(tr[0], py), (tr[2], py), (px, tr[1]), (px, tr[3])]
                         if not (bb[0] < c[0] < bb[2] and bb[1] < c[1] < bb[3]) and ok(c[0], c[1], side)
                         and not any(o[0] <= c[0] <= o[2] and o[1] <= c[1] <= o[3] for o in
                                     [grow(r4(q.GetBoundingBox()), 0.3) for q in fp.Pads()])]
            if cands:
                x, y = min(cands, key=lambda c: -math.hypot(c[0] - cx, c[1] - cy))
                add_dot(fp, x, y, side=side)
            elif tight:
                x, y = min(tight, key=lambda c: -math.hypot(c[0] - cx, c[1] - cy))
                add_dot(fp, x, y, r=0.15, side=side)
            else:
                print(f'  no room for the pin-1 dot of {ref}')

    # ---- designators (fp Reference field, so they move with the part)
    placed = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    blocks = {k: [grow(o, -LINE / 2 - 0.05) for o in opens[k]] + [v for r, v in bodies.items() if v and SILK[r] == k]
              for k in opens}                   # text: JLC's 0.15 mm to pads; bodies of parts on that face
    for fp in b.GetFootprints():                # case screw holes: keep text off the case bosses (r 1.4) on both faces
        if fp.IsBoardOnly():
            hx, hy = ToMM(fp.GetPosition().x), ToMM(fp.GetPosition().y)
            for k in blocks:
                blocks[k].append((hx - 1.4, hy - 1.4, hx + 1.4, hy + 1.4))

    def text_box(t):
        return text_ink(t)

    def try_place(fp, t, anchor, quiet=False):
        """Candidates around the part's pads+body: four sides, slid along, upright or rotated 90."""
        cx, cy = (anchor[0] + anchor[2]) / 2, (anchor[1] + anchor[3]) / 2
        side = t.GetLayer()
        best = None
        why = {}
        for rot in (0, 90):
            t.SetTextAngleDegrees(rot)
            t.SetPosition(pcbnew.VECTOR2I(0, 0))
            tb = text_box(t)
            w, h = tb[2] - tb[0], tb[3] - tb[1]
            ox, oy = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
            for d in (0.1, 0.2, 0.35, 0.5, 0.8, 1.1, 1.5, 2.0, 2.5, 3.0):
                for s in [i * 0.1 for i in range(-40, 41)]:
                    for x, y in ((cx + s, anchor[1] - d - h / 2), (cx + s, anchor[3] + d + h / 2),
                                 (anchor[0] - d - w / 2, cy + s), (anchor[2] + d + w / 2, cy + s)):
                        r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                        if not edge.rect_inside(r, EDGE_GAP):
                            why['edge'] = why.get('edge', 0) + 1; continue
                        if any(hit(r, o) for o in blocks[side]):
                            why['pad/body'] = why.get('pad/body', 0) + 1; continue
                        if any(hit(r, grow(p, 0.25)) for p in placed[side]):
                            why['text'] = why.get('text', 0) + 1; continue
                        if any(hit(r, grow(dl, 0.1)) for dl in drawn[side]):
                            why['line'] = why.get('line', 0) + 1; continue
                        own = rdist(anchor, x, y)
                        if any(rdist(a, x, y) < own for rr, a in anchors.items()
                               if rr != fp.GetReference() and SILK[rr] == side):
                            why['ambiguous'] = why.get('ambiguous', 0) + 1; continue
                        score = math.hypot(x - cx, y - cy) + (0.3 if rot else 0)
                        why['ok'] = why.get('ok', 0) + 1
                        if best is None or score < best[0]:
                            best = (score, rot, x - ox, y - oy, r)
        if best is None and not quiet:
            print('   ', fp.GetReference(), 'rejected:', why)
        try_place.free = why.get('ok', 0)
        return best

    def rdist(a, x, y):
        return math.hypot(max(a[0] - x, 0, x - a[2]), max(a[1] - y, 0, y - a[3]))
    anchors = {r: union([r4(p.GetBoundingBox()) for p in fps[r].Pads()] + ([bodies[r]] if bodies.get(r) else []))
               for r in fps if r != 'J1'}

    def free_spots(ref):                        # candidates with nothing placed yet: fewest go first
        fp = fps[ref]
        t = pcbnew.PCB_TEXT(b); t.SetText(LABELS.get(ref, ref)); t.SetLayer(SILK[ref])
        t.SetTextSize(pcbnew.VECTOR2I(FromMM(REF_H), FromMM(REF_H))); t.SetTextThickness(FromMM(TEXT_W))
        try_place(fp, t, anchors[ref], quiet=True)
        return try_place.free
    order = sorted((r for r in fps if r != 'J1'), key=lambda r: (free_spots(r), r))
    missing = []
    for ref in order:
        fp = fps[ref]
        t = fp.Reference()
        t.SetLayer(SILK[ref]); t.SetVisible(True); t.SetMirrored(SILK[ref] == pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(FromMM(REF_H), FromMM(REF_H))); t.SetTextThickness(FromMM(TEXT_W))
        t.SetKeepUpright(True)
        if ref in LABELS:                       # signal name as a board text, the ref goes to F.Fab
            t.SetLayer(FAB[ref])
            t = pcbnew.PCB_TEXT(b); t.SetText(LABELS[ref]); t.SetLayer(SILK[ref]); t.SetMirrored(SILK[ref] == pcbnew.B_SilkS)
            t.SetTextSize(pcbnew.VECTOR2I(FromMM(REF_H), FromMM(REF_H))); t.SetTextThickness(FromMM(TEXT_W))
        anchor = union([r4(p.GetBoundingBox()) for p in fp.Pads()] + ([bodies[ref]] if bodies.get(ref) else []))
        best = try_place(fp, t, anchor)
        if best is None and ref in INSIDE_OK:   # big package, no room around it: inside its own outline
            t.SetTextAngleDegrees(0); t.SetPosition(pcbnew.VECTOR2I(0, 0))
            tb = text_box(t); bb = bodies[ref]
            x = (bb[0] + bb[2]) / 2 - (tb[0] + tb[2]) / 2; y = (bb[1] + bb[3]) / 2 - (tb[1] + tb[3]) / 2
            r = (tb[0] + x, tb[1] + y, tb[2] + x, tb[3] + y)
            if not any(hit(r, o) for o in opens[SILK[ref]]) and not any(hit(r, grow(q, 0.25)) for q in placed[SILK[ref]]):
                best = (0, 0, x, y, r)
                print(f'    {ref}: designator inside its outline (no room outside)')
        if best is None:
            missing.append(ref)
            if t.GetParentFootprint():
                t.SetLayer(FAB[ref])            # on the assembly drawing only
            continue
        _, rot, x, y, r = best
        t.SetTextAngleDegrees(rot); t.SetPosition(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))
        if not t.GetParentFootprint():
            b.Add(t)
        placed[SILK[ref]].append(r)

    # ---- board labels: each searched outward from a wanted spot on a given face (pads, bodies, lines, texts)
    def label(s, side, x0, y0, h=TEXT_H, rot=0, reach=4.0):
        t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetLayer(side); t.SetMirrored(side == pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(FromMM(h), FromMM(h))); t.SetTextThickness(FromMM(max(TEXT_W, h / 7)))
        t.SetTextAngleDegrees(rot); t.SetPosition(pcbnew.VECTOR2I(0, 0))
        tb = text_ink(t); w, hh = tb[2] - tb[0], tb[3] - tb[1]; ox, oy = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
        n = int(reach / 0.1)
        for dx, dy in sorted(((i * 0.1, k * 0.1) for i in range(-n, n + 1) for k in range(-n, n + 1)),
                             key=lambda d: math.hypot(*d)):
            x, y = x0 + dx, y0 + dy
            r = (x - w / 2, y - hh / 2, x + w / 2, y + hh / 2)
            if (edge.rect_inside(r, EDGE_GAP) and not any(hit(r, o) for o in blocks[side])
                    and not any(hit(r, grow(p, 0.25)) for p in placed[side])
                    and not any(hit(r, grow(dl, 0.1)) for dl in drawn[side])):
                t.SetPosition(pcbnew.VECTOR2I(FromMM(x - ox), FromMM(y - oy))); b.Add(t)
                placed[side].append(r)
                return r
        print(f'  LABEL "{s}" found no room near ({x0}, {y0})')
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    j3x, j4x = ToMM(fps['J3'].GetPosition().x), ToMM(fps['J4'].GetPosition().x)
    label('MIDI OUT', B, j3x, 27.5, 1.2)
    label('MIDI IN', B, j4x, 27.5, 1.2)
    label('TRS type A', B, 0.0, 34.0, 1.0)
    label('FM-1 MIDI', B, -4.5, 21.0, 1.3)
    label('dongle', B, -4.5, 23.0, 1.3)
    label(REV, B, 4.5, 21.0, 1.0)
    label('USB HOST', B, 1.5, 5.0, 1.0)
    j2 = ToMM(fps['J2'].GetPosition().y)
    label('5V IN', F, 7.0, j2 - 6.0, 1.0)            # above the USB-C receptacle

    b.Save(str(PCB))
    shown = sum(1 for fp in fps.values() if fp.Reference().IsVisible() and fp.Reference().GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS))
    print(f'stripped {removed} old silk items; designators on silk: {shown} + {len(LABELS)} test-pad labels;'
          f' not placed (F.Fab only): {missing or "none"}')


if __name__ == '__main__':
    main()
