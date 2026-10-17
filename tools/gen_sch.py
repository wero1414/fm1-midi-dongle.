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
    m = re.search(r'\n\t\(symbol "%s"' % re.escape(name), libtext)
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


def load_symbol(lib, name):
    """(lib_symbols entry text, pins). Derived symbols ("extends") are flattened onto their parent."""
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


# ---------------------------------------------------------------- schematic builder
def uid():
    return str(uuid.uuid4())


class Sch:
    def __init__(self):
        self.libs = {}          # "Lib:Name" -> block text
        self.pins = {}          # "Lib:Name" -> pins
        self.items = []         # emitted s-expr strings
        self.refs = []

    def use(self, lib, name):
        key = f'{lib}:{name}'
        if key not in self.libs:
            if key == 'fm1_dongle:SY6280AAC':
                self.libs[key] = SY6280_BLOCK
                self.pins[key] = symbol_pins(SY6280_BLOCK)
            else:
                self.libs[key], self.pins[key] = load_symbol(lib, name)
        return key

    def place(self, lib, name, ref, value, x, y, nets, footprint='', lcsc='', nc=(), hidden_value=False, extra=()):
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
        for k, v in extra:
            props.append((k, v, x, y, True))
        s = [f'\t(symbol (lib_id "{key}") (at {x:g} {y:g} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)',
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
    s.place('Connector', 'USB_C_Receptacle_USB2.0_16P', 'J2', 'USB-C power in', 40, 60,
            {'A4': '+5V_IN', 'A9': '+5V_IN', 'B4': '+5V_IN', 'B9': '+5V_IN',
             'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'SH': 'GND',
             'A5': 'CC1_IN', 'B5': 'CC2_IN'},
            footprint='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', lcsc='C165948',
            nc=('A6', 'A7', 'B6', 'B7', 'A8', 'B8'))
    s.place('Device', 'R', 'R2', '5.1k', 75, 55, {'1': 'CC1_IN', '2': 'GND'}, footprint=R, lcsc='C23186')
    s.place('Device', 'R', 'R3', '5.1k', 85, 55, {'1': 'CC2_IN', '2': 'GND'}, footprint=R, lcsc='C23186')

    # ---- 3.3 V regulator
    s.place('Regulator_Linear', 'XC6206PxxxMR', 'U2', 'XC6206P332MR', 110, 40,
            {'3': '+5V_IN', '2': '+3V3', '1': 'GND'}, footprint='Package_TO_SOT_SMD:SOT-23-3', lcsc='C5446')
    s.place('Device', 'C', 'C1', '1u', 95, 50, {'1': '+5V_IN', '2': 'GND'}, footprint=C, lcsc='C15849')
    s.place('Device', 'C', 'C2', '1u', 125, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C15849')

    # ---- host VBUS switch
    s.place('fm1_dongle', 'SY6280AAC', 'U3', 'SY6280AAC', 110, 80,
            {'5': '+5V_IN', '1': 'VBUS_FM1', '2': 'GND', '4': 'VBUS_EN', '3': 'ISET'},
            footprint='Package_TO_SOT_SMD:SOT-23-5', lcsc='C55136')
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
            footprint='Package_DFN_QFN:WQFN-28-1EP_4x4mm_P0.4mm_EP2.7x2.7mm', lcsc='C7437027',
            nc=('1', '3', '4', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '23', '24', '28'),
            extra=(('Note', 'QFN28 F7P6/TSSOP20 has NO USB host; G8U6 required. footprint = KiCad symbol default; EP size not in the datasheet text, verify on the drawing.'),))
    s.place('Device', 'C', 'C4', '100n', 230, 50, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')
    s.place('Device', 'R', 'R5', '15k', 230, 100, {'1': 'USB_DM', '2': 'GND'}, footprint=R, lcsc='C22809',
            extra=(('Note', 'host-side pull-down; drop if the X035 host port has internal ones (RM check)'),))
    s.place('Device', 'R', 'R6', '15k', 240, 100, {'1': 'USB_DP', '2': 'GND'}, footprint=R, lcsc='C22809')

    # ---- J1 male plug to the FM-1 (dongle is the host / DFP)
    s.place('Connector', 'USB_C_Plug_USB2.0', 'J1', 'USB-C plug to FM-1', 280, 90,
            {'A4': 'VBUS_FM1', 'A9': 'VBUS_FM1', 'B4': 'VBUS_FM1', 'B9': 'VBUS_FM1',
             'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'SH': 'GND',
             'A5': 'CC_FM1', 'A6': 'USB_DP', 'A7': 'USB_DM'},
            footprint='', lcsc='C3151751', nc=('B5',),
            extra=(('Note', 'SHOU HAN TYPE-C 24P-GTJB 040; footprint from EasyEDA, PCB thickness unverified'),))
    s.place('Device', 'R', 'R1', '56k', 310, 60, {'1': '+5V_IN', '2': 'CC_FM1'}, footprint=R, lcsc='C23206',
            extra=(('Note', 'Rp: the FM-1 sees a default-USB host'),))

    # ---- MIDI OUT, TRS type A, 3.3 V
    s.place('Device', 'R', 'R7', '10', 180, 150, {'1': 'MIDI_TX', '2': 'MIDI_TIP_OUT'}, footprint=R, lcsc='C22859')
    s.place('Device', 'R', 'R8', '33', 190, 150, {'1': '+3V3', '2': 'MIDI_RING_OUT'}, footprint=R, lcsc='C23140')
    s.place('Connector_Audio', 'AudioJack3', 'J3', 'MIDI OUT TRS', 210, 150,
            {'T': 'MIDI_TIP_OUT', 'R': 'MIDI_RING_OUT', 'S': 'GND'},
            footprint='Connector_Audio:Jack_3.5mm_PJ320D_Horizontal', lcsc='C18594',
            extra=(('Note', 'PJ-320B: footprint placeholder is PJ320D, verify'),))

    # ---- MIDI IN, isolated
    s.place('Connector_Audio', 'AudioJack3', 'J4', 'MIDI IN TRS', 40, 150,
            {'T': 'MIDI_IN_TIP', 'R': 'MIDI_IN_RING'}, nc=('S',),
            footprint='Connector_Audio:Jack_3.5mm_PJ320D_Horizontal', lcsc='C18594',
            extra=(('Note', 'sleeve left open at the receiver (MIDI spec)'),))
    s.place('Device', 'R', 'R9', '220', 60, 140, {'1': 'MIDI_IN_TIP', '2': 'OPTO_A'}, footprint=R, lcsc='C22962')
    s.place('Device', 'D', 'D1', '1N4148W', 75, 150, {'1': 'OPTO_A', '2': 'MIDI_IN_RING'}, footprint='Diode_SMD:D_SOD-123', lcsc='C81598',
            extra=(('Note', 'reverse-polarity protection across the opto LED'),))
    s.place('Isolator', 'H11L1', 'U4', 'H11L1SM', 100, 150,
            {'1': 'OPTO_A', '2': 'MIDI_IN_RING', '4': 'MIDI_RX', '5': 'GND', '6': '+3V3'},
            footprint='Package_DIP:SMDIP-6_W7.62mm', lcsc='C899473',
            extra=(('Note', 'SMD gull-wing 6-pin; footprint to verify against onsemi drawing'),))
    s.place('Device', 'R', 'R10', '10k', 125, 140, {'1': '+3V3', '2': 'MIDI_RX'}, footprint=R, lcsc='C25804')
    s.place('Device', 'C', 'C5', '100n', 100, 130, {'1': '+3V3', '2': 'GND'}, footprint=C, lcsc='C14663')

    # ---- status LED + SDI header
    s.place('Device', 'R', 'R11', '1k', 250, 150, {'1': 'LED', '2': 'LED_K'}, footprint=R, lcsc='C21190')
    s.place('Device', 'LED', 'D2', 'green', 265, 160, {'2': 'LED_K', '1': 'GND'}, footprint='LED_SMD:LED_0603_1608Metric', lcsc='C72043')
    # programming: three bare pads for the WCH-LinkE wires (no connector on a board this small)
    for ref, net, x in (('TP1', '+3V3', 285), ('TP2', 'SDI_DIO', 295), ('TP3', 'GND', 305)):
        s.place('Connector', 'TestPoint', ref, net, x, 150, {'1': net},
                footprint='TestPoint:TestPoint_Pad_1.5x1.5mm',
                extra=(('Note', 'SDI pad: 3V3 / DIO (PC18, pin 25) / GND'),))

    # ---- power symbols and flags (one per net, tied by label)
    s.power('+5V', '#PWR01', 40, 190, net='+5V_IN')
    s.power('PWR_FLAG', '#FLG01', 50, 190, net='+5V_IN')
    s.power('+3V3', '#PWR02', 70, 190)
    s.power('GND', '#PWR03', 90, 190)
    s.power('PWR_FLAG', '#FLG02', 100, 190, net='GND')

    s.text('FM-1 MIDI dongle, rev A (netlist-first drawing: every connection is a net label; tidy before layout).\n'
           'Open items before ordering: J1 plug footprint + PCB thickness; PJ-320B footprint (placeholder PJ320D);\n'
           'U4 SMDIP footprint; U1 exposed-pad size; whether the X035 host port has internal D+/D- pull-downs (R5/R6).\n'
           'TRS type A: tip = MIDI pin 5 (data), ring = pin 4 (source), sleeve = pin 2.', 150, 185)

    s.write(HERE / f'{PROJECT}.kicad_sch')
    (HERE / 'fm1_dongle.kicad_sym').write_text(
        '(kicad_symbol_lib (version 20241209) (generator "gen_sch") (generator_version "9.0")\n\t'
        + SY6280_BLOCK.replace('(symbol "fm1_dongle:SY6280AAC"', '(symbol "SY6280AAC"', 1) + '\n)\n')
    (HERE / 'sym-lib-table').write_text(
        '(sym_lib_table (version 7)\n  (lib (name "fm1_dongle")(type "KiCad")(uri "${KIPRJMOD}/fm1_dongle.kicad_sym")(options "")(descr "project symbols"))\n)\n')
    (HERE / f'{PROJECT}.kicad_pro').write_text(
        '{\n  "board": {"design_settings": {}},\n  "meta": {"filename": "%s.kicad_pro", "version": 1},\n'
        '  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},\n  "sheets": [["%s", "Root"]],\n  "text_variables": {}\n}\n'
        % (PROJECT, ROOT_UUID))
    print('wrote', PROJECT + '.kicad_sch', 'with', len(s.refs), 'symbols')


if __name__ == '__main__':
    main()
