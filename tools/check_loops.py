#!/usr/bin/env python3
"""Count loops in the routed copper per net (tracks + vias + pads; pours and planes excluded):
cycles = edges - nodes + connected groups. A tree has 0. Also prints the longest 45 deg segment per net.
Run: python3 tools/check_loops.py
"""
import math, pathlib
import pcbnew
from pcbnew import ToMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

b = pcbnew.LoadBoard(str(pathlib.Path(__file__).resolve().parent.parent / 'fm1-midi-dongle.kicad_pcb'))
pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname()]
tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
nets = sorted({t.GetNetname() for t in tracks})
bad = 0
for n in nets:
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, c):
        parent[find(a)] = find(c)
    def node(x, y, layer):
        for i, v in enumerate(vs):                 # a via joins every layer at its position
            if math.dist((x, y), v[:2]) <= v[2] + 1e-3:
                return ('via', i)
        for i, p in enumerate(ps):
            if p[3] in (layer, 'both') and abs(x - p[0]) <= p[2][0] / 2 + 1e-3 and abs(y - p[1]) <= p[2][1] / 2 + 1e-3:
                return ('pad', i)
        return (round(x, 3), round(y, 3), layer)
    vs = [(ToMM(v.GetPosition().x), ToMM(v.GetPosition().y), ToMM(v.GetWidth(pcbnew.F_Cu)) / 2) for v in vias if v.GetNetname() == n]
    ps = []
    for p in pads:
        if p.GetNetname() != n:
            continue
        bb = p.GetBoundingBox()
        lay = 'both' if p.IsOnLayer(pcbnew.F_Cu) and p.IsOnLayer(pcbnew.B_Cu) else ('F' if p.IsOnLayer(pcbnew.F_Cu) else 'B')
        ps.append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), (ToMM(bb.GetWidth()), ToMM(bb.GetHeight())), lay))
    edges, nodes, long45 = 0, set(), 0.0
    for t in (t for t in tracks if t.GetNetname() == n):
        lay = 'F' if t.GetLayer() == pcbnew.F_Cu else 'B'
        a = node(ToMM(t.GetStart().x), ToMM(t.GetStart().y), lay)
        c = node(ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), lay)
        dx, dy = abs(ToMM(t.GetEnd().x - t.GetStart().x)), abs(ToMM(t.GetEnd().y - t.GetStart().y))
        if dx > 1e-3 and dy > 1e-3:
            long45 = max(long45, math.hypot(dx, dy))
        if a == c:
            continue
        nodes |= {a, c}; edges += 1; union(a, c)
    groups = len({find(x) for x in nodes})
    cyc = edges - len(nodes) + groups
    bad += cyc > 0
    print(f'{n:16s} segments {edges:3d}  loops {cyc}  longest 45 {long45:4.2f} mm')
print('nets with loops:', bad)
