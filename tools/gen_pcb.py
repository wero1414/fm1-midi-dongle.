#!/usr/bin/env python3
"""Floorplan the FM-1 MIDI dongle PCB with KiCad's pcbnew module.

Reads the netlist from the schematic (kicad-cli), loads the exact footprints, places every part from the
PLACE table below, draws the outline (the plug's own notched tongue edge completes the top edge), sets
JLCPCB 4-layer rules and a GND plane on In1.Cu. Routing is done in KiCad afterwards.

Board frame: x to the right, y downward (KiCad). The USB-C plug J1 sits at the origin, tongue tip at the
top edge (y = -1.98), the plug housing hangs off the board. Jacks at the bottom edge, noses overhanging.

Run:  python3 tools/gen_pcb.py       then: kicad-cli pcb drc fm1-midi-dongle.kicad_pcb --severity-all
"""
import pathlib, subprocess, sys, xml.etree.ElementTree as ET
import pcbnew
from pcbnew import VECTOR2I_MM as MM, FromMM

HERE = pathlib.Path(__file__).resolve().parent.parent
PROJECT = 'fm1-midi-dongle'
KICAD_FP = pathlib.Path('/usr/share/kicad/footprints')
sys.path.insert(0, str(HERE / 'tools'))
from gen_sch import ROOT_UUID  # noqa: E402  (the schematic's root sheet uuid, for symbol<->footprint links)

# ---------------------------------------------------------------- the floorplan (mm, degrees, side)
W = 18.9                       # two jacks at 9.3 mm pitch: each is 9 mm across its pads, 0.3 mm between them, 0.3 mm to the edges
Y_TOP = -1.97                  # plug tongue tip (datasheet: pads 1.3 mm from the tip; notches for the shell latches)
YJ = 16.7                      # jack centres: the receptacle's shield pins (y 11.2) must clear the jack bodies
Y_BOT = YJ + 7.3               # bottom edge: jack body front flush, 2.1 mm nose outside
J2_OVERHANG = 1.0              # receptacle front past the right edge
T, B = 'F.Cu', 'B.Cu'

PLACE = {
    # ref: (x, y, rotation, side)
    'J1': (0.0, 0.0, 180, T),          # USB-C plug to the FM-1, tongue at the top edge
    'J3': (4.65, YJ, 180, T),           # MIDI OUT jack, nose at the bottom edge (right)
    'J4': (-4.65, YJ, 180, T),          # MIDI IN jack (left)
    'J2': (None, 6.9, None, B),        # power USB-C, bottom right, opening to the right (x and angle computed)
    # top, row A (y 2.8): next to the plug pads
    'R6': (0.6, 2.8, 0, T),            # D+ pull-down (DNP)
    'R5': (-2.6, 2.8, 0, T),           # D- pull-down (DNP)
    'R1': (-7.0, 2.7, 0, T),           # CC Rp 56k
    # top, row B (y ~5): VBUS switch
    'U3': (-6.2, 5.1, 0, T),           # SY6280
    'C3': (-3.8, 5.2, 90, T),          # VBUS_FM1 1 µF
    'R4': (-1.2, 5.3, 90, T),          # ISET 6.8k
    'R12': (1.2, 5.3, 90, T),          # EN pull-down 100k
    # top, row C (y 8.4): LDO
    'U2': (-5.8, 8.4, 0, T),           # XC6206
    'C2': (-2.2, 8.4, 90, T),          # 3V3 1 µF
    'C1': (-0.4, 8.4, 90, T),          # 5 V 1 µF
    'D2': (0.0, 10.7, 0, T),           # LED, top centre between the jack rears
    # top, right: MCU in the hole-free band of the receptacle underneath
    'U1': (5.7, 7.3, 0, T),            # CH32X035, USB pins 26/27 on its left edge toward the plug
    'C4': (5.7, 4.3, 0, T),            # VDD 100 nF, above the MCU
    # bottom: receptacle (right), optocoupler (left), passives in columns under the jacks (pegs at x = +-4.65)
    'U4': (-4.7, 7.1, 0, B),           # H11L1SM
    'TP1': (-7.6, 14.0, 0, B),         # 3V3
    'TP2': (-7.6, 16.7, 0, B),         # DIO
    'TP3': (-7.6, 19.4, 0, B),         # GND
    'R9': (-2.4, 14.4, 90, B),         # MIDI IN 220 Ω
    'R10': (-2.4, 17.5, 90, B),        # MIDI_RX pull-up 10k
    'C5': (-2.4, 20.6, 90, B),         # opto VCC 100 nF
    'R2': (0.0, 14.0, 90, B),          # CC1 5.1k
    'R3': (0.0, 17.1, 90, B),          # CC2 5.1k
    'R7': (2.4, 14.0, 90, B),          # MIDI OUT tip 10 Ω
    'R8': (2.4, 17.1, 90, B),          # MIDI OUT ring 33 Ω
    'R11': (7.6, 14.0, 90, B),         # LED 1k
    'D1': (7.6, 18.5, 90, B),          # 1N4148W
}
DNP = {'R5', 'R6'}


