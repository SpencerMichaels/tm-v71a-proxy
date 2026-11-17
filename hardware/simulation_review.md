# Kenwood proxy simulation review, 2026-10-12

## Result

**PASS_WITH_MODEL_LIMITATIONS, 0 assertion failures.** The run covered 288 data-path transients, 20 DC operating points (ILL and faults) and 12 power operating points, and took 2.2 minutes. It uses ngspice 45.2 bundled with KiCad. The circuit comes from the exported KiCad netlist (`checks/netlist.xml`); its SHA-256 is recorded in the results JSON.

The board is **full proxy only**. Body TXD reaches the head only through the MCU: TAP_BODY via R6 10 kΩ in, and USART1 TX via R2 470 Ω out. JP1 is a recovery bypass. PB and GND pass straight through in copper. J3 is wired to ILL+ and chassis ground for lights on/off sensing.

This run follows the final minimality pass (RS1, TP1, R14 and the AUX pin removed; J4 now a 1×3 header; C6 now a 105 °C part of the same value). None of those changes touches a simulated path, and the results match the previous run.

## Data paths, 57.6 kbaud 8N1

There are 48 corners per mode:
- **Cable capacitance per data wire (body / head):** 100/100 pF, 470/470 pF (about 8 m each side), and **as installed** at 260/20 pF (4 m body cable, 0.3 m bridge).
- **Head varistor:** 20 or 100 pF.
- **Radio 5 V rails:** 4.75 or 5.25 V, with the board's 5 V rail at 4.85 or 5.15 V.
- **Body and head drivers:** strong or weak (25/100 Ω and 400/1500 Ω).
- **AVR output resistance:** 25 or 117 Ω.

Receiver thresholds are the guaranteed limits: TC4S81F and HC4050 VIL 1.5 V / VIH 3.5 V; AVR Schmitt (default input level) 0.2/0.8 VDD.

| Mode | Result, all corners | Worst head margin (all / as installed) | Worst edge skew at head (all / as installed) |
|---|---|---|---|
| Proxy (MCU forwards a rewritten stream) | head decodes the MCU stream | 1.35 V / 1.35 V | 0.26 µs / 0.07 µs |
| MCU in reset or tri-state | head idles high (at least 4.75 V); no garbage | — | — |
| MCU removed | head idles high (at least 4.75 V) | — | — |
| JP1 fitted, MCU removed (recovery) | body stream decodes at head | 1.25 V / 1.25 V | 0.87 µs / 0.33 µs |
| JP1 fitted with MCU running (misuse) | no damage: peak 5.0 mA at body driver (HC4050 abs. max ±25 mA), 10.3 mA at AVR pin; data garbled by design | — | — |
| LDO dead (fault) | head RX clamped to about 0.7 V through R2; display gets no data, as with any proxy failure | — | — |

- **Body isolated from head:** before the MCU starts forwarding, the body's own stream never pulls the head line below 4.85 V.
- **Head→body direct copper path:** decodes in every mode with at least 1.23 V margin (0.74 V with the LDO dead).
- **MCU taps:** both decode with at least 0.82 V margin (body 0.87 V, head 0.82 V) at the default Schmitt level.

## ILL input, as installed (J3 to ILL+ and chassis ground; R9 2.2 kΩ, R10 680 Ω)

- **Lights off (ILL+ 0, 1 and 2 V; CTR 0.24 and 2.0):** ILL_SENSE is 5.0 V (reads high).
- **Lights on:** ILL_SENSE is at most 0.36 V at 9 V with minimum CTR, and at most 0.14 V at 11 V or more. The AVR VIL is 0.97 V.
- **Reversed wiring (−14.5 V):** LED clamped to −0.66 V by D1; R9 0.09 W.
- **24 V continuous:** R9 0.23 W (rated 0.5 W).
- **40 V load dump:** R9 0.67 W while it lasts, 0.27 J for 400 ms; the opto LED carries 17 mA (60 mA abs. max).

## Power and faults

- **Board current from PB:** 4.5 mA (AVR modelled at 4.4 mA).
- **LDO input headroom:** at least 8.7 V at PB 9.5 V with a 300 mA head load.
- **+5 V shorted to GND:** R1 carries 68 mA and dissipates 0.69 W (1 W part). Head PB stays at 10.46 V.

## Model boundaries

- **Devices** are behavioural approximations, not vendor SPICE models: the SFH617A as a lagged CTR current source with soft saturation, and the LM2936 as an ideal limited source. A "dead" LDO is modelled as 0 V output, the worst case for back-feed.
- **Radio interface** is inferred from the service-manual schematics (R956/R953 1 kΩ, 47 kΩ pull-ups, TC4S81F/HC4050). Exact driver impedances, varistor capacitance and internal thresholds are swept assumptions.
- **The MCU is a pin-level stub.** Firmware correctness, forwarding latency, buffering and packet rewriting are not simulated.
- **Not covered:**
  - crystal and oscillator behaviour
  - EMC/ESD and automotive transients beyond the DC abuse cases
  - temperature drift other than the CTR corner

## Reproduction

```sh
python3 hardware/kenwood_proxy/check_design.py                # refresh netlist, ERC, design checks
python3 hardware/kenwood_proxy/simulation/run_simulation.py   # about 2-3 min; KP_SECTIONS=data,ill,power selects parts; KP_SMOKE=1 for a quick run
python3 hardware/kenwood_proxy/simulation/write_report.py     # summary tables
```

Results: `checks/simulation/results_data_ill_power.json`. Example deck: `checks/simulation/example_proxy.cir`.
