#!/usr/bin/env python3
"""Render the routed board for review without KiCad: F.Cu and B.Cu side by side (both seen from the top),
pours shaded by net, tracks drawn at their real width in their net's colour, vias as rings, pads outlined.

Run: python3 tools/render_route.py   ->  docs/pcb_route.png
"""
import pathlib
import pcbnew
from pcbnew import ToMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle

HERE = pathlib.Path(__file__).resolve().parent.parent
COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#17becf', '#bcbd22',
          '#393b79', '#e6550d', '#31a354', '#756bb1', '#843c39', '#3182bd', '#637939', '#d6616b',
          '#ce6dbd', '#6baed6', '#fd8d3c']
FIXED = {'GND': '#606060', '+3V3': '#d62728', '+5V_IN': '#ff9896', 'VBUS_HOST': '#e31a1c'}


def outline(ax, b):
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if d.GetShape() == pcbnew.SHAPE_T_ARC:
            import math
            c, r = d.GetCenter(), ToMM(d.GetRadius())
            cx, cy = ToMM(c.x), ToMM(c.y)
            a0 = math.atan2(ToMM(d.GetStart().y) - cy, ToMM(d.GetStart().x) - cx)
            am = math.atan2(ToMM(d.GetArcMid().y) - cy, ToMM(d.GetArcMid().x) - cx)
            a1 = math.atan2(ToMM(d.GetEnd().y) - cy, ToMM(d.GetEnd().x) - cx)
            span = (a1 - a0) % (2 * math.pi)
            if (am - a0) % (2 * math.pi) > span:
                span -= 2 * math.pi
            ts = [a0 + span * i / 16 for i in range(17)]
            ax.plot([cx + r * math.cos(t) for t in ts], [cy + r * math.sin(t) for t in ts], color='black', lw=1)
        else:
            ax.plot([ToMM(d.GetStart().x), ToMM(d.GetEnd().x)], [ToMM(d.GetStart().y), ToMM(d.GetEnd().y)],
                    color='black', lw=1)


def main():
    b = pcbnew.LoadBoard(str(HERE / 'fm1-midi-dongle.kicad_pcb'))
    nets = sorted({t.GetNetname() for t in b.GetTracks()} | {z.GetNetname() for z in b.Zones() if z.GetNetname()})
    color = dict(FIXED)
    i = 0
    for n in nets:
        if n not in color:
            color[n] = COLORS[i % len(COLORS)]; i += 1

    fig, axes = plt.subplots(1, 2, figsize=(17, 12.5), dpi=150)
    for ax, layer, title in ((axes[0], pcbnew.F_Cu, 'F.Cu (top, parts side)'),
                             (axes[1], pcbnew.B_Cu, 'B.Cu (back, seen from the top)')):
        outline(ax, b)
        for z in b.Zones():                                    # pour fills
            if z.GetIsRuleArea() or not z.IsOnLayer(layer):
                continue
            polys = z.GetFilledPolysList(layer)
            for k in range(polys.OutlineCount()):
                ol = polys.Outline(k)
                pts = [(ToMM(ol.CPoint(j).x), ToMM(ol.CPoint(j).y)) for j in range(ol.PointCount())]
                if pts:
                    ax.add_patch(Polygon(pts, closed=True, fc=color.get(z.GetNetname(), '#cccccc'), alpha=0.18,
                                         ec='none'))
        for fp in b.GetFootprints():                           # pads on this layer
            for p in fp.Pads():
                if not p.IsOnLayer(layer):
                    continue
                bb = p.GetBoundingBox()
                x0, y0, x1, y1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
                n = p.GetNetname()
                c = color.get(n, '#bbbbbb') if n and not n.startswith('unconnected') else '#dddddd'
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=c, ec='black', lw=0.3, alpha=0.55, zorder=2))
            if layer == pcbnew.F_Cu and fp.GetReference() != 'J1':
                bb = fp.GetBoundingBox(False, False)
                ax.text(ToMM(bb.GetCenter().x), ToMM(bb.GetCenter().y), fp.GetReference(), fontsize=6,
                        ha='center', va='center', color='black', alpha=0.6, zorder=6)
        for t in b.GetTracks():                                # tracks at true width
            if t.GetClass() != 'PCB_TRACK' or t.GetLayer() != layer:
                continue
            w = ToMM(t.GetWidth())
            ax.plot([ToMM(t.GetStart().x), ToMM(t.GetEnd().x)], [ToMM(t.GetStart().y), ToMM(t.GetEnd().y)],
                    color=color[t.GetNetname()], lw=w * 72 / 25.4 * 150 / 150 * 9.0, solid_capstyle='round',
                    zorder=4)
        for v in b.GetTracks():                                # vias
            if v.GetClass() != 'PCB_VIA':
                continue
            x, y = ToMM(v.GetPosition().x), ToMM(v.GetPosition().y)
            ax.add_patch(Circle((x, y), ToMM(v.GetWidth(pcbnew.F_Cu)) / 2, fc=color[v.GetNetname()], ec='black',
                                lw=0.4, zorder=5))
            ax.add_patch(Circle((x, y), ToMM(v.GetDrillValue()) / 2, fc='white', ec='none', zorder=6))
        ax.set_aspect('equal'); ax.invert_yaxis(); ax.set_title(title, fontsize=11)
        ax.set_xlim(-11.5, 11.5); ax.set_ylim(37, -3)
        ax.grid(True, lw=0.2, alpha=0.4)
    handles = [plt.Line2D([], [], color=color[n], lw=3, label=n.lstrip('/')) for n in nets]
    fig.legend(handles=handles, loc='center right', fontsize=8, frameon=False)
    fig.suptitle('FM-1 MIDI dongle v6 routing: pours shaded, tracks at true width, vias as rings '
                 '(In1 = GND plane, In2 = +3V3 plane)', fontsize=11)
    fig.subplots_adjust(right=0.86, wspace=0.08, top=0.95)
    out = HERE / 'docs' / 'pcb_route.png'
    fig.savefig(out, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    main()
