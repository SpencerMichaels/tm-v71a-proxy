# Kenwood TM-V71A proxy — native KiCad Rev A

> **Rev A as built, kept for reference.** Rev A's two data lines are swapped relative to the radio (body transmits on cable pin 3, head on pin 4; see [docs/protocol.md](../docs/protocol.md)). A built board needs the rework in [REWORK.html](REWORK.html), and the firmware's default `REV=A-rework` build. The notes below describe the original design intent, including the swapped pin mapping. For a new board use Rev B on the `main` branch.

Open `kenwood_proxy.kicad_pro` in KiCad 10. The schematic and routed 2-layer PCB are ready for an OSH Park prototype order (see [fab/ORDERING.md](fab/ORDERING.md)). Design decisions and rationale are in [KENWOOD_PCB_DESIGN_HANDOFF.md](../../KENWOOD_PCB_DESIGN_HANDOFF.md).

## What the board does

- **Pass-through.** Two Würth 615004143821 4P4C jacks (J1 body, J2 head). PB and GND pass straight through in copper. HEAD_TXD goes to BODY RX as direct copper; the MCU only listens to it (TAP_HEAD through R7 10 kΩ, for logging).
- **Full proxy, body→head.** The body's TXD goes only to the MCU (TAP_BODY through R6 10 kΩ). The MCU retransmits every byte to the head on USART1 TX through R2 (470 Ω), rewriting brightness packets on the way. Nothing else connects body TXD to head RXD except the JP1 recovery jumper.
- **Idle and reset behavior.** The head's RX input has its own 47 kΩ pull-up. While the MCU is in reset, being programmed, or removed, the head line idles high and the display keeps its last content. It gets no new data until the MCU runs.
- **JP1 hard bypass.** Leave it open. Recovery only: **remove U1 and fit the shunt**, which connects body TXD straight to head RXD. Fitting JP1 while U1 runs makes the MCU and body fight: no damage (simulated peaks are 10 mA at the AVR pin and 5 mA at the body driver), but garbled data.
- **Recovery.** Pull U1 from its socket and fit the JP1 shunt. If the board itself is suspect, replace it with a **straight-through** 4P4C coupler. Many RJ9/RJ11 couplers are reversed (1→4), which would put PB on the head's RX pin, so check continuity first. A spare OSH Park board fitted with only J1, J2 and a JP1 shunt (or wire) is a known-good coupler.
- **PB supply.** The radio's PB line (about 10 V from the radio's own regulator) feeds R1 150 Ω 1 W, an RC filter (C6, C5) and the LM2936Z-5.0 regulator, giving 5 V for a socketed AVR128DB28. The board never takes power from truck wiring. R1 limits current into a board fault and isolates MCU noise from PB; the voltage across R1 divided by 150 gives board current.
- **ILL sensing (lights on/off only).** Wire J3 (Molex Micro-Fit 3.0, latching; pin 1 ILL+, pin 2 GND) to **ILL+ (TAIL) and a chassis ground**, for example the ground wire in the stereo harness.
  - With the lights on, ILL+ sits at a steady 11–14 V, the SFH617A-3 LED conducts and ILL_SENSE reads low. With the lights off, ILL+ is below 1 V and ILL_SENSE reads high.
  - The optocoupler keeps the truck wiring isolated from the radio ground (nets ILL_P, ILL_GND, ILL_LED_A).
  - Simulated: reads low at 0.36 V or less down to 9 V, reads high at 5.0 V with ILL+ up to 2 V, and is safe with reversed wiring (D1), 24 V and a 40 V load dump (R9 0.5 W).
- **Programming header.** J4 is a 1×3 0.1 in header: 1 GND, 2 UPDI, 3 DBG_TX (through R13). It is for bench programming and packet logging before the board goes behind the dash. Use an Adafruit UPDI Friend or similar 5 V SerialUPDI adapter on GND + UPDI, and a separate 5 V USB-serial adapter's RX on DBG_TX for logging. The board is powered by the radio cable while programming; never connect adapter power.

## MCU pin plan (AVR128DB28 SPDIP-28, DS40002247B table 3-1)

| Pin | Port | Function |
|---|---|---|
| 23 / 22 | PA1 / PA0 | USART0 RX ← TAP_BODY; TX → DBG_TX (radio baud) |
| 3 / 2 | PC1 / PC0 | USART1 RX ← TAP_HEAD (logging); TX → HEAD_TX_MCU → R2 → head RX (proxy output; normal polarity, idle high) |
| 16 / 17 | PF0 / PF1 | 32.768 kHz crystal, OSCHF auto-tune |
| 7 | PD1 | ILL_SENSE (digital input: low = lights on) |
| 19 | UPDI | J4 pin 2 |
| others | PA2–PA7, PC2–PC3, PD2–PD7 | Unconnected: enable internal pull-ups or disable their input buffers |

