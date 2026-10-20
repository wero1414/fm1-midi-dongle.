#!/usr/bin/env python3
"""Route the FM-1 MIDI dongle v6 ("slab") by hand, in code: every track is an explicit polyline. No autorouter.

v6: tall parts on the top face (USB-A J1, USB-C J2, opto U4, jacks, THRU switch U5, LED), low parts on the
bottom face (MCU U1, regulators, passives, SDI pads). Drawn with the pcb-route skill's Board helper, which checks
every track and via against pads, tracks, vias, holes and the edge while drawing ('! ...' lines) and chamfers
90 degree corners to short 45s. Coordinates: KiCad board frame (x right, y down, mm).

House rules (house_rules.yaml + the owner's):
  - orthogonal runs, 45 deg only as short transitions; no 90 deg corners; each net a tree (no loops)
  - tracks 0.2 signal / 0.3 power next to fine pitch / 0.5 power; vias 0.6/0.3 signal + GND, 0.8/0.4 power
  - In1 = GND plane; In2 = +3V3 plane with a +5V_IN island under the power corner (J2 / SY6280 / LDO input);
    GND pours on F.Cu and B.Cu

Lanes (bottom face, around the MCU):
  - MCU top row, going up under the USB-A: RX (to the opto's via), LED (x -1.4), DIO (x -1.0), D- (x -0.4),
    D+ (x 0.6); D-/D+ change layer under the front of J1's pads
  - MCU left column, going down to the THRU switch: RX (x -4.3, outer), TX (x -3.85), OUT_SEL (x -3.4, inner)
  - MCU bottom row: VBUS_EN (pin 8) down then right to the SY6280
  - VBUS_HOST: SY6280 OUT up between J2's shell legs, via, then on F.Cu under the USB-A to J1's VBUS pad
Run:  python3 tools/gen_pcb.py && python3 tools/route.py
"""
import pathlib, sys
sys.path.insert(0, '/home/wero1414/hardware-design-skill/lib')
from hwkit.route import Board  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
PCB = HERE / 'fm1-midi-dongle.kicad_pcb'
SIG, PMIN, PWR = 'signal', 'power_min', 'power'

b = Board(PCB, PCB, fresh=True, origin='kicad')
P = b.pad

# ================================================================ planes
OUTLINE = [(-10, -1.97), (10, -1.97), (10, 35.7), (-10, 35.7)]
b.plane('GND', 'In1', OUTLINE)
b.plane('+3V3', 'In2', OUTLINE)
b.plane('+5V_IN', 'In2', [(1.5, 11.0), (5.0, 11.0), (5.0, 8.9), (9.6, 8.9), (9.6, 21.2), (1.5, 21.2)], priority=1)

# ================================================================ MCU exposed pad: 2 x 2 GND vias
for x in (-1.32, 0.08):
    for y in (11.7, 13.1):
        b.via('GND', x, y, 'signal')

# ================================================================ USB pair: up on B.Cu under the USB-A, via under the
# front of J1's D-/D+ pads (D- left, D+ right: the bottom-mounted MCU already has them in that order)
b.path('USB_DM', 'B', SIG, (-0.2, 10.05), (-0.2, 8.6), (-0.4, 8.4), (-0.4, 5.3)); b.via('USB_DM', -0.4, 5.3)
b.path('USB_DM', 'F', SIG, (-0.4, 5.3), (-0.4, 6.2))
b.path('USB_DP', 'B', SIG, (0.2, 10.05), (0.2, 8.6), (0.6, 8.2), (0.6, 5.3)); b.via('USB_DP', 0.6, 5.3)
b.path('USB_DP', 'F', SIG, (0.6, 5.3), (0.6, 6.2))

# ================================================================ SDI DIO and LED: up under the USB-A beside the pair
b.path('SDI_DIO', 'B', SIG, (-0.6, 10.05), (-0.6, 9.8), (-1.0, 9.4), (-1.0, 0.6))
b.path('LED', 'B', SIG, (-1.4, 10.05), (-1.4, 1.75), (-8.0, 1.75), (-8.0, 7.3), (-8.6, 7.3)); b.via('LED', -8.6, 7.3)
b.path('LED', 'F', SIG, (-8.6, 7.3), (-8.6, 6.42))
b.path('LED_K', 'F', SIG, (-8.6, 4.78), (-8.6, 2.89))

# ================================================================ MIDI RX: opto pin 4 (top) -> via -> MCU pin 22, R10, and the
# outer lane down to the THRU switch (top face, beside R7)
b.via('MIDI_RX', -2.3, 9.0)
b.path('MIDI_RX', 'F', SIG, (-2.3, 9.0), (-2.3, 9.7))
b.path('MIDI_RX', 'B', SIG, (-1.8, 10.05), (-1.8, 9.5), (-2.3, 9.0), (-3.6, 9.0))
b.path('MIDI_RX', 'B', SIG, (-4.0, 9.0), (-4.3, 9.3), (-4.3, 22.9), (-2.3, 22.9)); b.via('MIDI_RX', -2.3, 22.9)
b.path('MIDI_RX', 'F', SIG, (-2.3, 22.9), (-1.5, 22.9))

