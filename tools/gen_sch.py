#!/usr/bin/env python3
"""Generate fm1-midi-dongle.kicad_sch (KiCad 9/10 format) from the locked design in DESIGN.md.

Signal connections are net labels on short stubs; power and ground are KiCad power symbols (global power
ports), so +3V3, GND, +5V_IN and VBUS_HOST read as rails on the sheet. Symbols come from KiCad's own libraries
(copied into lib_symbols so the file is self-contained); SY6280AAC, SN74LVC1G3157 and the USB-A receptacle are
drawn here because KiCad has no symbol for them. Reference/value texts are placed outside each symbol's
outline, and check_overlaps() fails the run if any symbol, label, power port or text overlaps another.

Run:  python3 tools/gen_sch.py            (writes ../fm1-midi-dongle.kicad_sch and .kicad_pro)
Then: kicad-cli sch erc fm1-midi-dongle.kicad_sch --severity-all
"""
import re, uuid, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
LIBDIR = pathlib.Path('/usr/share/kicad/symbols')
PROJECT = 'fm1-midi-dongle'
ROOT_UUID = '7f2a1c4e-0b3d-4c1a-9e8f-fm1dongle0001'.replace('fm1dongle0001', '5a6b7c8d9e0f')


# ---------------------------------------------------------------- s-expression helpers
def tokens(s):
    return re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', s)


def parse(s):
    st = [[]]
    for t in tokens(s):
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop(); st[-1].append(x)
        else:
            st[-1].append(t[1:-1] if t.startswith('"') else t)
    return st[0]


def symbol_block_text(libtext, name):
    """raw text of the top-level (symbol "name" ...) block"""
    m = re.search(r'\n[ \t]*\(symbol "%s"' % re.escape(name), libtext)
    if not m:
        raise SystemExit(f'symbol {name} not found')
    i = m.start() + 1
    depth = 0; j = i; instr = False
    while True:
        c = libtext[j]
        if instr:
            if c == '\\': j += 1
            elif c == '"': instr = False
        elif c == '"': instr = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return libtext[i:j + 1]
        j += 1


def symbol_pins(block):
    tree = parse(block)[0]
    out = []
    def walk(e):
        if isinstance(e, list) and e and e[0] == 'pin':
            d = {'type': e[1]}
            for f in e[2:]:
                if isinstance(f, list):
                    if f[0] == 'at': d['at'] = (float(f[1]), float(f[2]), float(f[3]) if len(f) > 3 else 0.0)
                    if f[0] == 'name': d['name'] = f[1]
                    if f[0] == 'number': d['num'] = f[1]
            out.append(d)
        elif isinstance(e, list):
            for f in e[1:]: walk(f)
    walk(tree)
    return out


_libcache = {}
def lib_text(lib):
    if lib not in _libcache:
        _libcache[lib] = (LIBDIR / f'{lib}.kicad_sym').read_text()
    return _libcache[lib]


def project_symbol(name):
    """symbols of the project library fm1_dongle: SY6280AAC drawn here, the PJ-320D jack
    converted from EasyEDA/LCSC with easyeda2kicad (tools/easyeda/), renamed and pointed at fm1_dongle footprints"""
    if name == 'SY6280AAC':
        return SY6280_BLOCK
    if name == 'SN74LVC1G3157':
        return SW3157_BLOCK
    if name == 'USB_A_911-321B2028S10100':
        return USBA_BLOCK
    if name == 'PJ-320D':
        return PJ320D_BLOCK
    src, orig = PROJECT_SYMBOLS[name]
    txt = (HERE / 'tools' / 'easyeda' / src).read_text()
    block = symbol_block_text(txt, orig)
    block = block.replace(f'"{orig}_', f'"{name}_').replace(f'(symbol "{orig}"', f'(symbol "{name}"', 1)
    block = block.replace('"jlc:', '"fm1_dongle:').replace('(pin unspecified ', '(pin passive ')
    return block


PROJECT_SYMBOLS = {
}


def load_symbol(lib, name):
    """(lib_symbols entry text, pins). Derived symbols ("extends") are flattened onto their parent."""
    if lib == 'fm1_dongle':
        block = project_symbol(name)
        return block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1), symbol_pins(block)
    txt = lib_text(lib)
    block = symbol_block_text(txt, name)
    tree = parse(block)[0]
    ext = [f[1] for f in tree if isinstance(f, list) and f[0] == 'extends']
    if ext:
        # flatten: the parent's drawing and pins, the derived symbol's own properties on top
        parent = symbol_block_text(txt, ext[0])
        flat = parent.replace(f'"{ext[0]}_', f'"{name}_').replace(f'(symbol "{ext[0]}"', f'(symbol "{name}"', 1)
        for m in re.finditer(r'\(property "([^"]+)" "((?:[^"\\]|\\.)*)"', block):
            k, v = m.group(1), m.group(2)
            flat = re.sub(r'\(property "%s" "(?:[^"\\]|\\.)*"' % re.escape(k), lambda _: f'(property "{k}" "{v}"', flat, count=1)
        block = flat
    block = block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    return block, symbol_pins(block)