Enable crystal auto-tune before relying on the UARTs. Without it, the internal oscillator is only ±5% below 0 °C and ±3% at 60–85 °C (datasheet figure 39-2), which is marginal for 8N1 with the AVR both receiving and transmitting. Suggested core clock is 10 or 20 MHz, whose harmonics stay clear of 144–148 MHz.

**Firmware pin configuration.** Default Schmitt input levels work on all pins (simulated margin on the taps is at least 0.82 V). Set the SUT fuse short (0–1 ms) so the proxy starts forwarding quickly after power-up.

## Firmware behavior: proxy and day/night brightness memory

Public reverse engineering ([KK4HEJ](https://kk4hej.wordpress.com/decoding-the-tm-v71a-display-protocol/)) describes 57,600 8N1, `0x0D`-terminated messages and `0x33 '0'..'8' 0x0D` for brightness. Radio→panel messages set state, and no ACK or retry is documented. Firmware v1 is a **logger** that forwards bytes unchanged and copies both streams to DBG_TX, to confirm packet format, power-on behavior and timing before any rewriting is enabled.

- **Forwarding.** Each byte received on TAP_BODY is sent to the head right away. Added latency is about one byte time (0.17 ms).
- **Rewriting brightness.** When a byte after `0x0D` is `0x33`, the next byte (the level digit) is replaced by the stored slot for the current lights state. No buffering is needed. The firmware still records the body's original digit.
- **Inserting a packet.** On a lights change or at power-on, the firmware sends its own brightness packet right after the next `0x0D` it forwards. Body bytes that arrive meanwhile go into a small ring buffer (64 bytes is ample; an insert is 3 bytes) and are forwarded right after. The backlog drains at the next idle gap. Collisions are impossible by construction.
- **Learning.** A body brightness packet whose level differs from the last level the body sent is a user menu change. It is saved to the slot for the current lights state. The head already shows it, so nothing is inserted.
- **Re-broadcasts are not learning.** If the body re-sends its unchanged level, for example at power-on, the slot is left alone and the stored value is substituted in flight. Without this rule, a power-on re-broadcast at night would overwrite the night slot with the body's value. The body's last level is kept in EEPROM too, so the rule holds across power cycles.
- **Lights input.** Filter ILL_SENSE for about 50 ms, which covers relay bounce and still looks instant. A cranking sag can at worst cause one brief day/night blink.
- **First use.** Empty slots (0xFF) mean no rewriting, so the radio behaves normally until each slot has been set once.
- **EEPROM.** The AVR128DB28 has 512 bytes rated for 100k writes. Write only after the level has been stable for about 2 s, so stepping through the menu costs one write. Twenty changes a day lasts more than ten years.
- **Menu quirk.** The body's menu starts from its own last value, not the substituted one. The head shows each step live, and the last value is saved, so the result is what was seen.
- **Watchdog.** Enable the WDT; it costs nothing. A reset only pauses forwarding for milliseconds.
- **Standby current (to check).** If PB stays live while the radio is off (the head must power its own on key), the board draws about 4.5 mA continuously. Firmware can sleep while the body is silent and wake on USART start-of-frame detection.

## PCB layout

- **Board.** 54 × 52 mm, 2 layers, all through-hole, for hand assembly on OSH Park bare boards. 26 soldered parts plus the DIP socket. TP2 is a bare plated GND pad for scope ground; every other probe point is a component lead.
  - J1 BODY, J2 HEAD and J3 (ILL+/GND) are all on the top edge, so every connection used in normal operation is on one edge. The jack mating faces are flush with the edge.
  - J4 (programming header) is at the bottom left; the power section (R1, C6, C5, U2, C4) runs along the bottom.
  - Four M3 holes, one in each corner.
- **Routing.** Autorouted with Freerouting 2.1.0, plus hand-routed ILL nets.
  - PB, PB_FILT and +5V are 0.6 mm; signals are 0.3 mm; ILL nets are 0.4 mm.
  - GND pours on both layers, with about 95 GND stitching vias on a 3 mm grid. These also tie trace-enclosed pour fragments to the other layer.
  - The ILL region (top right, outlined on silk) has no pour and no foreign tracks. `kenwood_proxy.kicad_dru` enforces at least 2.0 mm between ILL nets and all other copper (functional isolation for 12–14 V); the layout gives about 2.5 mm.
- **Checks.** KiCad DRC with schematic parity: 0 violations, 0 unconnected, 0 parity errors (`checks/pcb-drc.json`).
- **Outputs.** `checks/pcb_layout.pdf` (top, bottom mirrored, assembly; 1:1, centred on A4 landscape). `checks/pcb-F.svg` and `checks/pcb-B.svg` are layer views. `checks/board_top_1to1.pdf` is a 1:1 silk and fab plot with pad outlines; print it at 100 % for a part-spacing check.
- **Rebuilding.** `build_board.py` (run with KiCad's Python) rebuilds the board from the netlist. Without `--session` it writes `checks/placement.dsn`. Route that with `java -jar tmp/freerouting-2.1.0.jar -de placement.dsn -do routing.ses -mp 40 --gui.enabled=false`, then run `build_board.py --session checks/routing.ses`. Regeneration overwrites manual PCB edits.
- **Jack footprint.** Pad, peg and body geometry match Würth's official KiCad footprint `J_Wurth_WR-MJ_615004143821` from [WurthElektronik/KiCad-Library](https://github.com/WurthElektronik/KiCad-Library), rotated 180° and with 1.5 mm pads instead of 1.4 mm. A copy is in `sources/`.
- **Fabrication outputs.** `fab/kenwood_proxy_revA_oshpark_gerbers.zip` (Gerbers + Excellon drill for OSH Park), `fab/BOM_purchasing.csv`, `fab/BOM_upload_digikey_mouser.csv`; see [fab/ORDERING.md](fab/ORDERING.md).

## Installation assumptions

- **Body cable:** body → board 4P4C cable, 4 m (about 200–260 pF per data wire).
- **Head cable:** board → faceplate bridge cable, about 0.3 m (about 15–20 pF).
- **Simulation:** this installation is the "as installed" corner (260 pF / 20 pF), bracketed by 100/100 pF and 470/470 pF corners.
- **Radio supply:** permanently fed from constant battery, so PB is present whenever the radio has DC.

## Files

- `build_schematic.py` generates the native schematic, local symbol library and `design_intent.json`. **Re-running overwrites GUI edits.**
- `check_design.py` exports the KiCad netlist and ERC, then checks pin-level netlist parity, jack mapping, PB containment, proxy-path topology, ILL isolation, the MCU pin plan and hand calculations. Results go to `checks/design_checks.json`. Current status: ERC clean, 23/23 checks pass.
- `simulation/` and [simulation_review.md](simulation_review.md): ngspice behavioural verification (0 failures, PASS_WITH_MODEL_LIMITATIONS).
- `checks/schematic.pdf` and `checks/bom_kicad.csv` are KiCad exports.
- `footprints/Kenwood_Proxy.pretty/` holds the hand-written jack footprint.
- `sources/` holds the datasheets used: Würth jack, AVR DB, LM2936, SFH617A and AB26TRB.

## Loose items not shown as symbols

| Item | Qty |
|---|---:|
| Machined DIP-28 0.3 in socket, Mill-Max 110-43-328-41-001000 | 1 |
| 2.54 mm shunt for JP1, kept loose for recovery, e.g. Samtec SNT-100-BK-G | 1 |
| Micro-Fit 3.0 2-circuit receptacle with pre-crimped 22 AWG leads for J3 (Molex 43025-0200, or a pre-crimped kit) | 1 |
| Adafruit UPDI Friend (or similar 5 V SerialUPDI adapter) | 1 |
| 5 V USB-serial adapter for logging (RX only) | 1 |

## Open items

1. **Interface levels (service manual).**
   - Page 84: body TXD leaves TC74HC4050 IC951 through **R956 1 kΩ** to J952-4. Body RXD enters through **R953 1 kΩ** with a 47 kΩ pull-up.
   - Page 74: the head RX input is a TC4S81F gate with a 47 kΩ pull-up (CP913) and varistor D988.
   - Resulting levels: proxy low at head 0.06 V; JP1 bypass low 0.11 V; JP1 fitted with U1 running, 3.5 mA steady contention.
   - Limits used: TC4S81F VIL is the 4000-series 1.5 V maximum at 5 V, taken from DigiKey's listing because the Toshiba datasheet was unavailable. The HC4050 recommended output current is ±4 mA (absolute maximum ±25 mA), from typical 74HC data.
2. **Unmeasured quantities.** PB current (about 4.5 mA simulated, AVR at 4.4 mA, 20 MHz); radio baud rate and packet format (the logger firmware confirms these).
3. **Enclosure.** Mounting holes suit a nonconductive enclosure with cable strain relief.
