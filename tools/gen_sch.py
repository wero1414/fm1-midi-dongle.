#!/usr/bin/env python3
"""Generate fm1-midi-dongle.kicad_sch (KiCad 9/10 format) from the locked design in DESIGN.md.

Every connection is made with net labels on short stubs, so the drawing is a correct netlist first and a
pretty schematic second. Symbols come from KiCad's own libraries (copied into lib_symbols so the file is
self-contained); SY6280AAC is drawn here because KiCad has no symbol for it.

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
    """symbols of the project library fm1_dongle: SY6280AAC drawn here, the USB-C plug and the PJ-320D jack
    converted from EasyEDA/LCSC with easyeda2kicad (tools/easyeda/), renamed and pointed at fm1_dongle footprints"""
    if name == 'SY6280AAC':
        return SY6280_BLOCK
    src, orig = PROJECT_SYMBOLS[name]
    txt = (HERE / 'tools' / 'easyeda' / src).read_text()
    block = symbol_block_text(txt, orig)
    block = block.replace(f'"{orig}_', f'"{name}_').replace(f'(symbol "{orig}"', f'(symbol "{name}"', 1)
    block = block.replace('"jlc:', '"fm1_dongle:').replace('(pin unspecified ', '(pin passive ')
    return block


PROJECT_SYMBOLS = {
    'USB-C_Plug_GTJB040': ('jlc_C3151751_etc.kicad_sym', 'TYPE-C24P-GTJB040'),
    'PJ-320D': ('jlc_C521460.kicad_sym', 'PJ-320D_C521460'),
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
\t\t(property "Reference" "U" (at -5.08 6.35 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "SY6280AAC" (at -5.08 -7.62 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-23-5" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Datasheet" "https://olimex.com/Products/Components/IC/SY6280/resources/SY6280AAC.PDF" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(property "Description" "Silergy load switch, 2 A, programmable current limit Ilim=6800/Rset" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
\t\t(symbol "SY6280AAC_0_1"
\t\t\t(rectangle (start -5.08 5.08) (end 5.08 -5.08) (stroke (width 0.254) (type default)) (fill (type background)))
\t\t)
\t\t(symbol "SY6280AAC_1_1"
\t\t\t(pin power_out line (at 7.62 2.54 180) (length 2.54) (name "OUT" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -7.62 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at 7.62 -2.54 180) (length 2.54) (name "ISET" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin input line (at -7.62 -2.54 0) (length 2.54) (name "EN" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at -7.62 2.54 0) (length 2.54) (name "IN" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t)
\t)'''


# manufacturer part numbers, from the LCSC product pages (2026-10-17)
MPN = {'C7437027': 'CH32X035G8U6', 'C5446': 'XC6206P332MR', 'C55136': 'SY6280AAC', 'C899473': 'H11L1SM',
       'C3151751': 'TYPE-C 24P-GTJB 040', 'C165948': 'TYPE-C-31-M-12', 'C521460': 'PJ-320D',
       'C22859': '0603WAF100JT5E', 'C23140': '0603WAF330JT5E', 'C22962': '0603WAF2200T5E', 'C21190': '0603WAF1001T5E',
       'C23186': '0603WAF5101T5E', 'C23212': '0603WAF6801T5E', 'C25804': '0603WAF1002T5E', 'C22809': '0603WAF1502T5E',
       'C23206': '0603WAF5602T5E', 'C25803': '0603WAF1003T5E', 'C14663': 'CC0603KRX7R9BB104', 'C15849': 'CL10A105KB8NNNC',
       'C81598': '1N4148W', 'C2286': 'KT-0603R'}


# ---------------------------------------------------------------- schematic builder
_UID_NS = uuid.UUID('6f1d2c3b-4a59-4e87-9c0d-fm1dongle000'.replace('fm1dongle000', '1e2f3a4b5c6d'))
_uid_n = [0]
def uid():
    """deterministic: same schematic -> same uuids, so the PCB's symbol links survive a regeneration"""
    _uid_n[0] += 1
    return str(uuid.uuid5(_UID_NS, str(_uid_n[0])))


