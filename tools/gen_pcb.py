#!/usr/bin/env python3
"""Floorplan the FM-1 MIDI dongle PCB with KiCad's pcbnew module.

Priorities, in order (IPC-2221/2222 practice):
 1. USB differential pair: MCU directly under the plug's D+/D- pads, pins 26/27 facing them, straight traces on
    F.Cu over the unbroken GND plane (In1.Cu). No vias, no layer change.
 2. Power: the plug's VBUS/GND pads exist on BOTH faces of the tongue, so the VBUS switch sits on the back and
    feeds the back-face pads directly; the receptacle's VBUS is 2 mm away. LDO on top next to the MCU VDD pin.
 3. Serial MIDI: TX straight down the top to the right jack; isolated RX chain on the back under the jacks.
 4. GND return: In1 = GND plane, In2 = GND plane (power runs as short traces on the outer layers), so every
    trace on either outer layer references an adjacent solid ground. GND vias at every GND pad.
 5. Mechanics: 10 mm jack pitch so two moulded TRS plugs (up to ~9 mm bodies) fit side by side; the plug
    housing is off-board; nothing within the 1.5 mm the plug's rear clamps; the receptacle cable comes out of
    the right side (its plug would collide with the TRS plugs if it shared the far end).

Board frame: x right, y down (KiCad). Plug J1 at the origin, tongue tip at the top edge (y = -1.97).
Run: python3 tools/gen_pcb.py ; then kicad-cli pcb drc fm1-midi-dongle.kicad_pcb --severity-all
"""
import math, pathlib, subprocess, sys, xml.etree.ElementTree as ET
import pcbnew
from pcbnew import VECTOR2I_MM as MM, FromMM, ToMM

HERE = pathlib.Path(__file__).resolve().parent.parent
PROJECT = 'fm1-midi-dongle'
KICAD_FP = pathlib.Path('/usr/share/kicad/footprints')
sys.path.insert(0, str(HERE / 'tools'))
from gen_sch import ROOT_UUID  # noqa: E402

# ---------------------------------------------------------------- the floorplan (mm)
W = 20.0                       # 10 mm jack pitch (two moulded TRS plugs) + 9 mm jack pad span + 0.5 mm margins
Y_TOP = -1.97                  # plug tongue tip
YJ = 16.7                      # jack centres: the receptacle's shield pins (y 11.2) must stay clear of the jack bodies
Y_BOT = YJ + 7.3               # jack body front flush with the edge, 2.1 mm nose outside
J2_Y = 6.9
J2_OVERHANG = 1.0
T, B = 'F.Cu', 'B.Cu'
AUTO = None                    # rotation chosen by pad goals (see GOALS)

