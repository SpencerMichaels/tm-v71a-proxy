# TM-V71A display proxy: Rev A

**This branch keeps the Rev A design as built. For a new board, use Rev B on the [`main`](../../tree/main) branch**, which has the fixes below built in, plus the full README and assembly guide.

The board sits in the cable between a Kenwood TM-V71A body and its separated control head. It sets the head's display brightness from the vehicle's lights. See `main` for how it works.

![Block diagram (Rev B wiring; Rev A after its rework is equivalent)](docs/img/block_diagram.svg)

## Rev A's known problem and the rework

Rev A was designed with the cable's two data lines the wrong way round: it expected the body to transmit on pin 4. In a measured radio, the **body transmits on pin 3** and the **head on pin 4** ([docs/protocol.md](docs/protocol.md)).

A built Rev A board works after a small rework, with no trace cuts:
1. J2 pin 3 is bent out of its hole.
2. R2 is replaced by a long-lead 470 Ω running from R2's left hole to the bent pin.
3. The JP1 shunt is fitted, which becomes the permanent head → body path.

Step-by-step instructions with diagrams are in [`hardware/REWORK.html`](hardware/REWORK.html). Download it and open it in a browser.

The reworked board has been tested in a vehicle with the full firmware.

## Contents

| Path | What |
|---|---|
| `hardware/` | Rev A KiCad project, Gerbers and BOMs (`fab/`), case (`enclosure/`), design checks and simulation |
| `hardware/ASSEMBLY_GUIDE.html` | Interactive Rev A assembly guide, with step-by-step diagrams |
| `hardware/REWORK.html` | The data-line rework |
| `hardware/TRUCK_TESTS.html` | In-vehicle bring-up tests used for Rev A |
| `firmware/` | Same firmware as `main`, but defaulting to `REV=A-rework`: body data through R7 on PC1 |
| `docs/` | Protocol notes, raw captures, service-manual research |

The HTML guides were written during the original build and are kept as they were. They mention the build's own adapter and serial port names, and "ask Claude" points where the build was done with an AI assistant.

## License

Hardware: [CERN-OHL-S-2.0](LICENSE-HARDWARE). Firmware, scripts and tools: [GPL-3.0](LICENSE).
