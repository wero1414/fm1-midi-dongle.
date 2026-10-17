"""ncroute config for the FM-1 MIDI dongle (KAT router, kicad-pcb-autorouter-workflow skill).

4-layer, 0.8 mm: F.Cu signals / In1 GND / In2 GND / B.Cu signals + power.  GND comes from the planes
(plane_via.py), everything else is routed on the outer layers only.
"""
from cfg_template import *          # noqa  (kat/ is on ncroute's path)
import pcbnew
from shapely.geometry import box

LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
ALL_CU = LAYERS
RES = 0.025                          # 0.4 mm QFN pitch escapes need the fine grid
ORIGIN = (-9.975, -1.945)             # ABSOLUTE grid origin (board top-left + half a cell), not an offset
EDGE = 0.30
VIA = (0.45, 0.20)                   # JLCPCB 4-layer minimum via
VIA_COST, B45, B90 = 30.0, 3.0, 15.0
DEFAULT_CLR = 0.15
CLASS_CLR = {'Default': 0.15}
PLANE_NETS = {'GND', '+3V3'}
PLANE_STUBS = True                   # GND pads that got no via: short stub to the nearest GND via/copper
STUB_R = 4.0
STUB_W = 0.2

POWER = ('+5V_IN', 'VBUS_FM1')
USB = ('USB_DP', 'USB_DM')
BACK_FIRST = ('+5V_IN', 'VBUS_FM1', 'CC1_IN', 'CC2_IN', 'ISET', 'VBUS_EN', 'MIDI_IN_TIP', 'MIDI_IN_RING', 'OPTO_A')
TOP_FIRST = ('MIDI_TX', 'MIDI_TIP_OUT', 'MIDI_RING_OUT', 'CC_FM1', 'LED', 'LED_K', 'SDI_DIO')


def width(net, cls):
    s = short(net)
    if s in ('+5V_IN', 'VBUS_FM1'):
        return 0.25                  # the USB-C pads are 0.3 mm wide; < 0.5 A on this board
    if s == '+3V3':
        return 0.20                  # lands on a 0.2 mm QFN pin
    return 0.15


def layer_cost(net):
    s = short(net)
    if s in USB:
        return [1.0, 999.0]          # the pair stays on F.Cu over the GND plane, straight from the plug pads
    if s in BACK_FIRST:
        return [3.0, 1.0]
    if s in TOP_FIRST:
        return [1.0, 3.0]
    return [1.0, 1.0]


def via_cost(net):
    s = short(net)
    return 999.0 if s in USB else (60.0 if s in POWER else VIA_COST)


def pair_gap(net):
    return 0.15                      # 0.2 mm / 0.15 mm on 0.8 mm 4-layer: close enough to 90 ohm for USB FS


PAIR_HARD = False


def PAIR_FAT(net):
    return False                     # 0.4 mm pads at one end, 0.5 mm at the other: route as two coupled-enough singles


from shapely.geometry import Point
NPTH = [(4.22, 4.01, 0.325), (4.22, 9.79, 0.325), (5.0, 15.25, 0.6), (-5.0, 15.25, 0.6), (5.0, 22.25, 0.6), (-5.0, 22.25, 0.6)]
HOLE_CLR = 0.25


def via_keepouts(b):
    """no vias where the plug's rear clamps the board (both faces); hole-to-hole room around the NPTH holes"""
    return [box(-5.0, -2.0, 5.0, 1.6)] + [Point(x, y).buffer(r + HOLE_CLR + VIA[0] / 2) for x, y, r in NPTH]


def track_keepouts(b):
    """hole-to-copper clearance (0.25) around the unplated holes, on both routing layers"""
    return [(li, Point(x, y).buffer(r + HOLE_CLR + 0.1)) for li in range(len(LAYERS)) for x, y, r in NPTH]
