#!/usr/bin/env python3
"""Route the FM-1 MIDI dongle by hand, in code: every track is an explicit polyline.

House rules (house_rules.yaml + the owner's instructions for this board):
  - orthogonal runs, every bend a short 45 deg transition, no 90 deg corners, no long 45 deg runs
  - each signal net is a tree (no loops); power nets are trees of tracks plus pours
  - tracks 0.2 signal / 0.3 power next to fine-pitch pads / 0.5 power
  - vias 0.6/0.3 signal and GND stitching, 0.8/0.4 power
  - In1 = GND plane, In2 = +3V3 plane, GND pours on F.Cu and B.Cu, +5V_IN as a B.Cu pour on the power side

Layers: F.Cu parts and short links; B.Cu carries the long nets (MIDI_OUT_DATA, MIDI_TX, CC_FM1, VBUS_EN) and the 5 V pour.
Run:  python3 tools/gen_pcb.py && python3 tools/route.py
"""
import pathlib
import pcbnew
from pcbnew import VECTOR2I_MM as MM, FromMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):          # KiCad 10 SWIG + Python 3.14: __iter__ calls it.next()
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

HERE = pathlib.Path(__file__).resolve().parent.parent
PCB = HERE / 'fm1-midi-dongle.kicad_pcb'
F, B = pcbnew.F_Cu, pcbnew.B_Cu
SIG, PWR_MIN, PWR = 0.2, 0.3, 0.5
VIA_S, VIA_P = (0.6, 0.3), (0.8, 0.4)

b = pcbnew.LoadBoard(str(PCB))
NET = {n: b.FindNet(n) for n in [str(k) for k in b.GetNetsByName().keys()]}


def net(name):
    n = NET.get(name) or NET.get('/' + name)
    if n is None:
        raise SystemExit(f'no net {name}')
    return n


def path(name, layer, width, *pts):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(MM(x1, y1)); t.SetEnd(MM(x2, y2))
        t.SetWidth(FromMM(width)); t.SetLayer(layer); t.SetNet(net(name))
        b.Add(t)


def via(name, x, y, size=VIA_S):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(MM(x, y)); v.SetWidth(FromMM(size[0])); v.SetDrill(FromMM(size[1]))
    v.SetLayerPair(F, B); v.SetNet(net(name))
    b.Add(v)


def zone(name, layer, poly, priority=0, label=''):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(net(name)); z.SetAssignedPriority(priority)
    z.SetZoneName(label or f'{name} pour')
    z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.25))
    z.SetThermalReliefGap(FromMM(0.5)); z.SetThermalReliefSpokeWidth(FromMM(0.5))
    o = z.Outline(); o.NewOutline()
    for x, y in poly:
        o.Append(MM(x, y))
    b.Add(z)


# ---- start from a freshly placed board (deleting tracks through the SWIG API crashes KiCad 10's bindings)
if any(not t.IsLocked() for t in b.GetTracks()):
    raise SystemExit('board already routed: run tools/gen_pcb.py first, then this script')

# ================================================================ USB pair: straight up, F.Cu over In1 GND
path('USB_DP', F, SIG, (-0.2, 2.6), (-0.2, 0.0))
path('USB_DM', F, SIG, (0.2, 2.6), (0.2, 0.0))

# ================================================================ VBUS_FM1: U3 OUT -> plug A4 (top), B4 + B9 (back)
path('VBUS_FM1', F, PWR_MIN, (-1.25, 0.0), (-1.25, 1.0), (-1.55, 1.3))          # A4 stub, 0.3 between 0.5 mm pads
path('VBUS_FM1', F, PWR, (-1.55, 1.3), (-4.75, 1.3), (-6.62, 1.3))             # trunk to C3
path('VBUS_FM1', F, PWR, (-4.75, 1.3), (-5.05, 1.6), (-5.05, 2.75))            # branch to U3 pin 1
via('VBUS_FM1', -2.0, 1.3, VIA_P)                                               # to the back-face contacts
path('VBUS_FM1', B, PWR_MIN, (1.25, 0.0), (1.25, 1.0), (0.95, 1.3), (-2.0, 1.3))  # B4
path('VBUS_FM1', B, PWR_MIN, (-1.25, 0.0), (-1.25, 1.0), (-1.55, 1.3))         # B9 joins the B4 link