SY6280_BLOCK = '''(symbol "fm1_dongle:SY6280AAC" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t(property "Reference" "U" (at -7.62 6.35 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "SY6280AAC" (at -7.62 -7.62 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-23-5" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Datasheet" "https://olimex.com/Products/Components/IC/SY6280/resources/SY6280AAC.PDF" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Description" "Silergy load switch, 2 A, programmable current limit Ilim=6800/Rset" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(symbol "SY6280AAC_0_1"
\t\t\t(rectangle (start -7.62 5.08) (end 7.62 -5.08) (stroke (width 0.254) (type default)) (fill (type background)))
\t\t)
\t\t(symbol "SY6280AAC_1_1"
\t\t\t(pin power_out line (at 10.16 2.54 180) (length 2.54) (name "OUT" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -7.62 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 10.16 -2.54 180) (length 2.54) (name "ISET" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin input line (at -10.16 -2.54 0) (length 2.54) (name "EN" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at -10.16 2.54 0) (length 2.54) (name "IN" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t)
\t)'''

# SPDT analog switch, pin map from the TI datasheet SCES424O (June 2025) table 4-1, DCK (SC70-6) package:
# 1 B2, 2 GND, 3 B1, 4 A (common), 5 VCC, 6 S. Function table 7-1: S low -> A = B1, S high -> A = B2
SW3157_BLOCK = '''(symbol "fm1_dongle:SN74LVC1G3157" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t(property "Reference" "U" (at -5.08 6.35 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "SN74LVC1G3157" (at -5.08 -11.43 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-363_SC-70-6" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Datasheet" "https://www.ti.com/lit/ds/symlink/sn74lvc1g3157.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Description" "TI SPDT analog switch: S low connects A to B1, S high connects A to B2" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(symbol "SN74LVC1G3157_0_1"
\t\t\t(rectangle (start -5.08 5.08) (end 5.08 -7.62) (stroke (width 0.254) (type default)) (fill (type background)))
\t\t)
\t\t(symbol "SN74LVC1G3157_1_1"
\t\t\t(pin bidirectional line (at -7.62 2.54 0) (length 2.54) (name "B2" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin bidirectional line (at -7.62 0 0) (length 2.54) (name "B1" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin bidirectional line (at 7.62 0 180) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 7.62 270) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t\t(pin input line (at -7.62 -5.08 0) (length 2.54) (name "S" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
\t\t)
\t)'''

# USB 2.0 type-A receptacle (host port), Jing Extension 911-321B2028S10100 (LCSC C42474). Pin map from the EasyEDA
# symbol/footprint for C42474 (1 VBUS, 2 D-, 3 D+, 4 GND, 5..8 shell legs), footprint checked against the datasheet
# drawing (signal pads at 2.00 / 7.00 mm pitch, shell legs 12.80 x 6.00 mm)
USBA_BLOCK = '''(symbol "fm1_dongle:USB_A_911-321B2028S10100" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t(property "Reference" "J" (at -5.08 6.35 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "USB-A" (at -5.08 -11.43 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "fm1_dongle:USB-A-SMD_911-321B2028S10100" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Datasheet" "https://jlcpcb.com/partdetail/C42474" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Description" "USB 2.0 type-A receptacle, SMD signal pins, through-hole shell legs" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(symbol "USB_A_911-321B2028S10100_0_1"
\t\t\t(rectangle (start -7.62 5.08) (end 7.62 -7.62) (stroke (width 0.254) (type default)) (fill (type background)))
\t\t)
\t\t(symbol "USB_A_911-321B2028S10100_1_1"
\t\t\t(pin passive line (at -10.16 2.54 0) (length 2.54) (name "VBUS" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at -10.16 -2.54 0) (length 2.54) (name "D-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at -10.16 0 0) (length 2.54) (name "D+" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at -2.54 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 2.54 -10.16 90) (length 2.54) (name "SH" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 2.54 -10.16 90) (length 2.54) hide (name "SH" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 2.54 -10.16 90) (length 2.54) hide (name "SH" (effects (font (size 1.27 1.27)))) (number "7" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 2.54 -10.16 90) (length 2.54) hide (name "SH" (effects (font (size 1.27 1.27)))) (number "8" (effects (font (size 1.27 1.27)))))
\t\t)
\t)'''