def run_netlist():
    out = HERE / 'production' / 'netlist.xml'
    out.parent.mkdir(exist_ok=True)
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    str(HERE / f'{PROJECT}.kicad_sch'), '-o', str(out)], check=True, capture_output=True)
    root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        comps[c.get('ref')] = {'value': c.findtext('value'), 'fp': c.findtext('footprint') or '',
                               'tstamp': (c.findtext('tstamps') or '').split()[0] if c.findtext('tstamps') else ''}
    nets = {}
    for n in root.find('nets'):
        name = n.get('name')
        nodes = [(x.get('ref'), x.get('pin')) for x in n.findall('node')]
        if name.startswith('unconnected-'):
            continue
        nets[name] = nodes
    return comps, nets


def load_fp(fpid):
    lib, name = fpid.split(':', 1)
    path = HERE / 'fm1_dongle.pretty' if lib == 'fm1_dongle' else KICAD_FP / f'{lib}.pretty'
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f'footprint not found: {fpid}')
    return fp


def fab_extent(fp):
    """y range of the F.Fab drawing of a footprint, from its file (the swig iterator is broken here)"""
    import re
    lib, name = fp.GetFPIDAsString().split(':', 1)
    path = HERE / 'fm1_dongle.pretty' if lib == 'fm1_dongle' else KICAD_FP / f'{lib}.pretty'
    txt = (path / f'{name}.kicad_mod').read_text()
    ys = []
    for m in re.finditer(r'\(fp_(?:line|rect)\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*\(end\s+([-\d.]+)\s+([-\d.]+)\).*?\(layer\s+"F\.Fab"\)', txt, re.S):
        ys += [float(m.group(2)), float(m.group(4))]
    return (min(ys), max(ys)) if ys else (None, None)