class Sch:
    def __init__(self):
        self.libs = {}          # "Lib:Name" -> block text
        self.pins = {}          # "Lib:Name" -> pins
        self.items = []         # emitted s-expr strings
        self.refs = []

    def use(self, lib, name):
        key = f'{lib}:{name}'
        if key not in self.libs:
            self.libs[key], self.pins[key] = load_symbol(lib, name)
        return key

    def place(self, lib, name, ref, value, x, y, nets, footprint='', lcsc='', nc=(), hidden_value=False, extra=(), in_bom=True, dnp=False):
        """nets: {pin_number: netname}; nc: pin numbers that get a no-connect flag.
        Pins listed in neither are left for the caller to connect by position (not used here)."""
        key = self.use(lib, name)
        pins = self.pins[key]
        x, y = round(x / 1.27) * 1.27, round(y / 1.27) * 1.27    # KiCad connection grid
        props = [
            ('Reference', ref, x + 2.54, y - 2.54, False),
            ('Value', value, x + 2.54, y, hidden_value),
            ('Footprint', footprint, x, y, True),
            ('Datasheet', '~', x, y, True),
        ]
        if lcsc:
            props.append(('LCSC#', lcsc, x, y, True))
            if lcsc in MPN:
                props.append(('MPN', MPN[lcsc], x, y, True))
        for k, v in extra:
            props.append((k, v, x, y, True))
        s = [f'\t(symbol (lib_id "{key}") (at {x:g} {y:g} 0) (unit 1) (exclude_from_sim no) (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp {"yes" if dnp else "no"})',
             f'\t\t(uuid "{uid()}")']
        for k, v, px, py, hide in props:
            h = ' (hide yes)' if hide else ''
            s.append(f'\t\t(property "{k}" "{v}" (at {px:g} {py:g} 0) (effects (font (size 1.27 1.27)) (justify left){h}))')
        seen = set()
        for p in pins:
            if p['num'] in seen: continue
            seen.add(p['num'])
            s.append(f'\t\t(pin "{p["num"]}" (uuid "{uid()}"))')
        s.append(f'\t\t(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
        s.append('\t)')
        self.items.append('\n'.join(s))
        self.refs.append(ref)
        # connections
        done = set()
        for p in pins:
            px, py, ang = p['at']
            X, Y = x + px, y - py                          # library y points up, sheet y points down
            if (X, Y) in done: continue
            done.add((X, Y))
            if p['num'] in nets:
                self.stub_label(X, Y, ang, nets[p['num']])
            elif p['num'] in nc or p['type'] == 'no_connect':
                self.items.append(f'\t(no_connect (at {X:g} {Y:g}) (uuid "{uid()}"))')
            else:
                raise SystemExit(f'{ref} pin {p["num"]} ({p.get("name")}) has no net and no NC')

    def stub_label(self, X, Y, ang, net, L=2.54):
        # pin angle: direction from the connection point into the body. Outward is the opposite.
        d = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(ang) % 360]   # sheet coords
        la = {0: 180, 180: 0, 90: 270, 270: 90}[int(ang) % 360]
        X2, Y2 = X + d[0] * L, Y + d[1] * L
        self.items.append(f'\t(wire (pts (xy {X:g} {Y:g}) (xy {X2:g} {Y2:g})) (stroke (width 0) (type default)) (uuid "{uid()}"))')
        just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[la]
        self.items.append(f'\t(label "{net}" (at {X2:g} {Y2:g} {la}) (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid()}"))')

    def power(self, name, ref, x, y, net=None):
        """a power symbol (its Value is the net) on a stub with a label; the label ties it to the labelled net"""
        self.place('power', name, ref, (net or name) if name != 'PWR_FLAG' else 'PWR_FLAG', x, y, {'1': net or name})

    def text(self, s, x, y):
        s = s.replace('"', '\\"').replace('\n', '\\n')
        self.items.append(f'\t(text "{s}" (exclude_from_sim no) (at {x:g} {y:g} 0) (effects (font (size 1.5 1.5)) (justify left top)) (uuid "{uid()}"))')

    def write(self, path):
        out = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")',
               f'\t(uuid "{ROOT_UUID}")', '\t(paper "A3")',
               '\t(title_block (title "FM-1 MIDI dongle: USB host to TRS MIDI") (date "2026-10-17") (rev "A") (company "Electronic Cats") (comment 1 "CH32X035G8U6 USB host, MIDI OUT 3.3 V type A, isolated MIDI IN") (comment 2 "generated by tools/gen_sch.py from DESIGN.md"))',
               '\t(lib_symbols']
        for k in sorted(self.libs):
            out.append('\t' + self.libs[k].strip('\n'))
        out.append('\t)')
        out += self.items
        out.append('\t(sheet_instances (path "/" (page "1")))')
        out.append('\t(embedded_fonts no)')
        out.append(')')
        path.write_text('\n'.join(out) + '\n')


