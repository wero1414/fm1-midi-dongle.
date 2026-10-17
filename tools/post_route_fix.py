#!/usr/bin/env python3
"""Hand fixes after the router: a GND via for C5 pad 2, where plane_via found no spot (board edge + D1 + jack peg)."""
import sys, pcbnew
from pcbnew import VECTOR2I_MM as MM, FromMM
src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
gnd = b.FindNet('GND')
v = pcbnew.PCB_VIA(b); v.SetPosition(MM(-8.9, 22.6)); v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.2))
v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
t = pcbnew.PCB_TRACK(b); t.SetStart(MM(-7.6, 21.62)); t.SetEnd(MM(-8.9, 22.6)); t.SetWidth(FromMM(0.2)); t.SetLayer(pcbnew.B_Cu); t.SetNet(gnd); b.Add(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(dst); print('C5.2 GND via + stub added')