# ================================================================ CC_FM1: plug A5 -> R1 (back layer under VBUS)
path('CC_FM1', F, SIG, (-0.75, 0.0), (-0.75, 1.95), (-1.2, 2.4), (-1.3, 2.4))
via('CC_FM1', -1.3, 2.4)
path('CC_FM1', B, SIG, (-1.3, 2.4), (-2.0, 3.1), (-5.45, 3.1), (-5.75, 2.8), (-5.75, -0.55))
via('CC_FM1', -5.75, -0.55)
path('CC_FM1', F, SIG, (-5.75, -0.55), (-6.58, -0.55))

# ================================================================ +5V_IN: tracks at each pad, B.Cu pour joins them
path('+5V_IN', F, PWR, (-8.22, -0.55), (-9.1, -0.55)); via('+5V_IN', -9.1, -0.55, VIA_P)          # R1
path('+5V_IN', F, PWR, (-5.05, 5.05), (-4.25, 5.05)); via('+5V_IN', -4.25, 5.05, VIA_P)           # U3 IN
path('+5V_IN', F, PWR, (-8.9, 7.72), (-8.18, 7.72), (-7.9, 8.0))                                    # C1
path('+5V_IN', F, PWR, (-7.9, 8.0), (-7.1, 8.8), (-6.84, 8.8)); via('+5V_IN', -7.9, 8.0, VIA_P)  # U2 VI
path('+5V_IN', F, PWR, (-2.78, 13.45), (-1.44, 13.45)); via('+5V_IN', -1.44, 13.45, VIA_P)        # J2 A4/B9
path('+5V_IN', F, PWR, (-2.78, 18.35), (-1.44, 18.35)); via('+5V_IN', -1.44, 18.35, VIA_P)        # J2 A9/B4
zone('+5V_IN', B, [(-9.5, -1.47), (-5.0, -1.47), (-5.0, 1.9), (-0.9, 1.9), (-0.9, 19.75), (-9.5, 19.75)],
     priority=1, label='+5V_IN pour')

# ================================================================ +3V3: In2 plane, one power via per cluster
path('+3V3', F, SIG, (-1.4, 3.8), (-2.55, 3.8))                                  # U1 VDD -> C4 (0.4 mm pitch)
path('+3V3', F, PWR, (-2.55, 4.03), (-3.6, 4.03)); via('+3V3', -3.6, 4.03, VIA_P)
path('+3V3', F, PWR, (-4.36, 7.85), (-3.9, 7.85), (-3.63, 8.12), (-2.85, 8.12))  # U2 VO -> C2
path('+3V3', F, PWR, (-2.85, 8.12), (-2.85, 7.4), (-3.1, 7.15)); via('+3V3', -3.1, 7.0, VIA_P)
path('+3V3', F, PWR, (-3.1, 7.15), (-3.1, 7.0))
path('+3V3', F, PWR, (3.325, 7.1), (3.325, 7.6))                                 # C5 -> U4 VCC (pin 6)
path('+3V3', F, PWR, (2.86, 8.2), (1.3, 8.2)); via('+3V3', 1.3, 8.2, VIA_P)
path('+3V3', F, PWR, (8.7, -0.45), (8.7, 2.48)); via('+3V3', 8.7, 1.2, VIA_P)  # TP1 -> R10
path('+3V3', F, PWR, (-3.67, 22.4), (-2.8, 22.4)); via('+3V3', -2.8, 22.4, VIA_P)            # R8

# ================================================================ logic and MIDI
path('VBUS_EN', F, SIG, (-1.4, 5.0), (-2.85, 5.0)); via('VBUS_EN', -2.85, 5.0)
path('VBUS_EN', B, SIG, (-2.85, 5.0), (-3.75, 5.9), (-6.85, 5.9), (-7.7, 5.05)); via('VBUS_EN', -7.7, 5.05)
path('VBUS_EN', F, SIG, (-7.7, 5.05), (-6.95, 5.05))
path('VBUS_EN', F, SIG, (-6.9, 5.3), (-6.9, 6.3))                                 # U3 EN -> R12
path('ISET', F, SIG, (-8.9, 3.0), (-6.95, 3.0))
path('LED', F, SIG, (-1.4, 5.4), (-1.95, 5.4), (-2.15, 5.6), (-2.15, 7.5), (-1.75, 7.9), (-1.38, 7.9))
path('LED_K', F, SIG, (0.26, 7.9), (0.26, 9.55))
path('SDI_DIO', F, SIG, (0.6, 2.6), (0.6, 1.6), (0.9, 1.3), (5.85, 1.3), (6.15, 1.0), (6.15, -0.45))
path('MIDI_RX', F, SIG, (1.8, 2.6), (1.8, 2.1), (2.1, 1.8), (7.3, 1.8), (7.6, 2.1), (7.6, 3.6),
     (7.9, 3.9), (8.4, 3.9))                                                     # pin 22 -> R10
