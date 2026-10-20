#!/usr/bin/env python3
"""Floorplan the FM-1 MIDI dongle PCB with KiCad's pcbnew module. v5: USB-A host receptacle J1 on the BOTTOM
face (mouth at the top edge), every other part on the top face.

Priorities, in order (IPC-2221/2222 practice):
 1. USB differential pair: J1's D+/D- pads sit on the back face right under the MCU, whose pins 27/26 face the
    top edge. One via per line just above the MCU, then straight down on B.Cu to the pads (D+ left, D- right, no
    crossing), over the unbroken GND plane (In1.Cu).
 2. Power on the left, because the MCU's VDD (2) and VBUS_EN (5) pins face left: SY6280 in the band freed by
    the old plug, LDO under it, power receptacle J2 below them with its mouth on the left edge. J1's VBUS pad is
    on the right (the bottom mount mirrors the pinout), so VBUS_HOST is the one net that crosses the board,
    above the D+/D- vias; the 10 uF host-port cap sits at that crossing.
    J1's four shell legs are through-hole and stick 0.65 mm out of the top face: no top part within 0.3 mm.
 3. Serial MIDI on the right, because TX 21 / RX 22 / DIO 25 face right and up: LinkE pads in the free corner
    beside the tongue, opto above the MIDI IN jack (whose tip/ring pads are at the board centre), MIDI OUT
    series resistors right above the MIDI OUT jack's tip/ring pads at the left edge.
 4. GND return: In1 = GND plane, In2 = 3V3 plane; B.Cu carries no parts, so it is a free routing layer.
 5. Mechanics: 10 mm jack pitch (two moulded TRS plugs); nothing in the 1.5 mm the plug's rear clamps.
    Every check (pads, bodies, courtyards, holes, edge) is numeric, see the end of main().

Board frame: x right, y down (KiCad). Top edge at y = -1.97 (the v4 plug tip), so the board stays 20 x 37.7 mm.
Run: python3 tools/gen_pcb.py ; then kicad-cli pcb drc fm1-midi-dongle.kicad_pcb --severity-all
"""
import math, pathlib, subprocess, sys, xml.etree.ElementTree as ET
import pcbnew
from pcbnew import VECTOR2I_MM as MM, FromMM, ToMM
if not hasattr(pcbnew.SwigPyIterator, 'next'):          # KiCad 10 SWIG + Python 3.14: __iter__ calls it.next()
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

HERE = pathlib.Path(__file__).resolve().parent.parent
PROJECT = 'fm1-midi-dongle'
KICAD_FP = pathlib.Path('/usr/share/kicad/footprints')
sys.path.insert(0, str(HERE / 'tools'))
from gen_sch import ROOT_UUID  # noqa: E402

# ---------------------------------------------------------------- the floorplan (mm)
W = 20.0                       # 10 mm jack pitch (two moulded TRS plugs) + 9 mm jack pad span + 0.5 mm margins
Y_TOP = -1.97                  # top edge (same as the v4 plug tip: outline unchanged in size)
J1_OVERHANG = 0.8              # USB-A shell front past the top edge; keeps its front legs' copper 0.5 mm off the edge
YJ = 28.4                      # jack centres, below the J2 / opto row
Y_BOT = YJ + 7.3               # jack body front flush with the edge, 2.1 mm nose outside
J2_Y = 15.9                    # power receptacle, left edge, below the power row
J2_OVERHANG = 1.0
NOTCH_Y, NOTCH_R, NOTCH_F = 22.2, 0.6, 0.3   # case locating notches, both side edges: half-moon r 0.6 (pin d 1.2, R7 pad 0.5 mm away),
                                             # 0.3 mm fillets so the lips are not sharp; the band between J2/D1 and
                                             # the jacks is the only one free on both edges
T = 'F.Cu'                     # single-sided: every part on the top face, one reflow pass
AUTO = None                    # rotation chosen by pad goals (see GOALS)