def main():
    s = Sch()
    R = 'Resistor_SMD:R_0603_1608Metric'
    C = 'Capacitor_SMD:C_0603_1608Metric'

    # ---- power in: J2 female USB-C, power only
    s.place('Connector', 'USB_C_Receptacle_USB2.0_16P', 'J2', 'TYPE-C-31-M-12', 40, 60,
            {'A4': '+5V_IN', 'A9': '+5V_IN', 'B4': '+5V_IN', 'B9': '+5V_IN',
             'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'SH': 'GND',
             'A5': 'CC1_IN', 'B5': 'CC2_IN'},
            footprint='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', lcsc='C165948',
            nc=('A6', 'A7', 'B6', 'B7', 'A8', 'B8'))
    s.place('Device', 'R', 'R2', '5.1k', 75, 55, {'1': 'CC1_IN', '2': 'GND'}, footprint=R, lcsc='C23186')
    s.place('Device', 'R', 'R3', '5.1k', 85, 55, {'1': 'CC2_IN', '2': 'GND'}, footprint=R, lcsc='C23186')

    # ---- 3.3 V regulator
    s.place('Regulator_Linear', 'XC6206PxxxMR', 'U2', 'XC6206P332MR', 110, 40,
            {'3': '+5V_IN', '2': '+3V3', '1': 'GND'}, footprint='fm1_dongle:SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR', lcsc='C5446')
    s.place('Device', 'C', 'C1', '1u', 95, 50, {'1': '+5V_IN', '2': 'GND'}, footprint=C, lcsc='C15849')
    s.place('Device', 'C', 'C2', '1u', 125, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C15849')

    # ---- host VBUS switch
    s.place('fm1_dongle', 'SY6280AAC', 'U3', 'SY6280AAC', 110, 80,
            {'5': '+5V_IN', '1': 'VBUS_FM1', '2': 'GND', '4': 'VBUS_EN', '3': 'ISET'},
            footprint='fm1_dongle:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL', lcsc='C55136')
    s.place('Device', 'R', 'R4', '6.8k', 125, 92, {'1': 'ISET', '2': 'GND'}, footprint=R, lcsc='C23212',
            extra=(('Note', 'Ilim = 6800 / Rset = 1 A'),))
    s.place('Device', 'R', 'R12', '100k', 95, 92, {'1': 'VBUS_EN', '2': 'GND'}, footprint=R, lcsc='C25803',
            extra=(('Note', 'VBUS off until firmware enables it'),))
    s.place('Device', 'C', 'C3', '1u', 135, 80, {'1': 'VBUS_FM1', '2': 'GND'}, footprint=C, lcsc='C15849')

    # ---- MCU
    s.place('MCU_WCH_RiscV', 'CH32X035G8U6', 'U1', 'CH32X035G8U6', 190, 90,
            {'2': '+3V3', '29': 'GND',
             '26': 'USB_DM', '27': 'USB_DP',
             '21': 'MIDI_TX', '22': 'MIDI_RX',
             '25': 'SDI_DIO',
             '5': 'VBUS_EN', '6': 'LED'},
            footprint='fm1_dongle:QFN-28_L4.0-W4.0-P0.40-BL-EP2.8', lcsc='C7437027',
            nc=('1', '3', '4', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '23', '24', '28'),
            extra=(('Note', 'QFN28 F7P6/TSSOP20 has NO USB host; G8U6 required. footprint from EasyEDA/LCSC for C7437027 (EP 2.8 mm).'),))
    s.place('Device', 'C', 'C4', '100n', 230, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')
    # no D+/D- pull-downs: the X035 host port has them internally (RB_UH_PD_DIS = 0); stubs on a USB pair are worse than nothing

    # ---- J1 male plug to the FM-1 (dongle is the host / DFP)
    s.place('fm1_dongle', 'USB-C_Plug_GTJB040', 'J1', 'TYPE-C 24P-GTJB 040', 280, 90,
            {'A4': 'VBUS_FM1', 'B4': 'VBUS_FM1', 'B9': 'VBUS_FM1',
             'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', '25': 'GND', '26': 'GND',
             'A5': 'CC_FM1', 'A6': 'USB_DP', 'A7': 'USB_DM'},
            footprint='fm1_dongle:USB-C-SMD_TYPE-C-24P-GTJB-040', lcsc='C3151751',
            nc=('A2', 'A3', 'A8', 'A9', 'A10', 'A11', 'B2', 'B3', 'B5', 'B6', 'B7', 'B8', 'B10', 'B11'),
            extra=(('Note', 'SHOU HAN TYPE-C 24P-GTJB 040, board-edge clamp plug: PCB 0.80 +/-0.05 mm, pads on both faces (datasheet p.2); JLCPCB Standard assembly only. VBUS on A4 (top) + B4/B9 (back, joined to A4 by a via): 3 of 4 contacts, ~0.33 A each at the 1 A limit. A9 is NC: it sits right of the USB pair and the DIO/RX traces pass under it'),))
    s.place('Device', 'R', 'R1', '56k', 310, 60, {'1': '+5V_IN', '2': 'CC_FM1'}, footprint=R, lcsc='C23206',
            extra=(('Note', 'Rp: the FM-1 sees a default-USB host'),))

    # ---- MIDI OUT, TRS type A, 3.3 V
    s.place('Device', 'R', 'R7', '10', 180, 150, {'1': 'MIDI_TX', '2': 'MIDI_TIP_OUT'}, footprint=R, lcsc='C22859')
    s.place('Device', 'R', 'R8', '33', 190, 150, {'1': '+3V3', '2': 'MIDI_RING_OUT'}, footprint=R, lcsc='C23140')
    s.place('fm1_dongle', 'PJ-320D', 'J3', 'PJ-320D', 210, 150,
            {'4': 'MIDI_TIP_OUT', '3': 'MIDI_RING_OUT', '1': 'GND', '2': 'GND'},
            footprint='fm1_dongle:AUDIO-SMD_PJ-320D', lcsc='C521460',
            extra=(('Note', 'PJ-320D 4-pole: 1 sleeve, 2 ring2, 3 ring1, 4 tip. A TRS plug: tip=4, ring=3, sleeve on 1 and 2'),))

    # ---- MIDI IN, isolated
    s.place('fm1_dongle', 'PJ-320D', 'J4', 'PJ-320D', 40, 150,
            {'4': 'MIDI_IN_TIP', '3': 'MIDI_IN_RING'}, nc=('1', '2'),
            footprint='fm1_dongle:AUDIO-SMD_PJ-320D', lcsc='C521460',
            extra=(('Note', 'sleeve (1, 2) left open at the receiver (MIDI spec). tip=4, ring=3'),))
    s.place('Device', 'R', 'R9', '220', 60, 140, {'1': 'MIDI_IN_TIP', '2': 'OPTO_A'}, footprint=R, lcsc='C22962')
    s.place('Device', 'D', 'D1', '1N4148W', 75, 150, {'1': 'OPTO_A', '2': 'MIDI_IN_RING'}, footprint='Diode_SMD:D_SOD-123', lcsc='C81598',
            extra=(('Note', 'reverse-polarity protection across the opto LED'),))
    s.place('Isolator', 'H11L1', 'U4', 'H11L1SM', 100, 150,
            {'1': 'OPTO_A', '2': 'MIDI_IN_RING', '4': 'MIDI_RX', '5': 'GND', '6': '+3V3'},
            footprint='fm1_dongle:SOP-6_L8.5-W6.4-P2.54-LS9.2-BL', lcsc='C899473',
            extra=(('Note', 'footprint from EasyEDA/LCSC for C899473'),))
    s.place('Device', 'R', 'R10', '10k', 125, 140, {'1': '+3V3', '2': 'MIDI_RX'}, footprint=R, lcsc='C25804')
    s.place('Device', 'C', 'C5', '100n', 100, 130, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')

    # ---- status LED + SDI header
    s.place('Device', 'R', 'R11', '1k', 250, 150, {'1': 'LED', '2': 'LED_K'}, footprint=R, lcsc='C21190')
    s.place('Device', 'LED', 'D2', 'LED red 0603', 265, 160, {'2': 'LED_K', '1': 'GND'}, footprint='LED_SMD:LED_0603_1608Metric', lcsc='C2286')
    # programming: three bare pads for the WCH-LinkE wires (no connector on a board this small)
    for ref, net, x in (('TP1', '+3V3', 285), ('TP2', 'SDI_DIO', 295), ('TP3', 'GND', 305)):
        s.place('Connector', 'TestPoint', ref, net, x, 150, {'1': net},
                footprint='TestPoint:TestPoint_Pad_1.5x1.5mm', in_bom=False,
                extra=(('Note', 'SDI pad: 3V3 / DIO (PC18, pin 25) / GND'),))

    # ---- power symbols and flags (one per net, tied by label)
    s.power('+5V', '#PWR01', 40, 190, net='+5V_IN')
    s.power('PWR_FLAG', '#FLG01', 50, 190, net='+5V_IN')
    s.power('+3V3', '#PWR02', 70, 190)
    s.power('GND', '#PWR03', 90, 190)
    s.power('PWR_FLAG', '#FLG02', 100, 190, net='GND')

    s.text('FM-1 MIDI dongle, rev A (netlist-first drawing: every connection is a net label; tidy before layout).\n'
           'JLCPCB build: PCB 0.8 mm (the plug clamps the board edge), all parts top side SMD, footprints from EasyEDA/LCSC.\n'
           'No D+/D- pull-downs: the X035 host port has them internally (RB_UH_PD_DIS = 0).\n'
           'TRS type A: tip = MIDI pin 5 (data), ring = pin 4 (source), sleeve = pin 2.', 150, 185)

    s.write(HERE / f'{PROJECT}.kicad_sch')
    blocks = [SY6280_BLOCK.replace('(symbol "fm1_dongle:SY6280AAC"', '(symbol "SY6280AAC"', 1)] + \
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