path('MIDI_RX', F, SIG, (8.7, 4.12), (8.7, 7.6))                                 # R10 -> U4 pin 4
path('MIDI_RX', F, SIG, (7.47, 6.6), (7.47, 7.5))                                  # U4 pin 4 -> U5 B1 (THRU)

# ---- hardware THRU switch U5: the OUT jack's tip follows B1 (opto, OUT_SEL low) or B2 (TX, OUT_SEL high)
path('MIDI_TX', F, SIG, (2.6, 3.4), (2.95, 3.4), (3.2, 3.15), (3.2, 2.6)); via('MIDI_TX', 3.2, 2.6)
path('MIDI_TX', B, SIG, (3.2, 2.6), (3.2, 5.15), (3.5, 5.45), (5.4, 5.45)); via('MIDI_TX', 5.4, 5.45)
path('MIDI_TX', F, SIG, (5.4, 5.45), (6.07, 6.12))                                # -> U5 B2
path('OUT_SEL', F, SIG, (2.6, 3.8), (5.87, 3.8), (6.17, 4.1), (6.17, 4.4))          # PB9 -> U5 S
path('OUT_SEL', F, SIG, (4.175, 3.225), (4.175, 3.8))                            # R13 pull-down
path('+3V3', F, PWR_MIN, (6.82, 4.4), (6.82, 3.5)); via('+3V3', 6.82, 3.5, VIA_P)  # U5 VCC
path('GND', F, PWR_MIN, (6.82, 6.6), (6.82, 6.85), (6.27, 7.4))                   # U5 GND -> U4 pin 5
path('GND', F, PWR_MIN, (5.775, 2.75), (6.25, 2.75), (6.55, 2.45)); via('GND', 6.55, 2.45)  # R13
path('MIDI_OUT_DATA', F, SIG, (7.47, 4.9), (7.75, 4.9), (8.1, 5.25)); via('MIDI_OUT_DATA', 8.1, 5.25)
path('MIDI_OUT_DATA', B, SIG, (8.1, 5.25), (8.1, 21.0), (7.65, 21.45), (-6.78, 21.45))
via('MIDI_OUT_DATA', -6.78, 21.45)
path('MIDI_OUT_DATA', F, SIG, (-6.78, 21.45), (-6.78, 22.4))
path('MIDI_TIP_OUT', F, SIG, (-8.43, 22.4), (-8.43, 25.45))
path('MIDI_RING_OUT', F, SIG, (-5.33, 22.4), (-5.33, 23.1), (-6.1, 23.87), (-6.1, 28.9), (-6.65, 29.45), (-8.0, 29.45))
path('CC1_IN', F, SIG, (-2.78, 14.65), (-1.3, 14.65), (-0.6, 15.35))
path('CC2_IN', F, SIG, (-2.78, 17.65), (-1.3, 17.65), (-0.6, 16.95))
path('MIDI_IN_TIP', F, SIG, (2.4, 21.23), (2.4, 25.45))
path('OPTO_A', F, SIG, (2.4, 19.57), (2.4, 18.0))
path('OPTO_A', F, SIG, (4.55, 20.3), (4.55, 19.0), (3.55, 18.0))
path('MIDI_IN_RING', F, SIG, (5.4, 17.5), (6.47, 17.5), (6.77, 17.8), (6.77, 19.4), (7.67, 20.3), (7.85, 20.3))
path('MIDI_IN_RING', F, SIG, (7.85, 20.3), (7.85, 21.2), (6.95, 22.1), (4.6, 22.1), (4.0, 22.7),
     (4.0, 28.6), (3.15, 29.45), (2.0, 29.45))