PLACE = {
    # ref: (x, y, rotation, side)
    'J1': (0.0, 0.0, 180, T),        # USB-C plug to the FM-1, tongue at the top edge
    'J3': (5.0, YJ, 180, T),         # MIDI OUT jack, nose at the bottom edge (right)
    'J4': (-5.0, YJ, 180, T),        # MIDI IN jack (left)
    'J2': (AUTO, J2_Y, AUTO, B),     # power receptacle, back, opening on the right edge
    # ---- top
    'U1': (AUTO, 4.6, AUTO, T),      # CH32X035: pins 27/26 straight under the plug's D+/D- pads
    'C4': (-2.6, 3.8, 90, T),        # VDD 100 nF beside pin 2
    'U2': (-5.2, 3.6, AUTO, T),      # XC6206: VO toward C4 / pin 2, VI toward the 5 V via on the left
    'C1': (-8.0, 3.2, 90, T),        # 5 V 1 µF at the LDO input
    'C2': (-5.0, 6.0, 0, T),         # 3V3 1 µF at the LDO output
    'R1': (-8.0, 0.6, 0, T),         # CC Rp 56k (A5 is top-face only)
    'R5': (8.4, 4.4, 90, T),         # D- pull-down, DNP
    'R6': (8.4, 7.6, 90, T),         # D+ pull-down, DNP
    'R7': (3.9, 7.8, 90, T),         # MIDI OUT tip 10 Ω: TX pin -> R7 -> J3 tip, all on top
    'R8': (5.4, 10.2, 90, T),        # MIDI OUT ring 33 Ω from 3V3
    'R11': (-3.2, 7.8, 0, T),        # LED 1k
    'D2': (-3.2, 9.8, 0, T),         # LED
    'TP1': (-8.4, 6.2, 0, T),        # 3V3
    'TP2': (-8.4, 8.9, 0, T),        # DIO
    'TP3': (0.6, 8.8, 0, T),         # GND, top centre
    # ---- back
    'U3': (-0.6, 3.6, AUTO, B),      # SY6280: OUT to the plug's back-face VBUS pad, IN to the receptacle VBUS
    'C3': (-3.4, 3.4, 90, B),        # VBUS_FM1 1 µF
    'R4': (-3.4, 6.6, 90, B),        # ISET 6.8k
    'R12': (-5.6, 3.4, 90, B),       # EN pull-down 100k
    'R2': (-1.0, 7.6, 90, B),        # CC1 5.1k next to the receptacle CC pads
    'R3': (-1.0, 10.8, 90, B),       # CC2 5.1k
    'U4': (0.0, 18.0, AUTO, B),      # H11L1SM under the jacks, LED pins toward the MIDI IN jack
    'R9': (-7.6, 15.0, 90, B),       # MIDI IN 220 Ω
    'D1': (-7.6, 19.0, 90, B),       # 1N4148W
    'R10': (7.0, 14.0, 90, B),       # MIDI_RX pull-up 10k
    'C5': (7.0, 17.0, 90, B),        # opto VCC 100 nF
}
DNP = {'R5', 'R6'}
# pad -> target point (board mm); the rotation minimising the summed distances wins
GOALS = {
    'U1': {'27': (-0.25, -0.03), '26': (0.25, -0.03)},            # D+ (A6) left, D- (A7) right after J1 rot 180
    'U3': {'1': (1.25, -0.03), '5': (2.8, 4.8)},                  # OUT -> B4 VBUS pad, IN -> receptacle VBUS
    'U2': {'2': (-2.6, 3.0), '3': (-8.0, 3.2)},                   # VO -> C4, VI -> C1 / 5 V via
    'U4': {'1': (-8.0, 13.75), '2': (-8.0, 17.75), '4': (2.6, 3.4)},  # LED pins toward J4's tip/ring, output up
}
ANGLES = {'U3': (0, 180), 'U4': (0, 180)}   # pad rows must stay horizontal (jack pegs / receptacle beside)
HOLE_CLEAR = 0.25
PAD_CLEAR = 0.3                # want at least this between pad groups of different parts


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
        if n.get('name').startswith('unconnected-'):
            continue
        nets[n.get('name')] = [(x.get('ref'), x.get('pin')) for x in n.findall('node')]
    return comps, nets


def load_fp(fpid):
    lib, name = fpid.split(':', 1)
    path = HERE / 'fm1_dongle.pretty' if lib == 'fm1_dongle' else KICAD_FP / f'{lib}.pretty'
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f'footprint not found: {fpid}')
    return fp


def pad_pos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            return ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)


def orient(fp, x, y, goals, angles=(0, 90, 180, 270)):
    best = None
    for ang in angles:
        fp.SetOrientationDegrees(ang); fp.SetPosition(MM(x, y))
        cost = sum(math.dist(pad_pos(fp, n), t) for n, t in goals.items())
        if best is None or cost < best[0]:
            best = (cost, ang)
    fp.SetOrientationDegrees(best[1]); fp.SetPosition(MM(x, y))
    return best[1]


