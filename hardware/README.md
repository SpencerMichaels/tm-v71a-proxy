# Hardware: Rev B

The KiCad 10 project for the proxy board: a 54 × 52 mm, 2-layer, all-through-hole board for hand assembly.

| File | What |
|---|---|
| `kenwood_proxy.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | The KiCad project, with three schematic sheets |
| `fab/` | Gerbers (OSH Park zip), BOMs, [ordering notes](fab/ORDERING.md) |
| `enclosure/` | 3D-printable case: STL, STEP and the generator; see its [README](enclosure/README.md) |
| `checks/` | Schematic PDF, layout PDF (1:1), ERC/DRC reports, design-check results, netlist |
| `build_schematic.py`, `build_board.py`, `check_design.py` | Scripts that generate and check the design (see [Rebuilding](#rebuilding)) |
| `simulation/`, [`simulation_review.md`](simulation_review.md) | ngspice checks of the interface, ILL input and power networks |
| `footprints/`, `Kenwood_Proxy.kicad_sym` | Project footprint (4P4C jack) and symbol library |

**Rev B status.** Rev B is Rev A with three changes:
- the data-line fix
- the J5 tap header
- a long-lead crystal

The design has been verified on a **reworked Rev A board** in a vehicle, and the firmware is the same. Rev B itself hasn't been fabricated yet. It passes ERC, DRC with schematic parity, and the design checks.

## Circuit

| Block | What it does |
|---|---|
| **Pass-through** | J1 (BODY) and J2 (HEAD) are Würth 615004143821 4P4C jacks. PB (pin 1), GND (pin 2) and the head → body data line (pin 4) run straight through in copper. |
| **Proxy, body → head** | The body's data (J1 pin 3) goes only to the AVR, through R6 10 kΩ. The AVR re-sends every byte to the head (J2 pin 3) on USART1 TX through R2 470 Ω, rewriting brightness messages on the way. |
| **Idle and reset** | The head's input has its own 47 kΩ pull-up. While the AVR is in reset, being programmed or removed, the line idles high and the display keeps its last content. |
| **JP1 bypass** | Recovery only: **remove U1, then fit the shunt** to connect body data straight to the head. With U1 running, JP1 makes the AVR and the body fight over the line. Nothing is damaged (simulated peaks are 10 mA at the AVR pin and 5 mA at the body's driver), but the data is garbled. |
| **Power** | PB (about 10 V from the radio's regulator) → R1 150 Ω 1 W → RC filter (C6, C5) → LM2936Z-5.0 → 5 V. Draws about 5 mA. The board never takes power from vehicle wiring. R1 limits fault current, and the voltage across it ÷ 150 gives the board's current. |
| **Lights input** | J3 (Molex Micro-Fit 3.0, latching): pin 1 ILL+, pin 2 GND. R9 2.2 kΩ, R10 680 Ω shunt, D1 reverse protection, then an SFH617A-3 optocoupler. ILL_SENSE (PD1) reads low when the lights are on. The vehicle side is isolated from the radio's ground. |
| **J4: programming** | 1 GND, 2 UPDI, 3 DBG_TX (event log, through R13). |
| **J5: data taps** | 1 GND, 2 body → head (through R6), 3 head → body (through R7), 4 what the head receives (after R2). Listen only. |
| **Crystal** | Y1, 32.768 kHz, auto-tunes the AVR's internal 20 MHz oscillator, so the UART timing holds over temperature. |

**Lights input, simulated:**
- reads low (0.36 V or less) with ILL+ from 9 V upward
- reads high (5.0 V) with ILL+ at 2 V or below
- survives reversed wiring (D1), 24 V, and a 40 V load dump (R9 is rated 0.5 W)

## MCU pins (AVR128DB28, SPDIP-28)

| Pin | Port | Function |
|---|---|---|
| 23 | PA1 | USART0 RX ← body data, through R6 |
| 22 | PA0 | USART0 TX → DBG_TX on J4 pin 3 (event log, 57,600 baud) |
| 2 | PC0 | USART1 TX → R2 → head's data input |
| 3 | PC1 | head → body data, through R7 (logging only) |
| 7 | PD1 | ILL_SENSE (low = lights on) |
| 16 / 17 | PF0 / PF1 | 32.768 kHz crystal |
| 19 | UPDI | J4 pin 2 |
| 6, 14, 20 / 15, 21 | | 5 V / GND |
| others | PA2–PA7, PC2–PC3, PD2–PD7 | unused; the firmware enables pull-ups |

## Interface levels

Taken from the TM-V71A service manual; see [`docs/research/`](../docs/research/).
- **Body transmit:** a TC74HC4050 buffer through a 1 kΩ resistor.
- **Body receive:** through a 1 kΩ resistor with a 47 kΩ pull-up.
- **Head receive:** a TC4S81F gate with a 47 kΩ pull-up and a varistor.

Simulated against those values:
- the proxy's low level at the head is 0.06 V
- the low level through the JP1 bypass is 0.11 V
- JP1 fitted with U1 running gives a steady 3.5 mA of contention, which is safe

Cable corners from 100 pF to 470 pF were simulated: the default installation (a 4 m body cable, a 0.3 m head cable) plus those extremes.

## PCB layout

- **Edges:** J1, J2 and J3 sit on the top edge, with the jack faces flush. J4 is at the bottom left, J5 at the top left, and the power section runs along the bottom. There's an M3 mounting hole in each corner.
- **Routing:** Freerouting 2.1.0, plus hand-routed ILL nets.
  - Track widths: PB, PB_FILT and +5 V are 0.6 mm; signals 0.3 mm; ILL nets 0.4 mm.
  - GND pours on both layers, with stitching vias on a 3 mm grid.
- **ILL isolation:** the ILL area (top right, outlined on the silkscreen) has no pour and no other tracks. `kenwood_proxy.kicad_dru` enforces at least 2.0 mm from the ILL nets to all other copper, and the layout gives about 2.5 mm.
- **Checks:** DRC with schematic parity gives 0 violations, 0 unconnected and 0 parity errors (`checks/pcb-drc.json`). The design checks pass 25/25 (`checks/design_checks.json`).
- **Jack footprint:** matches Würth's official KiCad footprint `J_Wurth_WR-MJ_615004143821` ([WurthElektronik/KiCad-Library](https://github.com/WurthElektronik/KiCad-Library)), rotated 180° and with 1.5 mm pads.

## Rebuilding

The schematic and board are generated by scripts. Edit the scripts rather than the KiCad files: **re-running a script overwrites GUI edits.**

```sh
python3 build_schematic.py                       # schematic, symbol library, design_intent.json
python3 check_design.py                          # netlist + ERC + 25 design checks -> checks/
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$KPY build_board.py                              # placement -> checks/placement.dsn
java -jar freerouting-2.1.0.jar -de checks/placement.dsn -do checks/routing.ses -mp 40 --gui.enabled=false
$KPY build_board.py --session checks/routing.ses # import routing, pours, hand fixes
kicad-cli pcb drc --schematic-parity -o checks/pcb-drc.json kenwood_proxy.kicad_pcb
```

`build_board.py` hand-routes one PB link beside J4 that Freerouting leaves unrouted. The paths in it assume the macOS KiCad install; adjust them for other platforms.

## Possible future work

- **Follow the dash dimmer.** Wire J3 across ILL+ and ILL− instead of ILL+ and GND. The opto output then follows the dimmer's PWM, so the AVR could time the duty cycle and map it to brightness 0–8.
  - Reported automotive dimmer frequencies are 100 Hz–1 kHz, which the SFH617A and the 10 kΩ pull-up can follow, so this would be firmware-only.
  - The current firmware's 50 ms "stable" filter assumes a steady input, so it would need changing.
  - Measure the dimmer's frequency first.
- **Auto power-on** needs no hardware: the radio resumes its on/off state when DC returns, so an ACC-switched supply is enough.
