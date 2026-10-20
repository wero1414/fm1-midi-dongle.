# FM-1 MIDI dongle: USB host to TRS MIDI (locked 2026-10-17; v5 USB-A host port 2026-10-20, see the end)

A stick that plugs into the M-VAVE FM-1's USB-C port (left side) and gives it a TRS MIDI OUT and a
TRS MIDI IN. The FM-1 is a USB MIDI device, so the stick is a USB host. It works with any FM-1 firmware
that sends MIDI over USB (Melodee, SLOOP, Felucca, Hortator, stock).

## Decisions (owner, this conversation)
- MCU: WCH CH32X035G8U6, QFN-28. Cheapest WCH part with a USB full-speed HOST. The TSSOP-20
  CH32X035F7P6 does not have host (datasheet V2.3 selection table), so it is out.
- MIDI IN isolated (H11L1SM). MIDI OUT 3.3 V, TRS type A (matches the FM-1's own jack type).
- Second USB-C (female) is POWER ONLY. One USB port on the chip, so no pass-through to a computer.
- Hand assembled by the owner; PCB from JLCPCB, parts from LCSC. Programmer: WCH-LinkE (owner has one).
- Form: male plug toward the FM-1, both TRS jacks on the far end facing away from the FM-1.

## Block diagram
```
 J2 USB-C F (5 V in) --VBUS--> U3 SY6280 (1 A limit, EN from MCU) --VBUS--> J1 USB-C male --> FM-1
                      \--> U2 XC6206 3.3 V --> U1 CH32X035G8U6
 U1 PC16/UDM (pin 26), PC17/UDP (pin 27) <--> J1 D-, D+        (host side: 15k pull-downs, see R5 R6)
 U1 PB10/TX1 (pin 21) --> U5 B1 \
 U4 out (MIDI_RX)     --> U5 B2  > U5 A --10 Ω--> J3 tip ; 3V3 --33 Ω--> J3 ring ; sleeve GND   MIDI OUT / THRU, type A
 U1 PB9 (pin 20)      --> U5 S  /  (v5: 100k R13 to 3V3: S high = B2 = hardware THRU by default)
 J4 tip/ring --220 Ω--> U4 H11L1SM LED (D1 reverse) ; U4 out --pull-up--> U1 PB11/RX1 (pin 22)   MIDI IN
 U1 PC18/DIO (pin 25) + GND + 3V3 --> 3-pin SDI header/pads for WCH-LinkE
 U1 VDD pin 2, GND = exposed pad (pin "0" in the datasheet diagram)
```

## Connector details
- J1 (male plug, to the FM-1, board-edge clamp type, PCB 0.8 mm): the dongle is the host (DFP). Rp = 56 kΩ from 5 V to the CC pin.
  A captive plug wires one CC pin; the other (VCONN) left open. VBUS from U3 output.
- J2 (female, power in): Rd = 5.1 kΩ to GND on CC1 and CC2 so a USB-C charger or power bank turns on 5 V.
  D+/D- unconnected.
- J3/J4 TRS type A: tip = MIDI pin 5 (data sink), ring = MIDI pin 4 (source), sleeve = MIDI pin 2. On the PJ-320D: tip = pad 4, ring = pad 3, sleeve = pads 1 and 2.

## Pins verified from the CH32X035 datasheet V2.3 (QFN-28 diagram + pin table)
| Signal | Pin | Port |
|---|---|---|
| USB D- | 26 | PC16 / UDM |
| USB D+ | 27 | PC17 / UDP |
| USART1 TX | 21 | PB10 / TX1 |
| USART1 RX | 22 | PB11 / RX1 |
| SDI debug | 25 | PC18 / DIO |
| VDD | 2 | |
| GND | exposed pad | |
Free for EN / LED: PA0..PA7 (pins 3..11 area), PB0, PB3, PC0, PC3 - pick during layout.

## Verified chip facts (datasheet V2.3)
- QingKe V4C RISC-V, 48 MHz internal RC oscillator; no external crystal in the clock tree.
- 62 KB flash, 20 KB SRAM, VDD 2.0 to 5.5 V.
- One USB 2.0 full-speed controller, host or device; its 48 MHz clock comes from the internal HSI.
- USB PD / Type-C controller on PC14/CC1 (pin 28) and PC15/CC2 (pin 1) - not used here (J2 is passive).

## Open items (must be checked before ordering)
1. (closed) J1: datasheet read, PCB 0.80 mm, footprint from EasyEDA.
2. (closed) jack: PJ-320D C521460, 4-pole, pin map verified.
3. (closed) The X035 host port has internal D+/D- pull-downs: R8_UHOST_CTRL bit 7 RB_UH_PD_DIS, 0 = enabled
   (reset value 1). R5/R6 stay as DNP footprints; firmware clears the bit.
4. USB PHY supply: datasheet gives VDD 2.0-5.5 V and no separate PHY rail was found. Design runs the chip
   at 3.3 V; confirm in the RM that USB host works at 3.3 V VDD (device examples run at 3.3 V).
5. Does the stock/Melodee FM-1 attach as a plain full-speed device? (JieLi USB is HS-capable; a HS device
   must fall back to FS on an FS host - standard behavior, but test on the first prototype.)

## Firmware plan (not started)
- Base: openwch/ch32x035 EVT/EXAM/USB/USBFS/HOST_KM (host enumeration, descriptor fetch, interrupt IN polling).
- Add: parse the config descriptor for interface class 0x01 subclass 0x03 (MIDI Streaming); the FM-1 is a
  composite device (audio + MIDI), skip the audio interfaces; take bulk IN and bulk OUT.
- Loop: poll bulk IN, unpack 4-byte USB-MIDI event packets to serial bytes on USART1 at 31250 baud;
  parse USART1 RX (running status) into USB-MIDI packets on bulk OUT.
- PB9 (OUT_SEL) push-pull. v5 (inverted against v4): LOW = MIDI OUT jack carries the MCU's MIDI (U5 B1 = TX),
  HIGH = hardware THRU (U5 B2 = opto output). R13 pulls it HIGH through reset, so a blank or crashed MCU still passes
  MIDI IN to OUT.
  How the user switches modes (a SysEx, a long press, a saved setting) is a firmware decision.
- Re-enumerate on detach. Enable U3 only after power is stable; LED = connected.
- Toolchain: MounRiver Studio or riscv-none-elf-gcc; flash with WCH-LinkE.

## Cost (fetched LCSC prices; PCB and passives estimated)
- Parts per board: about 2.05 USD at 5 boards, about 1.10 USD at 1,000.
- Five hand-assembled boards: about 13 USD + shipping (PCB ~2 USD estimated).

## KiCad files (2026-10-17)
- `fm1-midi-dongle.kicad_sch` + `.kicad_pro`: generated by `tools/gen_sch.py` from this document. KiCad 10 opens it;
  `kicad-cli sch erc fm1-midi-dongle.kicad_sch --severity-all` reports 0 violations. Netlist checked against the
  block diagram above (21 nets, 33 symbols). Every connection is a net label on a stub: correct first, pretty later.
- `fm1_dongle.kicad_sym` + `sym-lib-table`: project library with the SY6280AAC symbol (KiCad has none).
- Each symbol carries an `LCSC` field for the JLCPCB/LCSC BOM, and a `Note` field where something must be verified.
- Regenerate after editing the generator: `python3 tools/gen_sch.py`. Hand edits in KiCad are fine too, but then
  stop using the generator.

## Built for JLCPCB assembly (2026-10-17)
- PCB: 4 layers (see floorplan), **0.8 mm** (the USB-C plug clamps the board edge; its datasheet says T = 0.80 +/- 0.05 mm),
  all parts SMD on the top side. JLCPCB Economic PCBA accepts 0.8 mm boards; the plug itself is "Standard
  assembly only" in JLCPCB's library, so a JLCPCB-assembled run is Standard. First five are hand assembled.
- Footprints for every IC and connector come from EasyEDA/LCSC for the exact LCSC number (easyeda2kicad),
  in `fm1_dongle.pretty` with 3D models in `fm1_dongle.3dshapes`; the plug and jack symbols too
  (`tools/easyeda/`). Passives use KiCad's 0603 / SOD-123 footprints.
- `tools/export_jlc.sh` writes `production/bom_jlcpcb.csv` (Comment, Designator, Footprint, LCSC Part #).
  The placement file (CPL) comes from the PCB once it is laid out.
- Jack changed from PJ-320B (its LCSC/EasyEDA entry is a dummy footprint marked "not a PCB-soldered
  part") to **PJ-320D C521460**, a 4-pole SMD jack with a real footprint, Economic assembly, 2,945 in stock.
  Pin map from the USAKRO drawing cross-checked against KiCad's named PJ320D footprint (same hole spacing
  and pad positions): 1 sleeve, 2 ring2, 3 ring1, 4 tip. A TRS plug: tip = 4, ring = 3, sleeve touches 1 and 2.

| Ref | Footprint | Source |
|---|---|---|
| U1 | fm1_dongle:QFN-28_L4.0-W4.0-P0.40-BL-EP2.8 | EasyEDA C7437027 (4x4 mm, 0.4 mm pitch per datasheet; EP 2.8) |
| U2 | fm1_dongle:SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR | EasyEDA C5446 |
| U3 | fm1_dongle:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL | EasyEDA C55136 |
| U4 | fm1_dongle:SOP-6_L8.5-W6.4-P2.54-LS9.2-BL | EasyEDA C899473 |
| J1 | fm1_dongle:USB-C-SMD_TYPE-C-24P-GTJB-040 | EasyEDA C3151751; pads A row on F.Cu, B row on B.Cu, shell pads 25/26 |
| J2 | Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12 | KiCad library footprint made for this exact HRO part |
| J3, J4 | fm1_dongle:AUDIO-SMD_PJ-320D | EasyEDA C521460 |
| R, C, D1, D2 | KiCad 0603 / SOD-123 | |
| TP1-3 | TestPoint:TestPoint_Pad_1.5x1.5mm | bare pads for the LinkE wires, no part, not in the BOM |

Added in the schematic beyond the BOM list: R12 100k pull-down on VBUS_EN (VBUS stays off until firmware
enables it; SY6280 says EN must not float), C5 100 nF at the optocoupler.

## PCB floorplan v4 (2026-10-18, `tools/gen_pcb.py`) - single-sided, placement only, routing is the owner's
v3 had 11 parts on the back (two reflow passes, the receptacle made the stick rock, its shell slots perforated the
GND plane beside the MCU and USB pair, MIDI_RX ran 22 mm across the board). v4 puts every part on the top face.
Board 20.0 x 37.7 mm (was 26), 4 layers (F.Cu parts / In1 GND plane / In2 +3V3 plane / B.Cu free routing), 0.8 mm.
Not routed. Self-check (pads, bodies, courtyards, holes, edge): 0 issues. DRC: no courtyard or clearance errors;
only silk clipped where J2 and the jack noses overhang the edge (by design), the unrouted ratsnest, and the 3V3
plane reported isolated until it gets its vias.

The MCU's pins decide the halves: VDD 2 / VBUS_EN 5 / LED 6 face left, TX 21 / RX 22 / DIO 25 face right and up.
1. USB pair: unchanged, CH32X035 directly under the plug, pins 27/26 face A6/A7, 2.6 mm straight on F.Cu over In1.
   Nothing with a hole within 6 mm of it.
2. Power (left): SY6280 beside the plug's top-face VBUS pad A4 (schematic now ties A4/A9/B4/B9 all to VBUS_FM1),
   C3 and the CC Rp R1 in the free corner left of the tongue, LDO + C1/C2 below, C4 vertical against pin 2,
   J2 below them with its mouth on the LEFT edge and R2/R3 beside its CC pads.
3. MIDI (right): LinkE pads TP2 (DIO) and TP1 (3V3) in the free corner right of the tongue, TP3 (GND) beside the
   MCU; opto above the MIDI IN jack, pin 4 up toward the MCU with R10 above it, C5 above pins 5/6; R9 and D1
   between the opto's LED pins and the jack's tip pad.
4. Jacks swapped: MIDI IN is now the right jack (J4) because its tip/ring pads sit at the board centre under the
   opto; MIDI OUT (J3) is left with R7/R8 right above its tip/ring pads at the edge.
5. Two-pin parts are turned so each signal pad faces the pads it connects to (GND/3V3 pads face away, toward
   their plane via); the generator does this for every R/C/D and prints which ones it flipped.
6. Mechanics: 10 mm jack pitch, jack noses 2.1 mm out, J2 1 mm out on the left edge, nothing in the plug clamp
   zone, back face flat (only the plug's B-row pads, shell/jack pegs and the EP vias).

Ratsnest (minimum spanning tree per net, v4 vs v3): every net single-sided now (v3: 8 nets crossed sides).
USB 2.6 / 2.6 mm (same); MIDI_RX 12.7 (was 22.3); OPTO_A 4.4 (11.4); CC1/CC2 2.2 (4.7); ISET 2.8 (6.1);
SDI_DIO 6.3 (9.3); MIDI_TIP_OUT 3.3 (7.0). Trade-off: MIDI_TX 22 mm (was 5.4), pin 21 to R7 at the jack - chosen
so the jack-side stub after the series resistor is short; at 31.25 kbaud the long run is harmless, and it can go
on B.Cu over the GND plane.

Open points for rev B: ESD array at the connectors, two fiducials if JLCPCB assembles, the QFN EP via-in-pad
(0.2 mm, plug/tent or move them out to avoid solder wicking).

## Routing v4 (2026-10-18, `tools/route.py`, owner asked for it)
Run: `python3 tools/gen_pcb.py && python3 tools/route.py` (route.py refuses an already-routed board: deleting tracks
through KiCad 10's Python bindings segfaults). Rules from the pcb-house-rules skill + `house_rules.yaml` override.
- Every track is an explicit polyline: orthogonal runs, every bend a short 45 deg (longest 1.41 mm), no 90 deg corners,
  no any-angle. `check_routing.py`: 86 % orthogonal / 14 % 45 deg by length.
- No loops: `tools/check_loops.py` counts edges - nodes + groups per net over tracks/vias/pads: 0 on every net.
- Widths 0.2 signal, 0.3 power next to fine-pitch pads, 0.5 power. Vias 0.6/0.3 signal + GND stitching, 0.8/0.4 power.
- In1 GND plane, In2 +3V3 plane, GND pours on F.Cu and B.Cu, +5V_IN as a B.Cu pour on the power side.
- B.Cu nets: MIDI_OUT_DATA (U5 A to R7 at the jack, down the right side), MIDI_TX (pin 21 to U5 B2, under
  OUT_SEL), CC_FM1 (A5 is boxed in by A4's VBUS stub), VBUS_EN
  (U3's IN pin sits between pin 5 and U3's EN pin).
- VBUS_FM1 reaches the plug on A4 (top) and B4/B9 (back, one 0.8/0.4 via + a B.Cu link). A9 is NC: it sits right
  of the USB pair and DIO/RX must pass under it. 3 of 4 contacts, ~0.33 A each at the 1 A limit.
- DRC: 0 unconnected, 0 clearance errors. Accepted: 6 copper-to-edge on the plug's own GND pads beside the tongue
  notches (the plug drawing), 1 width warning (+3V3 0.2 mm out of QFN pin 2: a 0.3 mm track cannot leave a 0.4 mm
  pitch pin with clearance). 24 text-height warnings: designators at 0.8 mm (owner's choice, see Silkscreen).
- Review renders: `docs/pcb_route.png` (tools/render_route.py), `docs/pcb_nets.png` (ratsnest, placement).

## Outline, case mounting, silkscreen, 3D (2026-10-18)
Full pipeline: `python3 tools/gen_pcb.py && python3 ~/.claude/skills/pcb-house-rules/scripts/apply_rules.py
fm1-midi-dongle.kicad_pro --layers 4 && python3 tools/route.py && python3 tools/silk.py`.
- Outline: no sharp convex corners. Far corners r 1.0, top corners r 0.75 (TP1's pad keeps 0.5 mm to the edge),
  plug shoulders and tongue tip r 0.25. The tongue notches' inner corners are left to the router bit.
- Case mounting (owner chose captured, no screws): the board drops into a pocket in the case bottom and the lid
  clamps it (ribs on the jack tops). Unplug load: the top shoulders (y = -1.97, x = +/-4.45 .. +/-10) bear on the
  case's front wall. Plug-in load: the jack fronts (y = 35.7) bear on the back wall. Two half-moon locating notches,
  r 0.6 with 0.3 mm fillets, on both side edges at y = 22.2 (case pins d ~1.1 printed); that band between J2/D1
  and the jacks is the only one free on both edges, and R7's pad keeps 0.5 mm to the left notch. Back face is flat
  (only the plug's B-row pads). Openings needed in the case: plug (front), J2 mouth (left, 1 mm overhang), jack
  noses (back, 2.1 mm out).
- Silkscreen (`tools/silk.py`): the library silk is replaced by one style: body outlines (EasyEDA courtyard = body,
  KiCad F.Fab) clipped 0.2 mm from mask openings and holes and 0.3 mm inside the edge, pin-1 dots on U1-U4,
  cathode brackets on D1/D2, no outline on R/C (U5's dot is 0.3 mm: C5 leaves 0.7 mm beside its pin 1). Designators 0.8 x 0.8 mm, 0.15 stroke (owner's choice; JLC's
  standard legend minimum is 1.0 mm, 0.8 only on their high-precision legend), placed most-constrained first, at
  least 0.15 mm from pads, never closer to another part than to their own: 24 of 27 fit (U4's inside its own
  outline since 2026-10-19, U5 took the spot above it), R7, R11, U2 stay on F.Fab (assembly drawing). Test pads labelled 3V3 / DIO / GND. Back: board name, revision, MIDI OUT / MIDI IN
  under the jacks, TRS type A, 5V IN at J2. Old silk is stripped from the file text, since removing it through
  the SWIG API corrupts the heap.
- 3D: the plug's EasyEDA WRL had every material at transparency 1.0 (invisible); set to 0. J2's EasyEDA model
  offset fixed to -0.80 mm (its shell legs now sit in the footprint's SH holes; it was 2.2 mm off). The KiCad 3D
  library is not installed, so the R/C/LED 0603 and SOD-123 STEP models are vendored in `fm1_dongle.3dshapes`
  (KiCad 3D library, CC-BY-SA 4.0) and gen_pcb.py points those footprints at them.
- Renders: `docs/pcb3d_{top,bot,iso}.png`, `docs/silk_{top,bot}.png`.

## Hardware MIDI THRU (2026-10-19, owner asked for it)
Owner chose: the OUT jack switchable between OUT and THRU (no third jack, outline and case unchanged), selected
by an MCU pin.
- U5 SN74LVC1G3157DCKR (TI, LCSC C38663, SC-70-6, Extended). Pin map and logic from TI SCES424O (June 2025),
  table 4-1 and function table 7-1: 1 B2, 2 GND, 3 B1, 4 A, 5 VCC, 6 S; S low connects A to B1, S high A to B2.
  Ron <= 25 ohm at VCC 3 V: adds to R7's 10 ohm in the tip line (MIDI 3.3 V type A sink current drops a few %).
- B1 = MIDI_RX (H11L1 output with R10 pull-up): in THRU the OUT jack's tip follows the opto with no firmware
  and no added delay beyond the opto (~us); the MCU still receives MIDI IN on PB11 at the same time.
  B2 = MIDI_TX (PB10). A = MIDI_OUT_DATA -> R7 -> J3 tip. S = OUT_SEL = PB9 (pin 20, plain I/O, datasheet V2.3
  pin table), R13 100k to GND (same part as R12, no new BOM line).
- THRU only works while the dongle is powered (the jack's ring is fed from 3.3 V either way).
- Layout: U5 sits in the old TP3 corner between the MCU and the opto (top row S / VCC / A, bottom row
  B2 / GND / B1): B1 drops straight into U4 pin 4, GND into U4 pin 5, A leaves by a via down the right side on
  B.Cu, TX comes in from a via under OUT_SEL. C5 moved under U5 (its pads straight over U4 pins 6 and 5); R13 sits
  under the RX trunk. TP3 (GND LinkE pad) moved to the free pocket between J2, R9 and the jacks, labelled GND.
- Checks after the change: ERC 0, DRC 0 unconnected and only the 6 accepted-pending J1 edge items,
  check_routing clean (0 any-angle), 0 loops, gen_pcb placement issues 0.

## v5: USB-A host port on the bottom face (2026-10-20, owner asked for it)
Why: a USB-A receptacle takes the cable every class-compliant synth/controller ships with (USB-A to B, micro-B
or C), so the dongle works with more synths than the FM-1. The owner chose the bottom face so the PCB does not
grow: the board is still 20 x 37.7 mm.

- **J1 = Jing Extension 911-321B2028S10100, LCSC C42474** (owner's pick over the fully-SMD C8328): 10.0 mm deep,
  6.9 mm tall, 4 SMD signal pads (2.00 / 7.00 mm pitch) and 4 through-hole shell legs (12.80 x 6.00 mm) that stick
  ~0.65 mm out of the 0.8 mm board's top face. Footprint and 3D from EasyEDA; pads checked against the datasheet
  drawing; the EasyEDA 3D model was 3.74 mm forward of the pads and is offset back in the footprint.
- Mounted on B.Cu, mirrored top-to-bottom, mouth up: D+ (pad 3) left, D- (pad 2) right, same order as the MCU's
  pins 27/26, so the pair does not cross. VBUS (pad 1) is on the right, GND (pad 4) on the left.
- Shell front 0.8 mm past the top edge (keeps the front legs' copper 0.5 mm from the edge).
- Netlist: plug, CC_FM1 and R1 (56k Rp) removed; VBUS_FM1 renamed VBUS_HOST; C3 now 10 uF 25 V (C96446, Basic)
  as host-port bulk, so a hot-plugged synth does not brown out the 5 V input. USB 2.0 asks a downstream port for
  120 uF; 10 uF is the usual small-host compromise (not verified against a USB-IF test).
- Assembly: J1's SMD pads are on the bottom (bottom stencil) and its legs need through-hole soldering, so JLC
  Standard PCBA stays (it was Standard already for the v4 plug).

### Floorplan v5 (placement only, NOT routed)
- Top band (y < 1.4) freed by the plug, between the front shell legs: U3 SY6280 at rotation 90 (EN / IN face the
  left gap, OUT / ISET face right), R4 right of it, C3 standing up, TP2 (DIO). TP1 stays in the top-right corner.
- VBUS_HOST plan: U3 OUT -> F.Cu at y ~0.4 under R4 -> C3 -> via -> B.Cu down to J1 VBUS (x 3.5).
- USB plan: MCU pins 27/26 -> vias at (-/+0.75, 1.6) -> B.Cu lanes at x -1.2 / 0.9 inside J1's 1.4 mm pads.
  The MCU's exposed-pad GND vias moved to two columns clear of both lanes.
- Right column (x > 7.4, outside the right legs): TP1, R10, U5 (THRU switch).
- (superseded by the routing pass below: U5, R10, R12, R13, C5, TP3 and the opto block moved again)
- Checks: `tools/gen_pcb.py` 0 placement issues (layer-aware: top parts vs J1's legs only; legs as real slots);
  KiCad DRC on the unrouted board: only silk-to-edge (library silk, regenerated by silk.py after routing) and the
  4 unconnected EP vias. Routed afterwards, see "Routing v5".

### Schematic v5
- Power and ground are KiCad `power:` symbols (GND, +3V3, +5V as +5V_IN, VBUS as VBUS_HOST); signals stay labels.
- No overlaps: gen_sch.py places reference/value outside each symbol and fails on any overlap of symbols,
  labels, power ports and texts (check_overlaps). Clean symbols drawn for SY6280, SN74LVC1G3157, USB-A and PJ-320D.
- ERC 0.

### Routing v5 (2026-10-20, `tools/route.py`, hand-written polylines, no autorouter)
The right rear shell leg of J1 left no room for the v4 THRU block, so the routing pass moved parts first:
- U5 (THRU switch) now sits in a band under the MCU, made by moving the opto U4 down 2.1 mm (R9, D1 1.5 mm with it).
  **U5 inputs swapped:** B2 (pin 1) = MIDI_RX straight above U4's output pin, B1 (pin 3) = MIDI_TX, and **R13 is now a
  pull-UP** to 3V3. Hardware THRU is still the default (blank / reset MCU: OUT_SEL high = B2 = opto output); firmware
  drives PB9 LOW to send its own MIDI. Same parts, same BOM.
- R10 (RX pull-up) in the right column, R13 beside the MCU's pin 20, C5 in the U5 band (feeds U4 pin 6 and U5 VCC).
- TP3 (GND LinkE pad) moved to the empty top-left corner: all three SDI pads (GND, DIO, 3V3) are on the top edge.
- Lanes leave the MCU's top-right corner in a fixed order so nothing crosses: DIO (y 1.45, up into TP2), RX (y 1.85,
  out to x 9.25, down the right edge into U4 pin 4, then up into U5 B2), TX (y 2.25, down the corridor right of J1's
  rear leg into U5 B1). OUT_SEL drops to B.Cu at R13 and comes up beside U5's S pin. U5's A output goes to B.Cu and
  runs down the right edge, then along y 21.45 to R7, as in v4.
- USB: pins 27/26 -> vias at (-1.0, 1.6) / (-0.25, 1.0) -> B.Cu straight down into J1's D+/D- pads (lanes x -1.0 and
  0.8, clear of the MCU's exposed-pad vias). VBUS_HOST: U3 OUT -> F.Cu (0.5 mm) under R4 -> C3 -> via -> B.Cu -> J1 VBUS.
- +5V_IN as a B.Cu pour on the power side (as v4); In1 GND and In2 3V3 planes; GND pours on F.Cu and B.Cu.
- J1's four shell legs and D2 pin 1 are solid-connected to the pour (one-spoke pockets between lanes).
- Checks: KiCad DRC 0 unconnected, 0 clearance / short items. One `track_width` item: the 0.2 mm neck where +3V3
  leaves the MCU's VDD pin (0.4 mm pin pitch; 0.3 mm from 0.55 mm out). `check_routing.py` clean (87.5 % orthogonal,
  12.5 % short 45 deg, 0 any-angle, no 90 deg corners). `check_loops.py`: 0 loops on every net. 22 text_height
  warnings are the 0.8 mm designators (owner's choice). Schematic parity shows only the generator's known
  footprint-library / field / net-name items.
- Silkscreen: 19 designators + 3 SDI labels on silk; D1, R11, R7, C2, R4, J3 only on F.Fab (no room at 0.8 mm).
- The J1 GND-pad copper-edge items from v4 are gone with the plug.