def bbox_of(items):
    xs, ys = [], []
    for it in items:
        bb = it.GetBoundingBox()
        xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]; ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def overlap(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def main():
    comps, nets = run_netlist()
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    b.SetLayerName(pcbnew.In1_Cu, 'GND1')
    b.SetLayerName(pcbnew.In2_Cu, 'GND2')
    ds = b.GetDesignSettings()
    ds.m_MinClearance = FromMM(0.127); ds.m_TrackMinWidth = FromMM(0.127)
    ds.m_ViasMinSize = FromMM(0.45); ds.m_MinThroughDrill = FromMM(0.20)
    ds.m_CopperEdgeClearance = FromMM(0.3); ds.m_HoleClearance = FromMM(HOLE_CLEAR)
    ds.SetBoardThickness(FromMM(0.8))
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(FromMM(0.15)); nc.SetTrackWidth(FromMM(0.2))
    nc.SetViaDiameter(FromMM(0.45)); nc.SetViaDrill(FromMM(0.2))

    netitems = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); netitems[name] = ni
    pad_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    fps, side_of = {}, {}
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
        if ref not in PLACE:
            raise SystemExit(f'{ref} has no placement')
        x, y, rot, side = PLACE[ref]
        side_of[ref] = side
        if side == B:
            fp.Flip(fp.GetPosition(), False)
        if ref == 'J2':
            # KiCad's HRO footprint (exact part) + the EasyEDA 3D model, whose origin is 1.42 mm toward the rear
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL(); m.m_Filename = '${KIPRJMOD}/fm1_dongle.3dshapes/USB-C_SMD-TYPE-C-31-M-12_1.wrl'
            m.m_Offset = pcbnew.VECTOR3D(0, 1.42, 0); m.m_Rotation = pcbnew.VECTOR3D(0, 0, 180); m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
            fp.Models().push_back(m)
            best = None
            for ang in (90, 270):                     # opening to the right: solder row toward the board centre
                fp.SetOrientationDegrees(ang); fp.SetPosition(MM(0, y))
                px = pad_pos(fp, 'A5')[0]
                if best is None or px < best[0]:
                    best = (px, ang)
            fp.SetOrientationDegrees(best[1]); fp.SetPosition(MM(0, y))
            front = ToMM(fp.GetBoundingBox(False, False).GetRight())
            fp.SetPosition(MM((W / 2 + J2_OVERHANG) - front, y))
        elif ref in GOALS:
            orient(fp, x if x is not None else 0.0, y, GOALS[ref], ANGLES.get(ref, (0, 90, 180, 270)))
            if ref == 'U1':                           # centre the pair under the plug pads
                mid = (pad_pos(fp, '26')[0] + pad_pos(fp, '27')[0]) / 2
                fp.SetPosition(MM(-mid, y))
        else:
            fp.SetOrientationDegrees(rot); fp.SetPosition(MM(x, y))
        for p in fp.Pads():
            n = pad_net.get((ref, p.GetNumber()))
            if n:
                p.SetNet(netitems[n])
        fps[ref] = fp

    # ---- outline: tongue tip with latch notches (plug drawing), straight sides, rounded far corners
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); b.Add(s)
    def arc(x1, y1, xm, ym, x2, y2):
        a = pcbnew.PCB_SHAPE(b); a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(MM(x1, y1), MM(xm, ym), MM(x2, y2)); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(FromMM(0.1)); b.Add(a)
    r, hw = 1.0, W / 2
    tip, sh, rr = -1.97, -1.07, 0.25
    k = rr * (1 - 0.7071)
    seg(hw, Y_TOP, 4.45, Y_TOP); seg(4.45, Y_TOP, 4.45, sh); seg(4.45, sh, 3.05, sh)
    seg(3.05, sh, 3.05, tip + rr); arc(3.05, tip + rr, 3.05 - k, tip + k, 3.05 - rr, tip)
    seg(3.05 - rr, tip, -3.05 + rr, tip)
    arc(-3.05 + rr, tip, -3.05 + k, tip + k, -3.05, tip + rr); seg(-3.05, tip + rr, -3.05, sh)
    seg(-3.05, sh, -4.45, sh); seg(-4.45, sh, -4.45, Y_TOP); seg(-4.45, Y_TOP, -hw, Y_TOP)
    seg(hw, Y_TOP, hw, Y_BOT - r)
    arc(hw, Y_BOT - r, hw - r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), hw - r, Y_BOT)
    seg(hw - r, Y_BOT, -hw + r, Y_BOT)
    arc(-hw + r, Y_BOT, -hw + r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), -hw, Y_BOT - r)
    seg(-hw, Y_BOT - r, -hw, Y_TOP)

    # ---- two inner GND planes: every outer-layer trace sees an adjacent solid reference
    for layer, name in ((pcbnew.In1_Cu, 'GND plane 1'), (pcbnew.In2_Cu, 'GND plane 2')):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(netitems['GND']); z.SetZoneName(name)
        ol = z.Outline(); ol.NewOutline()
        for x, y in [(-hw, Y_TOP), (hw, Y_TOP), (hw, Y_BOT), (-hw, Y_BOT)]:
            ol.Append(MM(x, y))
        z.SetMinThickness(FromMM(0.15)); z.SetLocalClearance(FromMM(0.2))
        b.Add(z)

    # ---- keep-out where the plug's rear clamps the board (both faces)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetDoNotAllowFootprints(True)
        for setter in ('SetDoNotAllowZoneFills', 'SetDoNotAllowCopperPour', 'SetDoNotAllowTracks', 'SetDoNotAllowVias', 'SetDoNotAllowPads'):
            if hasattr(kz, setter): getattr(kz, setter)(False)
        kz.SetLayer(layer); kz.SetZoneName('plug clamp, no parts')
        o = kz.Outline(); o.NewOutline()
        for x, y in [(-5.0, -0.8), (5.0, -0.8), (5.0, 1.5), (-5.0, 1.5)]:
            o.Append(MM(x, y))
        b.Add(kz)

    out = HERE / f'{PROJECT}.kicad_pcb'
    b.Save(str(out))
    print(f'wrote {out.name}: {len(fps)} footprints, {len(nets)} nets, board {W} x {Y_BOT - Y_TOP:.1f} mm')

    # ---- placement self-check: pad groups vs pad groups and bodies on the same side, holes vs copper
    print('orientations:', {r: fps[r].GetOrientationDegrees() for r in ('U1', 'U2', 'U3', 'U4', 'J2')})
    for ref in ('U1', 'U3'):
        print(f'  {ref} pads 26/27 or 1/5:', {n: tuple(round(v, 2) for v in pad_pos(fps[ref], n)) for n in (('26', '27') if ref == 'U1' else ('1', '5'))})
    groups = {}
    for ref, fp in fps.items():
        pads = [p for p in fp.Pads() if p.GetNumber()]
        groups[ref] = (bbox_of(pads), bbox_of([fp]) if False else None, side_of[ref])
    refs = sorted(fps)
    issues = 0
    for i, a in enumerate(refs):
        for bref in refs[i + 1:]:
            if side_of[a] != side_of[bref] or 'J1' in (a, bref):
                continue
            pa, _, _ = groups[a]; pb, _, _ = groups[bref]
            if pa and pb and overlap(pa, pb, PAD_CLEAR):
                issues += 1
                print(f'  PAD SPACING < {PAD_CLEAR}: {a} vs {bref}')
    holes = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), ToMM(p.GetDrillSize().x) / 2, ref)
             for ref, fp in fps.items() for p in fp.Pads() if p.GetDrillSize().x > 0]
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0 or not p.GetNumber():
                continue
            bbp = p.GetBoundingBox()
            px0, py0, px1, py1 = ToMM(bbp.GetLeft()), ToMM(bbp.GetTop()), ToMM(bbp.GetRight()), ToMM(bbp.GetBottom())
            for hx, hy, hr, href in holes:
                if href == ref:
                    continue
                dx = max(px0 - hx, 0, hx - px1); dy = max(py0 - hy, 0, hy - py1)
                if math.hypot(dx, dy) < hr + HOLE_CLEAR:
                    issues += 1
                    print(f'  HOLE too close: {href} hole at ({hx:.2f},{hy:.2f}) vs {ref} pad {p.GetNumber()}')
    print('placement issues:', issues)


if __name__ == '__main__':
    main()