# MCU pins by side (rotated so 27/26 face the plug's D+/D-): left = VDD 2, VBUS_EN 5, LED 6 -> power and LED
# on the left; right/top-right = TX 21, RX 22, DIO 25 -> MIDI and the LinkE pads on the right.
PLACE = {
    # ref: (x, y, rotation)
    'J1': (0.0, AUTO, 0),            # USB-A receptacle, BOTTOM face, mouth up (y set from J1_OVERHANG)
    'U1': (AUTO, 4.6, AUTO),         # CH32X035: pins 27/26 face the top edge, right above J1's D+/D- pads
    'J3': (-5.0, YJ, 180),           # MIDI OUT jack (left): only two resistors, traces run under the jack body
    'J4': (5.0, YJ, 180),            # MIDI IN jack (right): tip/ring pads at x = 2, right under the opto chain
    'J2': (AUTO, J2_Y, AUTO),        # power receptacle, opening on the left edge, pads toward the centre
    # ---- top band (y < 1.4), freed by the old plug, between the front shell legs. Left to right: SY6280 (EN / IN
    # face the left gap, OUT / ISET face right), its ISET resistor, the 10 uF host-port cap, the DIO pad.
    # VBUS_HOST runs on F.Cu at y ~0.4 between R4 and the D+/D- vias (y 1.6), then down to J1's VBUS on B.Cu.
    'U3': (-3.25, -0.15, 90),        # SY6280: OUT (1) bottom-right toward C3, ISET (3) top-right into R4; EN lane left of it
    'R4': (0.05, -0.95, 0),          # ISET 6.8k, right of U3 pin 3
    'C3': (2.3, -0.2, 90),           # VBUS_HOST 10 uF standing: VBUS pad down (fed at y 0.1), GND pad up beside R4's
    'TP2': (4.45, -0.4, 0),          # DIO, inside the right front leg; DIO lane at y 1.45 comes up into it
    'TP1': (8.75, -0.45, 0),         # 3V3, top-right corner outside the leg
    # ---- row P (y 1.6 .. 6.6): MCU; ISET / EN parts left between the legs; THRU switch in the right column
    'C4': (-2.55, 3.25, 90),         # VDD 100 nF, vertical against the left pin row
    'R12': (-4.6, 5.6, 90),          # VBUS_EN 100k pull-down: EN lane (x -5.35) turns into its top pad at y 5.0
    'R10': (8.4, 3.5, 90),           # MIDI_RX 10k pull-up in the right column: RX pad up to the RX lane (y 1.85), 3V3 via below
    # hardware THRU switch, right column outside the right rear leg: B1 (RX) down toward U4 pin 4
    'U5': (6.5, 8.3, 180),           # SN74LVC1G3157 in the band between the MCU / right rear leg and the opto: B2 (RX) straight
                                     # above U4 pin 4, B1 (TX) up to the corridor right of the leg, S / VCC / A face left
    'R13': (4.5, 3.75, 0),           # OUT_SEL 100k pull-up: OUT_SEL pad on the MCU's pin 20 line, 3V3 pad right
    'C5': (2.5, 8.3, 180),             # opto VCC 100 nF in the band: 3V3 pad on the U5 VCC -> U4 pin 6 link, GND via left
    # ---- row Q (y 7.2 .. 10.4): LDO and its caps left, LED centre
    'U2': (-5.6, 8.8, AUTO),         # XC6206: VO toward C2, VI toward C1
    'C1': (-8.9, 8.5, 90),           # 5 V 1 uF at the LDO input
    'C2': (-2.85, 8.9, 90),          # 3V3 1 uF at the LDO output
    'R11': (-0.55, 7.9, 0),          # LED 1k
    'D2': (-0.55, 9.55, 0),          # LED, top face, visible
    'TP3': (-8.6, 0.4, 0),           # GND LinkE pad: free top-left corner outside the left legs; all three SDI pads on the top edge
    # ---- row R (y 10.8 .. 22.3): J2 left with its CC pull-downs; opto right; series parts above each jack's pads
    'R2': (-0.35, AUTO, 90),         # CC1 5.1k next to J2 A5
    'R3': (-0.35, AUTO, 90),         # CC2 5.1k next to J2 B5
    'U4': (5.4, 15.05, AUTO),        # H11L1SM: 2.1 mm lower than v4 to open the U5 band above it
    'R9': (2.4, 21.9, 90),           # MIDI IN 220 R between J4 tip (x 2) and U4 pin 1
    'D1': (6.2, 21.8, 0),            # 1N4148W across the opto LED, under U4 pins 1/2
    'R7': (-7.6, 22.4, 0),           # MIDI OUT tip 10 R, right above J3's tip pad
    'R8': (-4.5, 22.4, 0),           # MIDI OUT ring 33 R
}
DNP = set()
NO_FLIP = {'R10', 'C5'}       # pad sides chosen by the routing plan (RX pad toward the RX lane; C5's 3V3 pad on the U5 VCC link)
# pad -> target point (board mm); the rotation minimising the summed distances wins
GOALS = {
    'U1': {'27': (-0.75, 1.6), '26': (0.75, 1.6)},                # D+ / D- vias above the MCU (J1 D+ left, D- right)
    'U3': {'1': (2.3, 0.8), '5': (-2.78, 13.15), '4': (-5.35, 3.0), '3': (0.05, -0.95)},  # OUT -> C3, IN -> J2 VBUS, EN -> lane, ISET -> R4
    'U2': {'2': (-2.85, 8.9), '3': (-8.9, 8.5)},                  # VO -> C2, VI -> C1
    'U4': {'1': (2.0, YJ - 2.95), '2': (2.0, YJ + 1.05), '4': (1.8, 2.6)},  # LED pins toward J4 tip/ring, out up
}
ANGLES = {'U4': (0, 180), 'U3': (90,)}     # U3: pins sideways (the band is 3 mm tall), OUT toward the host port
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


