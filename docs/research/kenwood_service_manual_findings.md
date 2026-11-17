# TM-V71A Kenwood interface: service-manual findings

> **Correction (measured 2026-11-15).** The board-side translation of these notes was wrong in Rev A: the two data lines were swapped. Sniffing the real radio showed this mapping, by the Würth 615004143821 footprint pin numbers used on the board:
> - pin 1 = PB (about 10 V)
> - pin 2 = GND
> - **pin 3 = body → head data** (display stream)
> - **pin 4 = head → body data** (key presses)
>
> Rev B uses this measured mapping. Treat the head/body labels below as service-manual reading only, and see [../protocol.md](../protocol.md).


Reviewed 2026-09-26. Source: the Kenwood TM-V71A service manual. Page references below are the printed page numbers.

## Verified electrical connections

Pages 19, 21, 73 and 75 establish the following connections. These are Kenwood connector numbers, **not proposed PCB 4P4C jack pad numbers**.

| Signal | Body panel jack J952 | Head internal connector CN912 | Direction |
|---|---|---|---|
| PB, nominal 10 V | 2 | 1 and 2 | Body supplies head |
| Ground | 3 | 3 and 4 | Common return |
| Body TX / head RX | 4 | 5 | Body to head |
| Head TX / body RX | 7 | 6 | Head to body |

The head's external connector is identified as E58-0457-05; CN912 is its six-contact internal connection, with doubled power and ground. J952 is an eight-position body connector, with other signals assigned to positions 1, 5, 6 and 8. Do not treat it as a four-position jack or infer a standard telephone cable wiring arrangement.

## Author-confirmed physical connector orientation

Reported 2026-09-26: looking into each **female mating face**, with the latch retainer **up**. The author clarified that these socket layouts were derived from physical observation of the actual Kenwood cables: they describe how the mating sockets must be laid out for those cables to work. Actual cable mapping is resolved; no additional cable-mapping information is pending.

- Body eight-position jack: left to right, positions 1 through 8. Relevant contacts are 2 = PB, 3 = GND, 4 = body TXD, 7 = body RXD. The author explicitly located pin 7 on the right and pins 2/3/4 on the left; numbering therefore decreases when read from right to left.
- Head four-position jack, left to right: **head RXD, head TXD, GND, PB**.

For reference, label those head contacts L1–L4 (physical left-to-right labels, not manufacturer footprint numbers): L1 connects to body J952-4; L2 to J952-7; L3 to J952-3; L4 to J952-2. RXD/TXD names are local to each device, so body TXD connects to head RXD and vice versa.

Final cable clarification: the cable from the radio body already terminates in a **4P4C plug at the PCB**. The PCB therefore needs **two 4P4C female jacks with identical mating-face pinouts**, not an eight-position PCB jack or a new body-side adapter. Looking into either PCB socket with its latch retainer up, left to right:

| Physical contact | Author's signal label (head perspective on both jacks) | Direction/function |
|---|---|---|
| L1 | RXD | Body TX to head RX |
| L2 | TXD | Head TX to body RX |
| L3 | GND | Ground |
| L4 | PB | Nominal 10 V panel power |

The author explicitly confirmed that the cable between the PCB and the Kenwood head is straight-through: **1 → 1, 2 → 2, 3 → 3, 4 → 4**. It introduces no contact-order reversal or TX/RX crossover. Retain the mating-face orientation above when translating connector contact numbers into PCB footprint pad numbers.

In bypass mode, connect corresponding physical contacts: L1–L1 and L2–L2 through removable links; L3–L3 and L4–L4 directly. Do not cross L1/L2 merely because one jack is labeled BODY and the other HEAD. Use direction-based net names to avoid changing the RXD/TXD naming perspective between jacks.

These observations establish the required mating-socket orientation for the actual cables. Map the selected PCB jack's contact-to-pad numbering from its datasheet; do not copy a mating-face drawing directly onto a solder-side footprint. That footprint translation is design work, not a request for further user cable measurements.

## Electrical levels

- Page 74: panel PB feeds the TA4805BF 5 V regulator IC904. The panel RX/TX buffers IC901 and IC902 (TC4S81F-F) are supplied from the resulting 5 V rail. The serial interface is therefore nominal 0–5 V logic, distinct from the 10 V power conductor.
- Pages 84–85: the body panel interface uses buffer IC951 (TC74HC4050AFT) on the 5M rail; IC953 provides the 5 V rail. IC952 is the 10 V regulator for PB.
- These establish nominal circuit levels, not measured waveforms, guaranteed logic thresholds, or permission to drive an unpowered Nano input.

## Proposed simple PCB provision

For two 4P4C PCB jacks, pass Kenwood PB and ground through directly. Keep PB separate from the Nano supply. Initially bridge each serial direction directly between jacks, with the Nano serial interface disconnected. Provide removable links or routing jumpers so a future two-UART proxy can replace those bridges without cutting PCB traces. No Kenwood firmware is needed in bypass mode.

Use the identical four-position PCB socket mapping above when assigning the selected jack's numbered contacts. The eight-position J952 mapping is radio-side reference information only; the existing body cable already provides the four-position PCB termination.

Before enabling proxy mode, finish the powered-off-safe buffer/interface design and reassign SWC output pins to avoid the proposed extra UART pins. Confirm serial framing and commands separately; the pages cited here do not establish the previously proposed baud rate or brightness packet format.

This note records the evidence and proposed expansion; it does not silently change the active SWC-only scope in `swc_module_plan.md`.
