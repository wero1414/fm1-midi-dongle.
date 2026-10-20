#!/usr/bin/env python3
"""Route the FM-1 MIDI dongle by hand, in code: every track is an explicit polyline.

House rules (house_rules.yaml + the owner's instructions for this board):
  - orthogonal runs, every bend a short 45 deg transition, no 90 deg corners, no long 45 deg runs
  - each signal net is a tree (no loops); power nets are trees of tracks plus pours
  - tracks 0.2 signal / 0.3 power next to fine-pitch pads / 0.5 power
  - vias 0.6/0.3 signal and GND stitching, 0.8/0.4 power
  - In1 = GND plane, In2 = +3V3 plane, GND pours on F.Cu and B.Cu, +5V_IN as a B.Cu pour on the power side

v5 (USB-A J1 on the back face). Lanes leave the MCU's top-right corner in a fixed order so nothing crosses:
DIO (y 1.45, up into TP2), RX (y 1.85, out to x 9.25 and down the right edge to the opto), TX (y 2.25, down the
corridor right of J1's rear leg into U5). OUT_SEL drops to B.Cu at R13 and comes up beside U5's S pin.
B.Cu carries USB D+/D- (vias above the MCU, straight down into J1's pads), VBUS_HOST (C3 -> J1 VBUS),
OUT_SEL, MIDI_OUT_DATA (right edge, then along y 21.45 to R7) and the +5V_IN pour on the power side.
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

# ================================================================ USB pair: one via each just above the MCU, then
# straight down on B.Cu into J1's pads (D+ left, D- right, no crossing), over the In1 GND plane
path('USB_DP', F, SIG, (-0.2, 2.6), (-0.2, 2.0), (-0.6, 1.6), (-1.0, 1.6)); via('USB_DP', -1.0, 1.6)
path('USB_DP', B, SIG, (-1.0, 1.6), (-1.0, 6.4))
path('USB_DM', F, SIG, (0.2, 2.6), (0.2, 1.45), (-0.25, 1.0)); via('USB_DM', -0.25, 1.0)
path('USB_DM', B, SIG, (-0.25, 1.0), (-0.25, 1.2), (0.25, 1.7), (0.55, 1.7), (0.8, 1.95), (0.8, 6.4))

# ================================================================ VBUS_HOST: U3 OUT -> C3 (top band) -> via -> J1 VBUS
path('VBUS_HOST', F, PWR, (-1.8, 0.8), (-1.45, 0.8), (-0.8, 0.15), (2.1, 0.15))
via('VBUS_HOST', 1.3, 0.3, VIA_P)
path('VBUS_HOST', B, PWR, (1.3, 0.3), (2.05, 0.3), (2.4, 0.65), (2.4, 5.0), (3.0, 5.6), (3.0, 6.4))

# ================================================================ SY6280 control: ISET into R4, EN down the left lane
path('ISET', F, SIG, (-2.1, -1.0), (-0.775, -1.0))
path('VBUS_EN', F, SIG, (-4.6, -1.1), (-5.145, -1.1), (-5.345, -0.9), (-5.345, 4.8), (-5.145, 5.0), (-1.4, 5.0))

# ================================================================ +5V_IN: tracks at each pad, B.Cu pour joins them
path('+5V_IN', F, PWR, (-4.4, 0.8), (-4.4, 1.6)); via('+5V_IN', -4.4, 1.6, VIA_P)                    # U3 IN
path('+5V_IN', F, PWR, (-8.9, 7.72), (-8.18, 7.72), (-7.9, 8.0))                                    # C1
path('+5V_IN', F, PWR, (-7.9, 8.0), (-7.1, 8.8), (-6.84, 8.8)); via('+5V_IN', -7.9, 8.0, VIA_P)  # U2 VI
path('+5V_IN', F, PWR, (-2.78, 13.45), (-1.44, 13.45)); via('+5V_IN', -1.44, 13.45, VIA_P)        # J2 A4/B9
path('+5V_IN', F, PWR, (-2.78, 18.35), (-1.44, 18.35)); via('+5V_IN', -1.44, 18.35, VIA_P)        # J2 A9/B4
zone('+5V_IN', B, [(-9.5, -1.47), (-1.65, -1.47), (-1.65, 9.0), (-0.9, 9.0), (-0.9, 19.75), (-9.5, 19.75)],
     priority=1, label='+5V_IN pour')

# ================================================================ +3V3: In2 plane, one power via per cluster
path('+3V3', F, SIG, (-1.4, 3.8), (-1.95, 3.8))                                  # U1 VDD: 0.2 neck between the 0.4 mm pitch pins
path('+3V3', F, PWR_MIN, (-1.95, 3.8), (-2.55, 3.8))                             # then 0.3 into C4
path('+3V3', F, PWR, (-2.55, 4.03), (-3.45, 4.03)); via('+3V3', -3.45, 4.03, VIA_P)
path('+3V3', F, PWR, (-4.36, 7.85), (-3.9, 7.85), (-3.63, 8.12), (-2.85, 8.12))  # U2 VO -> C2
path('+3V3', F, PWR, (-4.6, 7.85), (-5.3, 7.85)); via('+3V3', -5.3, 7.85, VIA_P)
path('+3V3', F, PWR_MIN, (5.4, 8.3), (3.275, 8.3))                               # U5 VCC -> C5
path('+3V3', F, PWR, (3.275, 8.3), (3.275, 9.6))                                 # C5 -> U4 VCC (pin 6)
path('+3V3', F, PWR, (2.86, 11.2), (2.86, 11.95)); via('+3V3', 2.86, 11.95, VIA_P)   # under U4's body
path('+3V3', F, PWR, (5.325, 3.75), (6.2, 3.75)); via('+3V3', 6.2, 3.75, VIA_P)  # R13 pull-up
path('+3V3', F, PWR, (8.4, 4.4), (8.4, 5.4)); via('+3V3', 8.4, 5.4, VIA_P)       # R10 pull-up
path('+3V3', F, PWR, (8.75, -0.45), (8.75, 0.75)); via('+3V3', 8.75, 0.75, VIA_P)  # TP1
path('+3V3', F, PWR, (-3.67, 22.4), (-2.8, 22.4)); via('+3V3', -2.8, 22.4, VIA_P)  # R8

# ================================================================ MCU top-right corner lanes (top to bottom: DIO, RX, TX)
path('SDI_DIO', F, SIG, (0.6, 2.6), (0.6, 1.7), (0.85, 1.45), (4.2, 1.45), (4.45, 1.2), (4.45, 0.2))
path('MIDI_RX', F, SIG, (1.8, 2.6), (1.8, 2.1), (2.05, 1.85), (9.0, 1.85), (9.25, 2.1), (9.25, 10.15),
     (9.0, 10.4), (8.6, 10.4))                                                   # pin 22 -> right edge -> U4 pin 4
path('MIDI_RX', F, SIG, (8.4, 1.85), (8.4, 2.5))                                 # R10 pull-up
path('MIDI_RX', F, SIG, (7.4, 9.6), (7.4, 9.0))                                  # U4 pin 4 -> U5 B2 (THRU input)
path('MIDI_TX', F, SIG, (2.6, 3.4), (2.6, 2.6), (2.95, 2.25), (7.18, 2.25), (7.43, 2.5), (7.43, 7.6))  # -> U5 B1
# OUT_SEL: pin 20 -> R13 (pull-up) -> B.Cu under the VBUS pad's edge -> up beside U5's S pin
path('OUT_SEL', F, SIG, (2.6, 3.8), (3.675, 3.8), (3.675, 4.65)); via('OUT_SEL', 3.675, 4.65)
path('OUT_SEL', B, SIG, (3.675, 4.65), (4.55, 5.525), (4.55, 8.75), (4.8, 9.0)); via('OUT_SEL', 4.8, 9.0)
path('OUT_SEL', F, SIG, (4.8, 9.0), (5.4, 9.0))
# U5 A -> via -> B.Cu: right edge, then along y 21.45 to R7 (the MIDI OUT jack's tip resistor)
path('MIDI_OUT_DATA', F, SIG, (5.4, 7.65), (5.15, 7.4), (5.15, 6.85)); via('MIDI_OUT_DATA', 5.15, 6.85)
path('MIDI_OUT_DATA', B, SIG, (5.15, 6.85), (5.15, 7.3), (5.45, 7.6), (8.95, 7.6), (9.2, 7.85), (9.2, 21.0),
     (8.75, 21.45), (-6.78, 21.45))
via('MIDI_OUT_DATA', -6.78, 21.45)
path('MIDI_OUT_DATA', F, SIG, (-6.78, 21.45), (-6.78, 22.4))

# ================================================================ LED, CC, MIDI OUT jack (as v4)
path('LED', F, SIG, (-1.4, 5.4), (-1.95, 5.4), (-2.15, 5.6), (-2.15, 7.5), (-1.75, 7.9), (-1.38, 7.9))
path('LED_K', F, SIG, (0.26, 7.9), (0.26, 9.55))
path('CC1_IN', F, SIG, (-2.78, 14.65), (-1.3, 14.65), (-0.6, 15.35))
path('CC2_IN', F, SIG, (-2.78, 17.65), (-1.3, 17.65), (-0.6, 16.95))
path('MIDI_TIP_OUT', F, SIG, (-8.43, 22.4), (-8.43, 25.45))
path('MIDI_RING_OUT', F, SIG, (-5.33, 22.4), (-5.33, 23.1), (-6.1, 23.87), (-6.1, 28.9), (-6.65, 29.45), (-8.0, 29.45))

# ================================================================ MIDI IN (opto 2.1 mm lower than v4)
path('MIDI_IN_TIP', F, SIG, (2.4, 22.725), (2.4, 25.3))
path('OPTO_A', F, SIG, (2.4, 21.0), (2.4, 20.5))                                 # R9 -> U4 pin 1
path('OPTO_A', F, SIG, (4.55, 21.4), (4.55, 21.1), (4.0, 20.55), (3.6, 20.55))   # D1 -> U4 pin 1
path('MIDI_IN_RING', F, SIG, (6.0, 20.4), (6.0, 20.75), (6.15, 20.9), (7.6, 20.9), (7.85, 21.15), (7.85, 21.4))
path('MIDI_IN_RING', F, SIG, (7.85, 22.2), (7.85, 22.75), (7.35, 23.25), (4.6, 23.25), (4.0, 23.85),
     (4.0, 28.6), (3.15, 29.45), (2.0, 29.45))

# ================================================================ GND: a stitching via at every GND pad cluster
GND_VIAS = [
    (-3.25, -0.15),                     # U3 pin 2, under its body between the pin rows
    (1.55, -0.95),                      # R4 + C3 (between their GND pads)
    (-3.55, 2.48),                      # C4
    (-3.55, 6.45),                      # R12; on B.Cu it lands in J1's GND pad 4
    (2.225, 7.5),                       # C5
    (8.4, 8.3),                         # U5 pin 2
    (5.4, 11.95),                       # U4 pin 5, under its body
    (-2.0, 10.5),                       # C2 / U2 GND / D2
    (-1.44, 12.45), (-1.44, 19.5),      # J2 GND contacts
    (0.6, 13.72), (0.6, 18.58),         # R2, R3
    (-8.6, 1.85),                       # TP3 (GND LinkE pad, top-left corner)
    (-1.7, 23.2), (-6.2, 32.45),        # J3 sleeve pads
]
for x, y in GND_VIAS:
    via('GND', x, y)
path('GND', F, PWR_MIN, (-2.1, -0.15), (-3.25, -0.15))
path('GND', F, PWR, (0.875, -0.95), (2.3, -0.95))
path('GND', F, PWR, (-2.55, 2.48), (-3.55, 2.48))
path('GND', F, PWR, (-4.2, 6.45), (-3.55, 6.45))
path('GND', F, PWR_MIN, (1.725, 8.0), (2.225, 7.5))
path('GND', F, PWR_MIN, (7.338, 8.3), (8.4, 8.3))
path('GND', F, PWR, (5.4, 11.2), (5.4, 11.95))
path('GND', F, PWR, (-4.36, 9.7), (-2.85, 9.7))
path('GND', F, PWR, (-2.85, 9.7), (-2.85, 10.1), (-2.45, 10.5), (-2.0, 10.5))
path('GND', F, PWR, (-1.34, 9.55), (-1.34, 10.2), (-1.64, 10.5), (-2.0, 10.5))
path('GND', F, PWR, (-2.78, 12.65), (-1.64, 12.65), (-1.44, 12.45))
path('GND', F, PWR_MIN, (-2.78, 19.15), (-1.64, 19.15), (-1.44, 19.35), (-1.44, 19.5))
path('GND', F, PWR, (-0.35, 13.72), (0.6, 13.72))
path('GND', F, PWR, (-0.35, 18.58), (0.6, 18.58))
path('GND', F, PWR, (-8.6, 0.4), (-8.6, 1.85))                                     # TP3
path('GND', F, PWR, (-2.0, 24.35), (-1.7, 24.05), (-1.7, 23.2))
path('GND', F, PWR, (-8.0, 32.45), (-6.2, 32.45))

# GND pads already tied by a trace whose pour pocket is too tight for two spokes: solid to the pour instead.
# J1's shell legs sit between lanes (RX / TX right, EN / TP3 left), where the F.Cu pour reaches them with one spoke
FP = {f.GetReference(): f for f in b.GetFootprints()}
for ref, num in (('D2', '1'), ('J1', '5'), ('J1', '6'), ('J1', '7'), ('J1', '8')):
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