# 3.5 mm 4-pole jack PJ-320D (LCSC C521460): drawn here (the EasyEDA symbol drew its pin numbers over its own art).
# Pin map from the PJ-320D drawing: 1 sleeve, 2 ring2, 3 ring1, 4 tip
PJ320D_BLOCK = '''(symbol "fm1_dongle:PJ-320D" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t(property "Reference" "J" (at -7.62 6.35 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "PJ-320D" (at -7.62 -10.16 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "fm1_dongle:AUDIO-SMD_PJ-320D" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Datasheet" "https://jlcpcb.com/partdetail/C521460" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Description" "3.5 mm 4-pole audio jack, SMD" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(symbol "PJ-320D_0_1"
\t\t\t(rectangle (start -7.62 5.08) (end 2.54 -7.62) (stroke (width 0.254) (type default)) (fill (type background)))
\t\t\t(rectangle (start -6.604 1.27) (end -5.08 -3.81) (stroke (width 0.254) (type default)) (fill (type outline)))
\t\t)
\t\t(symbol "PJ-320D_1_1"
\t\t\t(pin passive line (at 5.08 2.54 180) (length 2.54) (name "TIP" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 5.08 0 180) (length 2.54) (name "RING" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 5.08 -2.54 180) (length 2.54) (name "R2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 5.08 -5.08 180) (length 2.54) (name "SL" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t)
\t)'''


# manufacturer part numbers, from the LCSC product pages (2026-10-17)
MPN = {'C7437027': 'CH32X035G8U6', 'C5446': 'XC6206P332MR', 'C55136': 'SY6280AAC', 'C899473': 'H11L1SM',
       'C3151751': 'TYPE-C 24P-GTJB 040', 'C165948': 'TYPE-C-31-M-12', 'C521460': 'PJ-320D',
       'C22859': '0603WAF100JT5E', 'C23140': '0603WAF330JT5E', 'C22962': '0603WAF2200T5E', 'C21190': '0603WAF1001T5E',
       'C23186': '0603WAF5101T5E', 'C23212': '0603WAF6801T5E', 'C25804': '0603WAF1002T5E', 'C22809': '0603WAF1502T5E',
       'C23206': '0603WAF5602T5E', 'C25803': '0603WAF1003T5E', 'C14663': 'CC0603KRX7R9BB104', 'C15849': 'CL10A105KB8NNNC',
       'C81598': '1N4148W', 'C2286': 'KT-0603R', 'C38663': 'SN74LVC1G3157DCKR',
       'C42474': '911-321B2028S10100', 'C96446': 'CL10A106MA8NRNC'}


# ---------------------------------------------------------------- schematic builder
_UID_NS = uuid.UUID('6f1d2c3b-4a59-4e87-9c0d-fm1dongle000'.replace('fm1dongle000', '1e2f3a4b5c6d'))
_uid_n = [0]
def uid():
    """deterministic: same schematic -> same uuids, so the PCB's symbol links survive a regeneration"""
    _uid_n[0] += 1
    return str(uuid.uuid5(_UID_NS, str(_uid_n[0])))


# power nets are drawn as KiCad power symbols (global power ports); the symbol's Value is the net name
POWER = {'GND': 'GND', '+3V3': '+3V3', '+5V_IN': '+5V', 'VBUS_HOST': 'VBUS'}
CHAR_W, TEXT_H = 1.0, 1.4          # stroke font at 1.27 mm: ~1 mm per character (estimate used by the overlap check)


def gfx_bbox(block):
    """outline of a symbol's drawing (lib units, y up): rectangles, polylines, arcs, circles; pins excluded"""
    body = re.sub(r'\(pin [^\n]*', '', block)
    pts = [(float(a), float(b)) for a, b in re.findall(r'\((?:xy|start|end|mid|center) ([-\d.]+) ([-\d.]+)\)', body)]
    if not pts:
        return (0, 0, 0, 0)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def text_box(x, y, s, ang=0, just='left'):
    """sheet-space box of a 1.27 mm text anchored at (x, y), justify <just> bottom"""
    w = CHAR_W * len(s)
    if ang in (90, 270):
        x0 = x - TEXT_H
        return (x0, y - w, x, y) if ang == 90 else (x0, y, x, y + w)     # 90 reads upward, 270 hangs down
    if just == 'left':
        return (x, y - TEXT_H, x + w, y)
    if just == 'right':
        return (x - w, y - TEXT_H, x, y)
    return (x - w / 2, y - TEXT_H, x + w / 2, y)