def main():
    comps, nets = run_netlist()
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    b.SetLayerName(pcbnew.In1_Cu, 'GND')
    b.SetLayerName(pcbnew.In2_Cu, 'PWR')
    ds = b.GetDesignSettings()
    ds.m_MinClearance = FromMM(0.127)       # JLCPCB 4-layer: 0.09 mm min, keep margin
    ds.m_TrackMinWidth = FromMM(0.127)
    ds.m_ViasMinSize = FromMM(0.45)
    ds.m_MinThroughDrill = FromMM(0.20)
    ds.m_CopperEdgeClearance = FromMM(0.3)
    ds.m_HoleClearance = FromMM(0.25)
    ds.SetBoardThickness(FromMM(0.8))
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(FromMM(0.15)); nc.SetTrackWidth(FromMM(0.2))
    nc.SetViaDiameter(FromMM(0.45)); nc.SetViaDrill(FromMM(0.2))

    netitems = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); netitems[name] = ni
    pad_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    fps = {}
    spare_x = -8.0
    for ref, c in sorted(comps.items()):
        if not c['fp']:
            continue
        fp = load_fp(c['fp'])
        fp.SetReference(ref); fp.SetValue(c['value'])
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        if c['tstamp']:
            fp.SetPath(pcbnew.KIID_PATH(f'/{ROOT_UUID}/{c["tstamp"]}'))
        if ref in DNP:
            fp.SetDNP(True)
        b.Add(fp)
        x, y, rot, side = PLACE.get(ref, (spare_x, Y_BOT + 8, 0, T))
        if ref not in PLACE:
            spare_x += 3.0
        if side == B:
            fp.Flip(fp.GetPosition(), False)
        if ref == 'J2':
            # receptacle on the back, opening to the right: try both angles, keep the one with the
            # solder row (local y = -4.04) toward the board centre; then push the front to the edge
            best = None
            for ang in (90, 270):
                fp.SetOrientationDegrees(ang); fp.SetPosition(MM(0, y))
                xs = [pcbnew.ToMM(p.GetPosition().x) for p in fp.Pads() if p.GetNumber() in ('A5', 'B5')]
                if best is None or xs[0] < best[0]:
                    best = (xs[0], ang)
            fp.SetOrientationDegrees(best[1]); fp.SetPosition(MM(0, y))
            bb = fp.GetBoundingBox(False, False)
            # the courtyard's +x end is the connector front: put it at W/2 + overhang
            front = pcbnew.ToMM(bb.GetRight())
            x = (W / 2 + J2_OVERHANG) - front
            fp.SetPosition(MM(x, y))
        else:
            fp.SetOrientationDegrees(rot); fp.SetPosition(MM(x, y))
        for p in fp.Pads():
            n = pad_net.get((ref, p.GetNumber()))
            if n:
                p.SetNet(netitems[n])
        fps[ref] = fp

    # ---- outline. The plug footprint draws the notched tongue between x = -4.45 and 4.45 on Edge.Cuts.
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); b.Add(s)
    def arc(x1, y1, xm, ym, x2, y2):
        a = pcbnew.PCB_SHAPE(b); a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(MM(x1, y1), MM(xm, ym), MM(x2, y2)); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(FromMM(0.1)); b.Add(a)
    r = 1.0
    hw = W / 2
    tip, sh, rr = -1.97, -1.07, 0.25                 # tongue tip, latch-notch floor, tip corner radius
    k = rr * (1 - 0.7071)
    seg(hw, Y_TOP, 4.45, Y_TOP); seg(4.45, Y_TOP, 4.45, sh); seg(4.45, sh, 3.05, sh)     # right notch
    seg(3.05, sh, 3.05, tip + rr); arc(3.05, tip + rr, 3.05 - k, tip + k, 3.05 - rr, tip)
    seg(3.05 - rr, tip, -3.05 + rr, tip)                                                     # tongue tip
    arc(-3.05 + rr, tip, -3.05 + k, tip + k, -3.05, tip + rr); seg(-3.05, tip + rr, -3.05, sh)
    seg(-3.05, sh, -4.45, sh); seg(-4.45, sh, -4.45, Y_TOP); seg(-4.45, Y_TOP, -hw, Y_TOP)   # left notch
    seg(hw, Y_TOP, hw, Y_BOT - r)               # right side
    arc(hw, Y_BOT - r, hw - r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), hw - r, Y_BOT)
    seg(hw - r, Y_BOT, -hw + r, Y_BOT)          # bottom
    arc(-hw + r, Y_BOT, -hw + r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), -hw, Y_BOT - r)
    seg(-hw, Y_BOT - r, -hw, Y_TOP)             # left side

    # ---- GND plane on In1.Cu, whole board
    z = pcbnew.ZONE(b); z.SetLayer(pcbnew.In1_Cu); z.SetNet(netitems['GND']); z.SetZoneName('GND plane')
    ol = z.Outline(); ol.NewOutline()
    for x, y in [(-hw, Y_TOP), (hw, Y_TOP), (hw, Y_BOT), (-hw, Y_BOT)]:
        ol.Append(MM(x, y))
    z.SetMinThickness(FromMM(0.15)); z.SetLocalClearance(FromMM(0.2))
    b.Add(z)

    # ---- keep-out where the plug's rear clamps the board (both faces), so DRC flags anything placed there
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        k = pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowFootprints(True)
        for setter in ('SetDoNotAllowZoneFills', 'SetDoNotAllowCopperPour', 'SetDoNotAllowTracks', 'SetDoNotAllowVias', 'SetDoNotAllowPads'):
            if hasattr(k, setter): getattr(k, setter)(False)
        k.SetLayer(layer); k.SetZoneName('plug clamp, no parts')
        o = k.Outline(); o.NewOutline()
        for x, y in [(-5.0, -0.8), (5.0, -0.8), (5.0, 1.5), (-5.0, 1.5)]:
            o.Append(MM(x, y))
        b.Add(k)

    out = HERE / f'{PROJECT}.kicad_pcb'
    b.Save(str(out))
    print(f'wrote {out.name}: {len(fps)} footprints, {len(nets)} nets, board {W} x {Y_BOT - Y_TOP:.1f} mm')
    j2 = fps['J2']; bb = j2.GetBoundingBox(False, False)
    print(f"J2 at x={pcbnew.ToMM(j2.GetPosition().x):.2f} rot={j2.GetOrientationDegrees()} bbox x[{pcbnew.ToMM(bb.GetLeft()):.2f},{pcbnew.ToMM(bb.GetRight()):.2f}] y[{pcbnew.ToMM(bb.GetTop()):.2f},{pcbnew.ToMM(bb.GetBottom()):.2f}]")


if __name__ == '__main__':
    main()