# ================================================================ MIDI TX and OUT_SEL: MCU left column -> lanes down -> vias -> U5
b.path('MIDI_TX', 'B', SIG, (-2.6, 11.2), (-3.85, 11.2), (-3.85, 21.3), (-2.3, 21.3)); b.via('MIDI_TX', -2.3, 21.3)
b.path('MIDI_TX', 'F', SIG, (-2.3, 21.3), (-2.1, 21.5), (-1.5, 21.5))
b.path('OUT_SEL', 'B', SIG, (-2.6, 11.6), (-3.4, 11.6), (-3.4, 20.6), (1.4, 20.6)); b.via('OUT_SEL', 1.4, 20.6)
b.path('OUT_SEL', 'B', SIG, (0.82, 20.6), (0.82, 19.9))                       # R13 pull-down
b.path('OUT_SEL', 'F', SIG, (1.4, 20.6), (1.4, 21.5), (0.6, 21.5))

# ================================================================ THRU switch U5 (top) -> R7 -> MIDI OUT tip
b.path('MIDI_OUT_DATA', 'F', SIG, (0.9, 22.8), (1.2, 22.85), (2.5, 22.85))
b.path('+3V3', 'F', PMIN, (0.9, 22.15), (1.65, 22.15)); b.via('+3V3', 1.65, 22.15)
b.path('GND', 'F', PMIN, (-1.5, 22.1), (-2.3, 22.1)); b.via('GND', -2.3, 22.1, 'signal')

# ================================================================ VBUS_EN: MCU pin 8 down, right to the SY6280 EN; R12 below
b.path('VBUS_EN', 'B', SIG, (0.6, 14.4), (0.6, 15.95), (4.9, 15.95))
b.path('VBUS_EN', 'B', SIG, (3.6, 15.95), (3.6, 16.57))

# ================================================================ VBUS_HOST: SY6280 OUT up between J2's shell legs, via, F.Cu
# under the USB-A to J1's VBUS pad; C3 under the pad on B.Cu
b.path('VBUS_HOST', 'B', PWR, (7.55, 14.05), (7.55, 13.6), (7.1, 13.15), (6.4, 13.15), (6.4, 10.75))
b.via('VBUS_HOST', 6.4, 10.75)
b.path('VBUS_HOST', 'F', PWR, (6.4, 10.75), (6.4, 10.2), (5.9, 9.7), (5.2, 9.7), (5.2, 3.5), (-3.5, 3.5), (-3.5, 6.2))
b.via('VBUS_HOST', -3.5, 5.5)
b.path('VBUS_HOST', 'B', PWR, (-3.5, 5.5), (-3.5, 4.38))

# ================================================================ ISET
b.path('ISET', 'B', SIG, (7.55, 15.95), (9.0, 15.95), (9.0, 16.3))

# ================================================================ +5V_IN: J2's two VBUS pad groups and the SY6280 / LDO
# inputs drop into the In2 island
b.path('+5V_IN', 'F', PMIN, (2.6, 13.45), (2.3, 13.45)); b.via('+5V_IN', 2.3, 13.45, 'signal')
b.path('+5V_IN', 'F', PWR, (2.6, 18.35), (1.95, 18.35)); b.via('+5V_IN', 1.95, 18.35)
b.path('+5V_IN', 'B', PWR, (3.6, 13.9), (5.25, 13.9))                                       # C1 -> U3 IN (under J2's peg)
b.path('+5V_IN', 'B', PMIN, (2.3, 13.45), (3.3, 13.45))                                    # island via -> C1
b.path('+5V_IN', 'B', PWR, (8.74, 8.85), (8.74, 9.95)); b.via('+5V_IN', 8.74, 9.95)

# ================================================================ CC pull-downs (top)
b.path('CC1_IN', 'F', SIG, (2.6, 17.15), (0.8, 17.15), (0.35, 16.7))
b.path('CC2_IN', 'F', SIG, (2.6, 14.15), (0.8, 14.15), (0.35, 14.6))