# ================================================================ GND: a stitching via at every GND pad cluster
GND_VIAS = [
    (-4.5, 0.2), (3.6, 0.2),            # plug: pad 25 / A1 / B12 and pad 26 / A12 / B1 (pours join the rows)
    (-8.18, 1.85),                      # C3
    (-3.5, 2.48),                       # C4
    (-6.0, 3.9),                        # U3 pin 2 (between the pin rows)
    (-8.9, 5.75),                       # R4
    (-5.6, 7.3),                        # R12
    (-2.0, 10.5),                       # C2 / U2 GND / D2
    (-1.44, 12.45), (-1.44, 19.5),      # J2 GND contacts
    (0.6, 13.72), (0.6, 18.58),         # R2, R3
    (1.05, 20.4),                       # TP3 (clear of the MIDI_OUT_DATA run on B.Cu at y 21.45)
    (5.4, 9.6),                         # U4 pin 5
    (-1.7, 23.2), (-6.2, 32.45),        # J3 sleeve pads
]
for x, y in GND_VIAS:
    via('GND', x, y)
path('GND', F, PWR_MIN, (-6.0, 2.75), (-6.0, 3.9))
path('GND', F, PWR, (-2.55, 2.48), (-3.5, 2.48))
path('GND', F, PWR, (-4.36, 9.7), (-2.85, 9.7))
path('GND', F, PWR, (-2.85, 9.7), (-2.85, 10.1), (-2.45, 10.5), (-2.0, 10.5))
path('GND', F, PWR, (-1.34, 9.55), (-1.34, 10.2), (-1.64, 10.5), (-2.0, 10.5))
path('GND', F, PWR, (-2.78, 12.65), (-1.64, 12.65), (-1.44, 12.45))
path('GND', F, PWR_MIN, (-2.78, 19.15), (-1.64, 19.15), (-1.44, 19.35), (-1.44, 19.5))
path('GND', F, PWR, (-0.35, 13.72), (0.6, 13.72))
path('GND', F, PWR, (-0.35, 18.58), (0.6, 18.58))
path('GND', F, PWR, (4.875, 7.1), (4.875, 7.6))                                  # C5 -> U4 pin 5
path('GND', F, PWR, (0.4, 20.4), (1.05, 20.4))                                     # TP3
path('GND', F, PWR, (5.4, 8.2), (5.4, 9.6))
path('GND', F, PWR, (-8.9, 4.83), (-8.9, 5.75))
path('GND', F, PWR, (-5.17, 6.45), (-5.17, 6.87), (-5.6, 7.3))
path('GND', F, PWR, (-8.18, 0.95), (-8.18, 1.85))
path('GND', F, PWR, (-2.0, 24.35), (-1.7, 24.05), (-1.7, 23.2))
path('GND', F, PWR, (-8.0, 32.45), (-6.2, 32.45))
# plug GND contacts: explicit links to their stitching vias (pours alone reach them with one spoke)
path('GND', F, PWR_MIN, (-2.75, 0.2), (-3.6, 0.2), (-4.5, 0.2))     # A1 + pad 25
path('GND', B, PWR_MIN, (-2.75, 0.2), (-4.5, 0.2))                  # B12
path('GND', F, PWR_MIN, (2.75, 0.2), (3.6, 0.2))                    # A12
path('GND', B, PWR_MIN, (2.75, 0.2), (3.6, 0.2))                    # B1 + pad 26

# GND pads already tied by a trace whose pour pocket is too tight for two spokes: solid to the pour instead
FP = {f.GetReference(): f for f in b.GetFootprints()}
for ref, num in (('D2', '1'), ('C5', '2')):
    for pad in FP[ref].Pads():
        if pad.GetNumber() == num:
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

OUTLINE = [(-10, -1.97), (10, -1.97), (10, 36.0), (-10, 36.0)]
zone('GND', F, OUTLINE, priority=0, label='GND F pour')
zone('GND', B, OUTLINE, priority=0, label='GND B pour')

b.BuildConnectivity()
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(str(PCB))
print('routed:', sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK'), 'tracks,',
      sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_VIA'), 'vias,', len(list(b.Zones())), 'zones')
