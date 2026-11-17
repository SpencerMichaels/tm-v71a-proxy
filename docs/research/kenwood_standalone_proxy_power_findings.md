# Kenwood TM-V71A standalone proxy: PB power feasibility

Recorded: 2026-09-29.

## Scope and status

This is the pre-design service-manual review that led to powering the proxy from the radio's PB line. The board as built draws about 5 mA from PB.

**Conclusion:** an additional PB load of approximately 5–20 mA appears plausible, but available current margin is not established by the manual. Approximately 10 mA is a proposed design target, not measured consumption or a guaranteed allowance. No prototype measurements have been made for this assessment.

## Proposed architecture

- Use two 4P4C sockets with the previously confirmed identical mating-face pinouts; see [connector findings](kenwood_service_manual_findings.md).
- Pass PB (nominal 10 V) and GND directly between the body and head sockets.
- Take a small branch from PB through a local regulator to power a low-current microcontroller with two hardware UARTs and any necessary interface circuitry.
- Route the two serial directions through the microcontroller, with a hardware bypass provision for development/recovery.
- The manual establishes nominal 5 V serial interface circuitry; PB is a separate 10 V power conductor. Select compatible UART interfaces and handle reset, power sequencing, and USB back-powering if USB is included.
- This architecture could eliminate a separate ACC power connection for the Kenwood board. Dashboard-linked brightness would still require an external illumination signal; it is not available in the four-conductor Kenwood link.

## Service-manual evidence

Source: the Kenwood TM-V71A service manual. Page numbers below are printed manual page numbers.

| Pages | Finding |
|---|---|
| 85 | PB path: BAT (annotated approximately 13.75 V) → D956, MINISMDC110F16 resettable fuse → IC952, BAJ0CC0T regulator → R987, 0 Ω → PB, annotated 10 V. |
| 84 | PB connects to body connector J952 pin 2. |
| 74–75 | In the head, PB supplies IC904, TA4805BF, which generates 5 V for logic. PB also directly supplies the switched amber/green backlight circuits associated with Q904/Q905. Head logic current alone therefore does not represent the complete PB load. |
| 85 | No electronic enable or switching transistor appears in the PB supply path. IC952 is a three-terminal regulator without shutdown. PB therefore appears available while external DC remains connected, including front-panel soft-off. This is a schematic inference awaiting measurement. |
| 91 | The total-radio receive-current specification (<1.2 A at 2 W audio) is not a head/PB current specification and cannot establish spare PB capacity. |

**Correction to an initial progress report:** D956 protects the IC952/PB branch alone. IC953's 5M input comes from a parallel BAT branch through D957 (1SR154-400), not downstream of D956. The initial shared-fuse interpretation was corrected after inspection at higher resolution.

The reviewer found no standalone panel current specification or guaranteed accessory-current allowance.

## Component ratings and their limits

- [ROHM BAJ0CC0T product specification](https://www.rohm.com/products/power-management/linear-regulators/single-output-ldo-regulators/baj0cc0t-product): fixed 10 V output, up to 1 A, TO220FP-3, with overcurrent and overtemperature protection and no shutdown control. The 1 A rating is a component capability, **not** spare current available to an accessory.
- [Littelfuse miniSMDC110F/16 specification](https://www.littelfuse.com/assetdocs/ptc-minismdc110f16-2-product-specification?assetguid=65ee7bc3-81ab-46b3-9a5b-78270c634b30): hold current 1.1 A at 20°C and 0.75 A at 60°C; corresponding trip currents 2.2 A and 1.4 A. These are protection characteristics, not an allocated load budget.
- [ROHM BAxxCC0 application information](https://fscdn.rohm.com/en/products/databook/applinote/ic/power/linear_regulator/baxxcc0_app_info_an-e.pdf), printed p.11: continuous regulator capability depends on dissipation, mounting, and ambient temperature. The installed regulator's existing thermal margin remains unknown.

## Illustrative incremental load

Assumptions: 13.8 V at the radio supply, PB maintained at 10 V, and a local linear regulator producing 5 V. Values exclude regulator quiescent current and upstream voltage drops. These are examples, not actual proxy consumption measurements.

| Extra current drawn from PB | Additional dissipation in IC952, approximately (13.8 − 10) × I | Dissipation in local 10→5 V regulator, approximately (10 − 5) × I |
|---|---:|---:|
| 5 mA | 19 mW | 25 mW |
| 10 mA | 38 mW | 50 mW |
| 20 mA | 76 mW | 100 mW |

At 15.87 V, the radio's published upper supply limit, an additional 20 mA would add approximately 117 mW to IC952 under the same simplifying assumptions. These modest increments support investigating a low-power design but do not prove sufficient margin under all conditions.

## Remaining confirmation before committing the Kenwood design

1. Measure PB current with the normal head connected, including each backlight color at maximum brightness.
2. Verify PB voltage with the head operating and a representative additional 10–20 mA load.
3. Check whether PB remains powered with the front-panel power off and external DC connected.
4. Check warm operation and transmitting, which can affect thermal conditions inside the radio.
5. Establish actual proxy consumption and startup/reset behavior after selecting its controller, regulator, and interfaces. Confirm that it can forward any head power-on communication.

A multimeter and inline breakout suffice for the steady-state current/voltage checks above; an oscilloscope is not required for those checks. Such checks support prototype suitability, not complete worst-case qualification. Serial protocol verification and firmware development remain separate future work.

## Related notes

- [Connector and interface findings](kenwood_service_manual_findings.md)