def rect_gap(p, q):
    a, b = p.GetBoundingBox(), q.GetBoundingBox()
    dx = max(ToMM(a.GetLeft()) - ToMM(b.GetRight()), ToMM(b.GetLeft()) - ToMM(a.GetRight()), 0)
    dy = max(ToMM(a.GetTop()) - ToMM(b.GetBottom()), ToMM(b.GetTop()) - ToMM(a.GetBottom()), 0)
    return math.hypot(dx, dy)


def main():
    comps, nets = run_netlist()
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    b.SetLayerName(pcbnew.In1_Cu, 'GND1')
    b.SetLayerName(pcbnew.In2_Cu, 'PWR')
    ds = b.GetDesignSettings()
    ds.m_MinClearance = FromMM(0.2); ds.m_TrackMinWidth = FromMM(0.2)          # house rules (house_rules.yaml)
    ds.m_ViasMinSize = FromMM(0.6); ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_CopperEdgeClearance = FromMM(0.5); ds.m_HoleClearance = FromMM(HOLE_CLEAR)
    ds.SetBoardThickness(FromMM(0.8))
    for attr in ('m_TentViasFront', 'm_TentViasBack'):
        if hasattr(ds, attr): setattr(ds, attr, True)      # mask over vias: several sit at pad edges (plane_via)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(FromMM(0.2)); nc.SetTrackWidth(FromMM(0.2))
    nc.SetViaDiameter(FromMM(0.6)); nc.SetViaDrill(FromMM(0.3))

    netitems = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); netitems[name] = ni
    pad_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    fps = {}
    for ref, c in sorted(comps.items(), key=lambda kv: (kv[0] not in ('J1', 'J2', 'U1'), kv[0])):
        if not c['fp']:
            continue
        fp = load_fp(c['fp'])
        # KiCad-library parts: the 3D library is not installed here, so their models are vendored in the project
        # (KiCad 3D library, CC-BY-SA). Models() hands out copies: rebuild the list instead of editing in place.
        models = [(m.m_Filename, m.m_Offset, m.m_Rotation, m.m_Scale) for m in fp.Models()]
        if any(f.startswith('${KICAD') for f, *_ in models):
            fp.Models().clear()
            for f, off, rot, sc in models:
                m = pcbnew.FP_3DMODEL()
                m.m_Filename = ('${KIPRJMOD}/fm1_dongle.3dshapes/' + f.rsplit('/', 1)[1]) if f.startswith('${KICAD') else f
                m.m_Offset, m.m_Rotation, m.m_Scale = off, rot, sc
                fp.Models().push_back(m)
        fp.SetReference(ref); fp.SetValue(c['value'])
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        if c['tstamp']:
            fp.SetPath(pcbnew.KIID_PATH(f'/{ROOT_UUID}/{c["tstamp"]}'))
        if ref in DNP:
            fp.SetDNP(True)
        b.Add(fp)
        if ref not in PLACE:
            raise SystemExit(f'{ref} has no placement')
        x, y, rot = PLACE[ref]
        if ref == 'J1':
            # bottom face, mirrored top-to-bottom: at rotation 0 the mouth points up (-y) and D+ (3) is left of
            # D- (2), matching the MCU's 27/26. Shell front (courtyard edge) J1_OVERHANG past the top edge.
            fp.SetPosition(MM(0, 0)); fp.Flip(MM(0, 0), pcbnew.FLIP_DIRECTION_TOP_BOTTOM); fp.SetOrientationDegrees(0)
            front = ToMM(fp.GetCourtyard(pcbnew.B_CrtYd).BBox().GetTop())
            fp.SetPosition(MM(x, Y_TOP - J1_OVERHANG - front))
        elif ref == 'J2':
            # KiCad's HRO footprint (exact part) + the EasyEDA 3D model. After the 180 deg turn its shell legs sit
            # at y -3.93 / +0.25 and the footprint's SH holes at -3.13 / +1.05: model offset -0.80 (KiCad Y is up)
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL(); m.m_Filename = '${KIPRJMOD}/fm1_dongle.3dshapes/USB-C_SMD-TYPE-C-31-M-12_1.wrl'
            m.m_Offset = pcbnew.VECTOR3D(0, -0.80, 0); m.m_Rotation = pcbnew.VECTOR3D(0, 0, 180); m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
            fp.Models().push_back(m)
            best = None
            for ang in (90, 270):                     # opening to the left: solder row toward the board centre
                fp.SetOrientationDegrees(ang); fp.SetPosition(MM(0, y))
                px = pad_pos(fp, 'A5')[0]
                if best is None or px > best[0]:
                    best = (px, ang)
            fp.SetOrientationDegrees(best[1]); fp.SetPosition(MM(0, y))
            front = ToMM(fp.GetBoundingBox(False, False).GetLeft())
            fp.SetPosition(MM(-(W / 2 + J2_OVERHANG) - front, y))
        elif ref in ('R2', 'R3'):                     # beside J2's CC pad, same height
            cc = pad_pos(fps['J2'], 'A5' if ref == 'R2' else 'B5')
            fp.SetOrientationDegrees(rot); fp.SetPosition(MM(x, cc[1] + (-0.1 if ref == 'R2' else 0.1)))   # 3.0 mm CC pitch: 0.1 apart for courtyards
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

    # ---- two-pin parts: of the two orientations on their axis, keep the one that puts each signal pad nearest
    # the other pads of its net; a capacitor's GND / +3V3 pad aims at the nearest IC pin of its net (decoupling
    # loop); a resistor's GND / +3V3 pad has no target (it is one via to the plane)
    flipped = []
    for ref, fp in fps.items():
        pads = [p for p in fp.Pads() if p.GetNumber()]
        if len(pads) != 2 or ref[0] not in 'RCD' or ref in NO_FLIP:
            continue
        def cost():
            tot = 0.0
            for p in fp.Pads():
                n = p.GetNetname()
                if not n or n.startswith('unconnected') or (n in ('GND', '+3V3') and ref[0] != 'C'):
                    continue
                others = [pad_pos(fps[r], q) for r, q in nets[n] if r != ref and r in fps
                          and (n not in ('GND', '+3V3') or r[0] == 'U')]
                tot += min(math.dist(pad_pos(fp, p.GetNumber()), o) for o in others)
            return tot
        before = cost()
        rot0 = fp.GetOrientationDegrees()
        fp.SetOrientationDegrees(rot0 + 180)
        if cost() < before - 0.05:
            flipped.append(ref)
        else:
            fp.SetOrientationDegrees(rot0)
    print('flipped toward their nets:', sorted(flipped))

    # ---- outline: flat top edge (J1's mouth crosses it on the back face), straight sides, rounded corners
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); b.Add(s)
    def arc(x1, y1, xm, ym, x2, y2):
        a = pcbnew.PCB_SHAPE(b); a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(MM(x1, y1), MM(xm, ym), MM(x2, y2)); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(FromMM(0.1)); b.Add(a)
    r, hw = 1.0, W / 2
    rt = 0.75                                   # top corners: TP1's pad leaves 0.5 mm to the edge at r 0.75
    c = 1 - 0.7071
    arc(hw, Y_TOP + rt, hw - rt * c, Y_TOP + rt * c, hw - rt, Y_TOP)
    seg(hw - rt, Y_TOP, -hw + rt, Y_TOP)
    arc(-hw + rt, Y_TOP, -hw + rt * c, Y_TOP + rt * c, -hw, Y_TOP + rt)
    def side(xe, sgn, y_from, y_to):
        # straight edge from y_from to y_to with the locating notch; sgn = -1 on the right edge, +1 on the left
        R, f, yc = NOTCH_R, NOTCH_F, NOTCH_Y
        d = math.sqrt((R + f) ** 2 - f ** 2)
        def tan(fy):                            # fillet/notch tangent point for the fillet centred at (xe+sgn*f, fy)
            return (xe + (sgn * f) * R / (R + f), yc + (fy - yc) * R / (R + f))
        def fil(fy, from_edge):
            fx = xe + sgn * f
            e, t = (xe, fy), tan(fy)
            ang_e, ang_t = math.atan2(e[1] - fy, e[0] - fx), math.atan2(t[1] - fy, t[0] - fx)
            dm = (ang_t - ang_e + math.pi) % (2 * math.pi) - math.pi
            m = (fx + f * math.cos(ang_e + dm / 2), fy + f * math.sin(ang_e + dm / 2))
            (arc(*e, *m, *t) if from_edge else arc(*t, *m, *e))
        y1, y2 = (yc - d, yc + d) if y_from < y_to else (yc + d, yc - d)
        seg(xe, y_from, xe, y1)
        fil(y1, True)
        arc(*tan(y1), xe + sgn * R, yc, *tan(y2))
        fil(y2, False)
        seg(xe, y2, xe, y_to)
    side(hw, -1, Y_TOP + rt, Y_BOT - r)
    arc(hw, Y_BOT - r, hw - r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), hw - r, Y_BOT)
    seg(hw - r, Y_BOT, -hw + r, Y_BOT)
    arc(-hw + r, Y_BOT, -hw + r * (1 - 0.7071), Y_BOT - r * (1 - 0.7071), -hw, Y_BOT - r)
    side(-hw, 1, Y_BOT - r, Y_TOP + rt)

    # ---- inner planes: In1 = GND under the whole top side, In2 = +3V3 (every 3V3 pad is one via)
    for layer, name, net in ((pcbnew.In1_Cu, 'GND plane', 'GND'), (pcbnew.In2_Cu, '3V3 plane', '+3V3')):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(netitems[net]); z.SetZoneName(name)
        ol = z.Outline(); ol.NewOutline()
        for x, y in [(-hw, Y_TOP), (hw, Y_TOP), (hw, Y_BOT), (-hw, Y_BOT)]:
            ol.Append(MM(x, y))
        z.SetMinThickness(FromMM(0.25)); z.SetLocalClearance(FromMM(0.3))
        b.Add(z)

    # ---- QFN exposed pad: 2 x 2 via array into the GND planes (locked, so rip scripts keep them). D+ / D- run on
    # B.Cu under the MCU in lanes inside J1's 1.4 mm pads (D+ 0.2 outboard, D- 0.1 inboard): one via column
    # between the lanes, one between the D- lane and the MCU's right pin row
    ep = fps['U1']
    lanes = [pad_pos(fps['J1'], '3')[0] - 0.2, pad_pos(fps['J1'], '2')[0] - 0.1]
    for p in ep.Pads():
        if p.GetNumber() == '29':
            cx, cy = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
            cols = [x for x in (cx - 0.6, cx + 0.88) if all(abs(x - l) >= 0.3 + 0.1 + 0.2 - 1e-6 for l in lanes)]
            assert len(cols) == 2, (cx, lanes)
            for vx in cols:
                dx = vx - cx
                for dy in (-0.7, 0.7):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(MM(cx + dx, cy + dy))
                    v.SetWidth(FromMM(0.6)); v.SetDrill(FromMM(0.3)); v.SetNet(netitems['GND'])
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetLocked(True); b.Add(v)

    out = HERE / f'{PROJECT}.kicad_pcb'
    b.Save(str(out))
    print(f'wrote {out.name}: {len(fps)} footprints, {len(nets)} nets, board {W} x {Y_BOT - Y_TOP:.1f} mm')

    # ---- placement self-check: pad groups vs pad groups and bodies on the same side, holes vs copper
    print('orientations:', {r: fps[r].GetOrientationDegrees() for r in ('U1', 'U2', 'U3', 'U4', 'J2')})
    print('  J1 pads:', {p.GetNumber(): (round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in fps['J1'].Pads()})
    for ref in ('U1', 'U3'):
        print(f'  {ref} pads 26/27 or 1/5:', {n: tuple(round(v, 2) for v in pad_pos(fps[ref], n)) for n in (('26', '27') if ref == 'U1' else ('1', '5'))})
    def body(fp):                               # F.Fab outline (silk if the part has none): the plastic on the board
        items = [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_Fab and g.GetClass() != 'PCB_TEXT'] or \
                [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != 'PCB_TEXT']
        return bbox_of(items)
    def top_pads(fp):                           # what a top-face part can touch: top copper, incl. J1's shell legs
        return [p for p in fp.Pads() if p.GetNumber() and p.IsOnLayer(pcbnew.F_Cu)]
    pads_bb = {r: bbox_of(top_pads(fp)) for r, fp in fps.items()}
    bodies = {r: body(fp) for r, fp in fps.items()}
    refs = sorted(fps)
    issues = 0
    for i, a in enumerate(refs):
        for bref in refs[i + 1:]:
            if pads_bb[a] and pads_bb[bref] and overlap(pads_bb[a], pads_bb[bref], PAD_CLEAR):
                gap = min((rect_gap(p, q) for p in top_pads(fps[a]) for q in top_pads(fps[bref])   # pad by pad, not group bbox;
                           if not (p.GetNetname() and p.GetNetname() == q.GetNetname())), default=9)  # same net may touch
                if gap < PAD_CLEAR:
                    issues += 1; print(f'  PAD SPACING {gap:.2f} < {PAD_CLEAR}: {a} vs {bref}')
            for x, y in ((a, bref), (bref, a)):           # pad by pad: J1's legs sit at the board's four corners
                if bodies[y] and x not in ('J3', 'J4', 'J2') and any(overlap(bbox_of([q]), bodies[y], 0.1) for q in top_pads(fps[x])):
                    issues += 1; print(f'  PADS UNDER BODY: {x} under {y}')
    for i, a in enumerate(refs):                # courtyards (KiCad parts; EasyEDA ones are body-only, still checked)
        for bref in refs[i + 1:]:
            ca, cb = fps[a].GetCourtyard(pcbnew.F_CrtYd), fps[bref].GetCourtyard(pcbnew.F_CrtYd)
            if ca.OutlineCount() and cb.OutlineCount() and ca.Collide(cb):
                issues += 1; print(f'  COURTYARDS OVERLAP: {a} vs {bref}')
    # outline check: copper 0.5 mm inside the edge (house rule) (J2 and the jack noses overhang by design, their pads do not)
    for r, bb in pads_bb.items():
        if bb and r != 'J1' and (bb[1] < Y_TOP + 0.5 or bb[0] < -W / 2 + 0.5 or bb[2] > W / 2 - 0.5 or bb[3] > Y_BOT - 0.5):
            issues += 1; print(f'  PAD AT EDGE: {r} {bb}')
    holes = []                                  # (segment end a, end b, radius, ref): slots are capsules, round holes a == b
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                h = p.GetEffectiveHoleShape(); sg = h.GetSeg()
                holes.append(((ToMM(sg.A.x), ToMM(sg.A.y)), (ToMM(sg.B.x), ToMM(sg.B.y)), ToMM(h.GetWidth()) / 2, ref))
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0 or not p.GetNumber():
                continue
            bbp = p.GetBoundingBox()
            px0, py0, px1, py1 = ToMM(bbp.GetLeft()), ToMM(bbp.GetTop()), ToMM(bbp.GetRight()), ToMM(bbp.GetBottom())
            for ha, hb, hr, href in holes:
                if href == ref:
                    continue
                dist = 9.0
                for i in range(11):                     # pad rectangle to the slot's centre line, sampled
                    hx, hy = ha[0] + (hb[0] - ha[0]) * i / 10, ha[1] + (hb[1] - ha[1]) * i / 10
                    dist = min(dist, math.hypot(max(px0 - hx, 0, hx - px1), max(py0 - hy, 0, hy - py1)))
                if dist < hr + HOLE_CLEAR:
                    issues += 1
                    print(f'  HOLE too close: {href} hole at ({ha[0]:.2f},{ha[1]:.2f}) vs {ref} pad {p.GetNumber()}')
    print('placement issues:', issues)


if __name__ == '__main__':
    main()
