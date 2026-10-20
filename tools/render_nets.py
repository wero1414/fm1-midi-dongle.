#!/usr/bin/env python3
"""Render the placement with its ratsnest: pads coloured by net, one line per unrouted connection (minimum
spanning tree per net, as KiCad's ratsnest), net names on the lines, part outlines and references.
GND and +3V3 pads are marked instead of drawn: they reach the In1 / In2 planes through a via.

Run: python3 tools/render_nets.py   ->  docs/pcb_nets_top.png, docs/pcb_nets_bottom.png (both seen from the top;
each shows that face's parts in full and the other face's pads faded, so every ratsnest line has both ends)
"""
import math, pathlib
import pcbnew
from pcbnew import ToMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):          # KiCad 10 SWIG + Python 3.14: __iter__ calls it.next()
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

HERE = pathlib.Path(__file__).resolve().parent.parent
PLANE = {'GND': ('#555555', 'G'), '+3V3': ('#d62728', '3')}
COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#17becf', '#bcbd22',
          '#7f7f7f', '#393b79', '#e6550d', '#31a354', '#756bb1', '#843c39', '#3182bd', '#637939',
          '#d6616b', '#ce6dbd', '#6baed6', '#fd8d3c']


def main(side):
    b = pcbnew.LoadBoard(str(HERE / 'fm1-midi-dongle.kicad_pcb'))
    fig, ax = plt.subplots(figsize=(11, 19), dpi=150)
    on_side = (lambda fp: fp.IsFlipped()) if side == 'bottom' else (lambda fp: not fp.IsFlipped())

    for d in b.GetDrawings():                           # board outline
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if d.GetShape() == pcbnew.SHAPE_T_ARC:
            c, r = d.GetCenter(), ToMM(d.GetRadius())
            cx, cy = ToMM(c.x), ToMM(c.y)
            a0 = math.atan2(ToMM(d.GetStart().y) - cy, ToMM(d.GetStart().x) - cx)
            am = math.atan2(ToMM(d.GetArcMid().y) - cy, ToMM(d.GetArcMid().x) - cx)
            a1 = math.atan2(ToMM(d.GetEnd().y) - cy, ToMM(d.GetEnd().x) - cx)
            span = (a1 - a0) % (2 * math.pi)
            if (am - a0) % (2 * math.pi) > span:          # the arc runs the other way round
                span -= 2 * math.pi
            ts = [a0 + span * i / 16 for i in range(17)]
            ax.plot([cx + r * math.cos(t) for t in ts], [cy + r * math.sin(t) for t in ts], color='black', lw=1.2)
        else:
            ax.plot([ToMM(d.GetStart().x), ToMM(d.GetEnd().x)], [ToMM(d.GetStart().y), ToMM(d.GetEnd().y)],
                    color='black', lw=1.2)

    nets = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
        x0, y0, x1, y1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
        mine = on_side(fp)
        if mine:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec='#777777', lw=0.7, ls='--'))
            ax.text((x0 + x1) / 2, y0 - 0.15, f'{ref} {fp.GetValue()}', ha='center', va='bottom', fontsize=6.5,
                    color='#222222', weight='bold')
        else:                                             # other face: faint outline only
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec='#cccccc', lw=0.5, ls=':'))
        for p in fp.Pads():
            n = p.GetNetname()
            tht = p.IsOnLayer(pcbnew.B_Cu) and p.IsOnLayer(pcbnew.F_Cu)
            back_only = not (mine or tht)                 # 'back' = the face not being shown
            pb = p.GetBoundingBox()
            px0, py0, px1, py1 = ToMM(pb.GetLeft()), ToMM(pb.GetTop()), ToMM(pb.GetRight()), ToMM(pb.GetBottom())
            if p.GetDrillSize().x > 0 and not p.GetNumber():
                ax.add_patch(Circle(((px0 + px1) / 2, (py0 + py1) / 2), (px1 - px0) / 2, color='black'))
                continue
            if not n or n.startswith('unconnected'):
                col = '#dddddd'
            else:
                nets.setdefault(n, []).append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), back_only))
                col = None
            ax.add_patch(Rectangle((px0, py0), px1 - px0, py1 - py0, fc=col or 'white', ec='#444444',
                                   lw=0.4, ls=':' if back_only else '-', zorder=2, alpha=0.5 if back_only else 1))

    names = sorted(n for n in nets if n not in PLANE)
    color = {n: COLORS[i % len(COLORS)] for i, n in enumerate(names)}
    for n, pts in nets.items():
        if n in PLANE:
            c, tag = PLANE[n]
            for x, y, back in pts:
                ax.add_patch(Circle((x, y), 0.32, color=c, zorder=4, alpha=0.5 if back else 1))
                ax.text(x, y, tag, ha='center', va='center', fontsize=5, color='white', zorder=5, weight='bold')
            continue
        c = color[n]
        for x, y, back in pts:
            ax.add_patch(Circle((x, y), 0.22, color=c, zorder=4))
        inside, edges = {0}, []
        while len(inside) < len(pts):                     # Prim: KiCad-like ratsnest
            d, i, k = min((math.dist(pts[i][:2], pts[k][:2]), i, k)
                          for i in inside for k in range(len(pts)) if k not in inside)
            inside.add(k); edges.append((i, k, d))
        for i, k, d in edges:
            (xa, ya, _), (xb, yb, _) = pts[i], pts[k]
            ax.plot([xa, xb], [ya, yb], color=c, lw=1.4, zorder=3)
        i, k, d = max(edges, key=lambda e: e[2])
        mx, my = (pts[i][0] + pts[k][0]) / 2, (pts[i][1] + pts[k][1]) / 2
        ax.text(mx, my, n.lstrip('/'), fontsize=6, color=c, ha='center', va='center', zorder=6, weight='bold',
                bbox=dict(fc='white', ec=c, lw=0.5, pad=0.6, alpha=0.9))

    handles = [plt.Line2D([], [], color=color[n], lw=2, label=n.lstrip('/')) for n in names]
    handles += [plt.Line2D([], [], marker='o', ls='', color=PLANE[n][0], label=f'{n} (pad -> via -> plane)')
                for n in PLANE]
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    ax.set_aspect('equal'); ax.invert_yaxis()
    ax.set_xlabel('mm'); ax.set_ylabel('mm'); ax.grid(True, lw=0.2, alpha=0.5)
    ax.set_title(f'FM-1 MIDI dongle v6 placement: {side.upper()} face parts (seen from the top), ratsnest\n'
                 'faded = pads on the other face; black = holes', fontsize=10)
    out = HERE / 'docs' / f'pcb_nets_{side}.png'
    fig.savefig(out, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    for sd in ('top', 'bottom'):
        main(sd)