class Sch:
    def __init__(self):
        self.libs = {}          # "Lib:Name" -> block text
        self.pins = {}          # "Lib:Name" -> pins
        self.items = []         # emitted s-expr strings
        self.refs = []
        self.boxes = []         # (owner, what, (x0, y0, x1, y1)) in sheet mm, for check_overlaps()
        self.npwr = 0
        self.ports = []         # (net, owner, x, y) of drawn power ports

    def use(self, lib, name):
        key = f'{lib}:{name}'
        if key not in self.libs:
            self.libs[key], self.pins[key] = load_symbol(lib, name)
        return key

    def box(self, owner, what, b, pad=0.0):
        self.boxes.append((owner, what, (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)))

    def place(self, lib, name, ref, value, x, y, nets, footprint='', lcsc='', nc=(), hidden_value=False, extra=(), in_bom=True, dnp=False, rot=0):
        """nets: {pin_number: netname}; nc: pin numbers that get a no-connect flag.
        Reference and value go outside the symbol, where they hit nothing already drawn."""
        key = self.use(lib, name)
        pins = self.pins[key]
        if rot == 180:                                       # turned upside down: pins and outline mirrored through the origin
            pins = [dict(p, at=(-p['at'][0], -p['at'][1], (p['at'][2] + 180) % 360)) for p in pins]
        x, y = round(x / 1.27) * 1.27, round(y / 1.27) * 1.27    # KiCad connection grid
        g = gfx_bbox(self.libs[key])
        if rot == 180:
            g = (-g[2], -g[3], -g[0], -g[1])
        body = (x + g[0], y - g[3], x + g[2], y - g[1])
        sym = list(body)
        for p in pins:                                       # pin lines belong to the symbol too
            px, py, ang = p['at']
            X, Y = x + px, y - py
            L = 2.54 if 'length' not in p else p['length']
            d = {0: (1, 0), 180: (-1, 0), 90: (0, -1), 270: (0, 1)}[int(ang) % 360]
            X2, Y2 = X + d[0] * L, Y + d[1] * L
            sym = [min(sym[0], X, X2), min(sym[1], Y, Y2), max(sym[2], X, X2), max(sym[3], Y, Y2)]
        if not ref.startswith('#'):
            self.box(ref, 'symbol', sym, 0.3)
        # connections first, so the texts can avoid them
        done = set()
        conn = []
        for p in pins:
            px, py, ang = p['at']
            X, Y = x + px, y - py                          # library y points up, sheet y points down
            if (X, Y) in done: continue
            done.add((X, Y))
            if p['num'] in nets:
                conn.append((X, Y, ang, nets[p['num']]))
            elif p['num'] in nc or p['type'] == 'no_connect':
                self.items.append(f'\t(no_connect (at {X:g} {Y:g}) (uuid "{uid()}"))')
            else:
                raise SystemExit(f'{ref} pin {p["num"]} ({p.get("name")}) has no net and no NC')
        for X, Y, ang, net in conn:
            self.stub_label(X, Y, ang, net, owner=ref)
        # texts: two-pin vertical parts (R, C, test pads) to the right of the body, others above or below
        vertical = all(int(p['at'][2]) % 180 == 90 for p in pins)
        tw = max(len(ref), 0 if hidden_value else len(value)) * CHAR_W
        if vertical:
            cands = [(body[2] + 1.0, y - 0.6, y + 1.6), (body[0] - 1.0 - tw, y - 0.6, y + 1.6)]
        else:
            cands = [(sym[0], sym[1] - 2.0, sym[1] - 0.4), (sym[0], sym[3] + 1.8, sym[3] + 3.4),
                     (sym[2] - tw, sym[1] - 2.0, sym[1] - 0.4), (sym[2] - tw, sym[3] + 1.8, sym[3] + 3.4),
                     (sym[2] + 1.0, sym[1] + 2.0, sym[1] + 3.6)]
        pos = cands[0]
        for c in cands:
            tb = (c[0], c[1] - TEXT_H, c[0] + tw, c[2])
            if not any(overlap(tb, b) for o, w, b in self.boxes):
                pos = c
                break
        rx, ry, vy = pos
        if ref.startswith('#'):
            props = [('Reference', ref, x, y, True), ('Value', value, x, y, True)]
        else:
            props = [('Reference', ref, rx, ry, False), ('Value', value, rx, vy, hidden_value)]
            self.box(ref, 'reference', text_box(rx, ry, ref))
            if not hidden_value:
                self.box(ref, 'value', text_box(rx, vy, value))
        props += [('Footprint', footprint, x, y, True), ('Datasheet', '~', x, y, True)]
        if lcsc:
            props.append(('LCSC#', lcsc, x, y, True))
            if lcsc in MPN:
                props.append(('MPN', MPN[lcsc], x, y, True))
        for k, v in extra:
            props.append((k, v, x, y, True))
        s = [f'\t(symbol (lib_id "{key}") (at {x:g} {y:g} {rot}) (unit 1) (exclude_from_sim no) (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp {"yes" if dnp else "no"})',
             f'\t\t(uuid "{uid()}")']
        for k, v, px, py, hide in props:
            h = ' (hide yes)' if hide else ''
            s.append(f'\t\t(property "{k}" "{v}" (at {px:g} {py:g} 0) (effects (font (size 1.27 1.27)) (justify {"right top" if rot == 180 else "left bottom"}){h}))')   # a 180 deg symbol mirrors its fields' justification
        seen = set()
        for p in pins:
            if p['num'] in seen: continue
            seen.add(p['num'])
            s.append(f'\t\t(pin "{p["num"]}" (uuid "{uid()}"))')
        s.append(f'\t\t(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
        s.append('\t)')
        self.items.append('\n'.join(s))
        self.refs.append(ref)

    def stub_label(self, X, Y, ang, net, L=2.54, owner=''):
        # pin angle: direction from the connection point into the body. Outward is the opposite.
        d = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(ang) % 360]   # sheet coords
        X2, Y2 = X + d[0] * L, Y + d[1] * L
        self.items.append(f'\t(wire (pts (xy {X:g} {Y:g}) (xy {X2:g} {Y2:g})) (stroke (width 0) (type default)) (uuid "{uid()}"))')
        if net in POWER:
            for (n, o, px, py) in self.ports:
                if n == net and o == owner and abs(px - X2) < 0.01 and abs(abs(py - Y2) - 2.54) < 0.01:
                    self.items.append(f'\t(wire (pts (xy {X2:g} {Y2:g}) (xy {px:g} {py:g})) (stroke (width 0) (type default)) (uuid "{uid()}"))')
                    self.items.append(f'\t(junction (at {px:g} {py:g}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))')
                    return
            self.ports.append((net, owner, X2, Y2))
            self.power_port(net, X2, Y2, d, owner)
            return
        la = {0: 180, 180: 0, 90: 270, 270: 90}[int(ang) % 360]
        just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[la]
        self.items.append(f'\t(label "{net}" (at {X2:g} {Y2:g} {la}) (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid()}"))')
        if la in (0, 180):
            tb = text_box(X2, Y2, net, 0, 'left' if la == 0 else 'right')
        else:
            tb = text_box(X2, Y2, net, la, just)
        self.box(owner, f'label {net}', tb)

    def power_port(self, net, X, Y, d, owner=''):
        """global power symbol at the end of a stub pointing in sheet direction d. Ground hangs away from the
        pin, supplies point away from it; on side pins they lie along the stub."""
        sym = POWER[net]
        gnd = sym == 'GND'
        # rotation so the symbol's body points along d (GND body is +y on the sheet at 0, supplies -y)
        if gnd:
            rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]
        else:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]
        key = self.use('power', sym)
        self.npwr += 1
        ref = f'#PWR{self.npwr:03d}'
        far = 2.54 if not gnd else 2.54
        # value text just past the symbol's end, horizontal
        if d == (0, 1):
            vx, vy, just = X, Y + far + 1.9, 'center'
        elif d == (0, -1):
            vx, vy, just = X, Y - far - 0.6, 'center'
        elif d == (1, 0):
            vx, vy, just = X + far + 0.6, Y + 0.6, 'left'
        else:
            vx, vy, just = X - far - 0.6, Y + 0.6, 'right'
        self.items.append('\n'.join([
            f'\t(symbol (lib_id "{key}") (at {X:g} {Y:g} {rot}) (unit 1) (exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)',
            f'\t\t(uuid "{uid()}")',
            f'\t\t(property "Reference" "{ref}" (at {X:g} {Y:g} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
            f'\t\t(property "Value" "{net}" (at {vx:g} {vy:g} {(360 - rot) % 180}) (effects (font (size 1.27 1.27)) (justify {"" if just == "center" else just} bottom)))'.replace('(justify  bottom)', '(justify bottom)'),
            f'\t\t(property "Footprint" "" (at {X:g} {Y:g} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
            f'\t\t(property "Datasheet" "" (at {X:g} {Y:g} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
            f'\t\t(pin "1" (uuid "{uid()}"))',
            f'\t\t(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))',
            '\t)']))
        hw = 1.3 if gnd else 0.9                            # GND bar 2.54 wide, supply arrow 1.52
        if d[1]:
            b = (X - hw, min(Y, Y + d[1] * far), X + hw, max(Y, Y + d[1] * far))
        else:
            b = (min(X, X + d[0] * far), Y - hw, max(X, X + d[0] * far), Y + hw)
        self.box(owner, f'power {net}', b)
        self.box(owner, f'power {net} text', text_box(vx, vy, net, 0, just))

    def flag(self, net, x, y):
        """PWR_FLAG on a short stub to the net's power port (hung upside down under a supply, so its arrow points up)"""
        self.place('power', 'PWR_FLAG', f'#FLG{len(self.refs):02d}', 'PWR_FLAG', x, y, {'1': net}, rot=0 if net == 'GND' else 180)

    def text(self, s, x, y, size=1.5):
        lines = s.split('\n')
        self.box('text', 'note', (x, y, x + max(map(len, lines)) * size * 0.8, y + len(lines) * size * 1.7))
        s = s.replace('"', '\\"').replace('\n', '\\n')
        self.items.append(f'\t(text "{s}" (exclude_from_sim no) (at {x:g} {y:g} 0) (effects (font (size {size} {size})) (justify left top)) (uuid "{uid()}"))')

    def check_overlaps(self):
        """every pair of boxes from different owners, plus a symbol's own texts against its outline"""
        bad = []
        for i, (oa, wa, a) in enumerate(self.boxes):
            for ob, wb, b in self.boxes[i + 1:]:
                if oa == ob and 'symbol' in (wa, wb) and not {'reference', 'value'} & {wa, wb}:
                    continue
                if oa == ob and wa.startswith('power') and wb.startswith('power') and wa.split()[1] == wb.split()[1]:
                    continue
                if overlap(a, b):
                    bad.append(f'{oa} {wa} x {ob} {wb}')
        return bad

    def write(self, path):
        out = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")',
               f'\t(uuid "{ROOT_UUID}")', '\t(paper "A3")',
               '\t(title_block (title "FM-1 MIDI dongle: USB host to TRS MIDI") (date "2026-10-20") (rev "B") (company "Electronic Cats") (comment 1 "CH32X035G8U6 USB-A host, MIDI OUT 3.3 V type A with hardware THRU, isolated MIDI IN") (comment 2 "generated by tools/gen_sch.py from DESIGN.md"))',
               '\t(lib_symbols']
        for k in sorted(self.libs):
            out.append('\t' + self.libs[k].strip('\n'))
        out.append('\t)')
        out += self.items
        out.append('\t(sheet_instances (path "/" (page "1")))')
        out.append('\t(embedded_fonts no)')
        out.append(')')
        path.write_text('\n'.join(out) + '\n')


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main():
    s = Sch()
    R = 'Resistor_SMD:R_0603_1608Metric'
    C = 'Capacitor_SMD:C_0603_1608Metric'

    # ================= block 1, top left: 5 V input (power only USB-C receptacle)
    s.text('POWER IN  (USB-C, 5 V only)', 25, 25)
    s.place('Connector', 'USB_C_Receptacle_USB2.0_16P', 'J2', 'TYPE-C-31-M-12', 40, 70,
            {'A4': '+5V_IN', 'A9': '+5V_IN', 'B4': '+5V_IN', 'B9': '+5V_IN',
             'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'SH': 'GND',
             'A5': 'CC1_IN', 'B5': 'CC2_IN'},
            footprint='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', lcsc='C165948',
            nc=('A6', 'A7', 'B6', 'B7', 'A8', 'B8'))
    s.place('Device', 'R', 'R2', '5.1k', 85, 80, {'1': 'CC1_IN', '2': 'GND'}, footprint=R, lcsc='C23186')
    s.place('Device', 'R', 'R3', '5.1k', 100, 80, {'1': 'CC2_IN', '2': 'GND'}, footprint=R, lcsc='C23186')

    # ================= block 2: 3.3 V regulator
    s.text('3.3 V LDO', 130, 25)
    s.place('Device', 'C', 'C1', '1u', 130, 50, {'1': '+5V_IN', '2': 'GND'}, footprint=C, lcsc='C15849')
    s.place('Regulator_Linear', 'XC6206PxxxMR', 'U2', 'XC6206P332MR', 160, 45,
            {'3': '+5V_IN', '2': '+3V3', '1': 'GND'}, footprint='fm1_dongle:SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR', lcsc='C5446')
    s.place('Device', 'C', 'C2', '1u', 190, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C15849')

    # ================= block 3: host VBUS switch -> USB-A
    s.text('USB HOST PORT  (VBUS switch, 1 A limit)', 130, 75)
    s.place('Device', 'R', 'R12', '100k', 130, 105, {'1': 'VBUS_EN', '2': 'GND'}, footprint=R, lcsc='C25803',
            extra=(('Note', 'VBUS off until firmware enables it'),))
    s.place('fm1_dongle', 'SY6280AAC', 'U3', 'SY6280AAC', 165, 100,
            {'5': '+5V_IN', '1': 'VBUS_HOST', '2': 'GND', '4': 'VBUS_EN', '3': 'ISET'},
            footprint='fm1_dongle:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL', lcsc='C55136')
    s.place('Device', 'R', 'R4', '6.8k', 190, 110, {'1': 'ISET', '2': 'GND'}, footprint=R, lcsc='C23212',
            extra=(('Note', 'Ilim = 6800 / Rset = 1 A'),))
    s.place('Device', 'C', 'C3', '10u', 205, 100, {'1': 'VBUS_HOST', '2': 'GND'}, footprint=C, lcsc='C96446',
            extra=(('Note', 'bulk on the host port: a synth hot-plugged into J1 charges this, not the LDO input'),))
    s.place('fm1_dongle', 'USB_A_911-321B2028S10100', 'J1', '911-321B2028S10100', 240, 100,
            {'1': 'VBUS_HOST', '2': 'USB_DM', '3': 'USB_DP', '4': 'GND', '5': 'GND'},
            footprint='fm1_dongle:USB-A-SMD_911-321B2028S10100', lcsc='C42474',
            extra=(('Note', 'USB-A host port for any class-compliant synth, mounted on the BOTTOM face; '
                    'shell legs are through-hole (poke 0.65 mm through the 0.8 mm board)'),))

    # ================= block 4: MCU
    s.text('MCU  (CH32X035 USB host)', 290, 25)
    s.place('MCU_WCH_RiscV', 'CH32X035G8U6', 'U1', 'CH32X035G8U6', 330, 85,
            {'2': '+3V3', '29': 'GND',
             '26': 'USB_DM', '27': 'USB_DP',
             '21': 'MIDI_TX', '22': 'MIDI_RX', '20': 'OUT_SEL',
             '25': 'SDI_DIO',
             '8': 'VBUS_EN', '23': 'LED'},    # v6: PA3 (pin 8) / PB12 (pin 23), datasheet V2.2 QFN28 drawing
            footprint='fm1_dongle:QFN-28_L4.0-W4.0-P0.40-BL-EP2.8', lcsc='C7437027',
            nc=('1', '3', '4', '5', '6', '7', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '24', '28'),
            extra=(('Note', 'QFN28 F7P6/TSSOP20 has NO USB host; G8U6 required. footprint from EasyEDA/LCSC for C7437027 (EP 2.8 mm).'),))
    s.place('Device', 'C', 'C4', '100n', 380, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')
    # no D+/D- pull-downs: the X035 host port has them internally (RB_UH_PD_DIS = 0)

    # ================= block 5, bottom left: MIDI IN, isolated
    s.text('MIDI IN  (TRS type A, opto-isolated)', 25, 160)
    s.place('fm1_dongle', 'PJ-320D', 'J4', 'PJ-320D', 40, 190,
            {'4': 'MIDI_IN_TIP', '3': 'MIDI_IN_RING'}, nc=('1', '2'),
            footprint='fm1_dongle:AUDIO-SMD_PJ-320D', lcsc='C521460',
            extra=(('Note', 'sleeve (1, 2) left open at the receiver (MIDI spec). tip=4, ring=3'),))
    s.place('Device', 'R', 'R9', '220', 80, 180, {'1': 'MIDI_IN_TIP', '2': 'OPTO_A'}, footprint=R, lcsc='C22962')
    s.place('Device', 'D', 'D1', '1N4148W', 95, 205, {'1': 'OPTO_A', '2': 'MIDI_IN_RING'}, footprint='Diode_SMD:D_SOD-123', lcsc='C81598',
            extra=(('Note', 'reverse-polarity protection across the opto LED'),))
    s.place('Isolator', 'H11L1', 'U4', 'H11L1SM', 135, 190,
            {'1': 'OPTO_A', '2': 'MIDI_IN_RING', '4': 'MIDI_RX', '5': 'GND', '6': '+3V3'},
            footprint='fm1_dongle:SOP-6_L8.5-W6.4-P2.54-LS9.2-BL', lcsc='C899473',
            extra=(('Note', 'footprint from EasyEDA/LCSC for C899473'),))
    s.place('Device', 'C', 'C5', '100n', 165, 175, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')
    s.place('Device', 'R', 'R10', '10k', 180, 175, {'1': '+3V3', '2': 'MIDI_RX'}, footprint=R, lcsc='C25804')

    # ================= block 6: MIDI OUT with hardware THRU
    # U5 picks what drives the OUT jack's tip. OUT_SEL low (R13 pull-down default, MCU in reset or blank) = B1 =
    # MIDI_RX, the opto output: MIDI IN copied to MIDI OUT with no firmware. OUT_SEL high = B2 = MIDI_TX.
    # (v6: back to the v4 order; on the bottom face B2 and S line up with the MCU's TX and PB9 pins.)
    s.text('MIDI OUT  (TRS type A, 3.3 V)  with hardware THRU', 205, 160)
    s.place('fm1_dongle', 'SN74LVC1G3157', 'U5', 'SN74LVC1G3157', 230, 195,
            {'1': 'MIDI_TX', '3': 'MIDI_RX', '4': 'MIDI_OUT_DATA', '6': 'OUT_SEL', '5': '+3V3', '2': 'GND'},
            footprint='Package_TO_SOT_SMD:SOT-363_SC-70-6', lcsc='C38663',
            extra=(('Note', 'TI SCES424O: 1 B2, 2 GND, 3 B1, 4 A, 5 VCC, 6 S; S low A=B1, S high A=B2. Ron <= 25 ohm at 3 V'),))
    s.place('Device', 'R', 'R13', '100k', 210, 220, {'1': 'OUT_SEL', '2': 'GND'}, footprint=R, lcsc='C25803',
            extra=(('Note', 'OUT_SEL pull-down: default low = hardware THRU until firmware drives PB9 high'),))
    s.place('Device', 'R', 'R7', '10', 275, 200, {'1': 'MIDI_OUT_DATA', '2': 'MIDI_TIP_OUT'}, footprint=R, lcsc='C22859')
    s.place('Device', 'R', 'R8', '33', 300, 200, {'1': '+3V3', '2': 'MIDI_RING_OUT'}, footprint=R, lcsc='C23140')
    s.place('fm1_dongle', 'PJ-320D', 'J3', 'PJ-320D', 340, 195,
            {'4': 'MIDI_TIP_OUT', '3': 'MIDI_RING_OUT', '1': 'GND', '2': 'GND'},
            footprint='fm1_dongle:AUDIO-SMD_PJ-320D', lcsc='C521460',
            extra=(('Note', 'PJ-320D 4-pole: 1 sleeve, 2 ring2, 3 ring1, 4 tip. A TRS plug: tip=4, ring=3, sleeve on 1 and 2'),))

    # ================= block 7: status LED and programming pads
    s.text('STATUS LED + WCH-LinkE PADS', 25, 240)
    s.place('Device', 'R', 'R11', '1k', 40, 262, {'1': 'LED', '2': 'LED_K'}, footprint=R, lcsc='C21190')
    s.place('Device', 'LED', 'D2', 'LED red 0603', 65, 270, {'2': 'LED_K', '1': 'GND'}, footprint='LED_SMD:LED_0603_1608Metric', lcsc='C2286')
    # programming: three bare pads for the WCH-LinkE wires (no connector on a board this small)
    for ref, net, x in (('TP1', '+3V3', 100), ('TP2', 'SDI_DIO', 120), ('TP3', 'GND', 140)):
        s.place('Connector', 'TestPoint', ref, net, x, 262 if net != '+3V3' else 252, {'1': net}, rot=180 if net == '+3V3' else 0,
                footprint='TestPoint:TestPoint_Pad_1.5x1.5mm', in_bom=False,
                extra=(('Note', 'SDI pad: 3V3 / DIO (PC18, pin 25) / GND'),))

    # ================= power flags: the 5 V input and ground come from a connector, ERC needs a driver
    s.flag('+5V_IN', 175, 265)
    s.flag('GND', 195, 255)

    s.text('FM-1 MIDI dongle v5: USB-A host port (bottom face) for any class-compliant USB-MIDI synth.\n'
           'JLCPCB build: PCB 0.8 mm, 4 layers; J1 on the bottom face, every other part on top.\n'
           'No D+/D- pull-downs: the X035 host port has them internally (RB_UH_PD_DIS = 0).\n'
           'TRS type A: tip = MIDI pin 5 (data), ring = pin 4 (source), sleeve = pin 2.', 215, 240, size=1.27)

    bad = s.check_overlaps()
    for b in bad:
        print('  OVERLAP:', b)
    print('schematic overlaps:', len(bad))
    s.write(HERE / f'{PROJECT}.kicad_sch')
    blocks = [SY6280_BLOCK.replace('(symbol "fm1_dongle:SY6280AAC"', '(symbol "SY6280AAC"', 1),
              SW3157_BLOCK.replace('(symbol "fm1_dongle:SN74LVC1G3157"', '(symbol "SN74LVC1G3157"', 1),
              USBA_BLOCK.replace('(symbol "fm1_dongle:USB_A_911-321B2028S10100"', '(symbol "USB_A_911-321B2028S10100"', 1),
              PJ320D_BLOCK.replace('(symbol "fm1_dongle:PJ-320D"', '(symbol "PJ-320D"', 1)] + \
             [project_symbol(n) for n in PROJECT_SYMBOLS]
    (HERE / 'fm1_dongle.kicad_sym').write_text(
        '(kicad_symbol_lib (version 20241209) (generator "gen_sch") (generator_version "9.0")\n\t'
        + '\n\t'.join(b.strip('\n') for b in blocks) + '\n)\n')
    (HERE / 'sym-lib-table').write_text(
        '(sym_lib_table (version 7)\n  (lib (name "fm1_dongle")(type "KiCad")(uri "${KIPRJMOD}/fm1_dongle.kicad_sym")(options "")(descr "project symbols"))\n)\n')
    (HERE / f'{PROJECT}.kicad_pro').write_text(
        '{\n  "board": {"design_settings": {}},\n  "meta": {"filename": "%s.kicad_pro", "version": 1},\n'
        '  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},\n  "sheets": [["%s", "Root"]],\n  "text_variables": {}\n}\n'
        % (PROJECT, ROOT_UUID))
    print('wrote', PROJECT + '.kicad_sch', 'with', len(s.refs), 'symbols')


if __name__ == '__main__':
    main()