# ================================================================ +3V3: one power via per cluster into In2
b.path('+3V3', 'B', SIG, (1.4, 11.6), (2.1, 11.6), (2.1, 11.3))                              # VDD (0.2 neck between the 0.4 mm pitch pins)
b.path('+3V3', 'B', PMIN, (2.1, 11.3), (2.1, 9.2), (1.68, 9.2))      # -> C4
b.path('+3V3', 'B', PMIN, (1.68, 8.72), (1.68, 8.3), (4.9, 8.3), (4.9, 7.83))     # C4 -> C2
b.path('+3V3', 'B', PMIN, (4.9, 7.83), (6.26, 7.83))                            # C2 -> U2 VO
b.via('+3V3', 2.6, 10.65); b.path('+3V3', 'B', PMIN, (2.1, 10.65), (2.6, 10.65))
b.path('+3V3', 'B', PMIN, (-5.42, 8.8), (-6.2, 8.8), (-6.2, 8.3)); b.via('+3V3', -6.2, 8.3)      # R10
b.via('+3V3', -7.9, 11.95)                                                       # U4 VCC + C5
b.path('+3V3', 'F', PMIN, (-7.94, 11.0), (-7.94, 11.95))
b.path('+3V3', 'B', PMIN, (-7.9, 11.95), (-7.9, 12.82))
b.path('+3V3', 'B', PWR, (1.1, 0.4), (2.5, 0.4)); b.via('+3V3', 2.5, 0.4)          # TP1
b.path('+3V3', 'F', PWR, (7.42, 22.4), (8.45, 22.4)); b.via('+3V3', 8.45, 22.4)    # R8

# ================================================================ MIDI IN (opto, top)
b.path('MIDI_IN_TIP', 'F', SIG, (-8.4, 22.73), (-8.4, 25.3))
b.path('OPTO_A', 'F', SIG, (-8.4, 21.07), (-8.4, 20.3), (-7.94, 19.84))
b.path('OPTO_A', 'F', SIG, (-6.65, 21.4), (-6.65, 21.0), (-7.4, 20.25))
b.path('MIDI_IN_RING', 'F', SIG, (-5.4, 20.4), (-5.4, 21.2), (-3.35, 21.2), (-3.35, 21.5))
b.path('MIDI_IN_RING', 'F', SIG, (-3.35, 22.2), (-3.35, 23.2), (-5.6, 23.2), (-6.2, 23.8), (-6.2, 28.9),
       (-6.75, 29.45), (-8.0, 29.45))

# ================================================================ MIDI OUT jack (top)
b.path('MIDI_TIP_OUT', 'F', SIG, (4.33, 22.4), (4.33, 23.35), (2.0, 23.35), (2.0, 25.3))
b.path('MIDI_RING_OUT', 'F', SIG, (5.78, 22.4), (5.78, 25.6), (3.9, 25.6), (3.9, 28.9), (3.35, 29.45), (2.0, 29.45))

# ================================================================ GND: a stitching via at every GND pad cluster
GND_VIAS = [   # (via, pad link start) per GND pad cluster
    ((-8.6, 0.3), (-8.6, 1.31)),         # D2 (top)
    ((-4.3, -0.9), (-4.3, 0.4)),         # TP3
    ((-2.5, 2.6), (-3.1, 2.6)),        # C3
    ((3.4, 10.1), (3.4, 9.68)),          # C4
    ((4.9, 10.4), (4.9, 9.82)),          # C2
    ((8.6, 15.0), (7.55, 15.0)),         # U3 pin 2 + R4
    ((2.6, 19.2), (3.6, 19.2)),           # R12 (and J2's A1 / B12 on top)
    ((1.95, 15.18), (3.13, 15.18)),       # C1
    ((-1.2, 18.95), (-1.2, 19.6)),
    ((2.4, 12.6), (2.7, 12.6)),          # J2 A12 / B1 (top)        # R13
    ((-5.4, 11.95), (-5.4, 11.3)),       # U4 pin 5 (top, under its body)
    ((-7.9, 15.1), (-7.9, 14.6)),        # C5
    ((-0.5, 13.22), (-0.1, 13.22)),      # R3 (top)
    ((-0.5, 18.07), (-0.1, 18.07)),      # R2 (top)
    ((8.0, 23.4), (8.0, 23.7)),          # J3 sleeve 1 (top)
    ((2.0, 33.4), (2.0, 33.1)),          # J3 sleeve 2 (top)
]
TOP_PADS = {(2.7, 12.6), (-8.6, 1.31), (-5.4, 11.3), (-0.1, 13.22), (-0.1, 18.07), (8.0, 23.7), (2.0, 33.1)}
b.path('GND', 'B', PMIN, (3.6, 18.6), (3.6, 19.2))                                  # R12 -> its via
b.via('GND', 7.3, 10.6, 'signal'); b.path('GND', 'B', PMIN, (6.79, 10.0), (7.3, 10.0), (7.3, 10.6))   # U2 -> its via
for v, pad in GND_VIAS:
    b.via('GND', *v, 'signal')
    b.path('GND', 'F' if pad in TOP_PADS else 'B', PMIN, pad, v)

for ref, num in (('D2', '1'), ('J1', '5'), ('J1', '6'), ('J1', '7'), ('J1', '8'),
                 ('J2', 'A12'), ('J2', 'B1'), ('R12', '2'), ('U3', '2')):
    b.solid(ref, num)
b.pour('GND', ['F', 'B'])
b.save()
