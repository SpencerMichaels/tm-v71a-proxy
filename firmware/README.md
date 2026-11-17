# Firmware

Firmware for the AVR128DB28 on the proxy board, built with **arduino-cli + DxCore** and flashed over J4 with a 5 V SerialUPDI adapter.

| Path | Purpose |
|---|---|
| `kenwood_proxy/proxy_core.c/.h` | All packet logic: forwarding, brightness rewrite, learning, inserts, lights filter. Plain C with no hardware access. |
| `kenwood_proxy/config.h` | Protocol bytes, timings and build options. |
| `kenwood_proxy/kenwood_proxy.ino` | Hardware layer: UART interrupts, lights input, EEPROM, watchdog, clock auto-tune, event log. |
| `test/` | Host unit tests of `proxy_core.c`, including replays of captured radio traffic (`make test`). |
| `tools/log.py` | Reads the event log from J4 pin 3. |
| `tools/rawlog.py` | Records the raw body → head stream from the sniff build. |
| `tools/serial_loopback.py` | Checks that a USB-serial adapter can send and receive: loop its TXD to its RXD first. |
| `tools/sniff.py`, `tools/framecheck.py` | Baud-rate and framing checks for a direct tap on a data line. |

## Setup

```sh
brew install arduino-cli            # or your platform's package
arduino-cli config add board_manager.additional_urls http://drazzy.com/package_drazzy.com_index.json
arduino-cli core update-index && arduino-cli core install DxCore:megaavr
```

The host tests need a C compiler (`cc`) and Python 3 for the tools. The tools use no extra packages.

## Build and flash

```sh
make test                                   # host tests
make fuses PORT=/dev/cu.usbserial-XXXX      # once per new chip: 1 ms start-up, BOD 2.85 V, keep EEPROM
make flash PORT=/dev/cu.usbserial-XXXX      # full firmware
make log LOGPORT=/dev/cu.usbserial-XXXX     # event log from J4 pin 3
```

| Target | What it builds |
|---|---|
| `make flash` | Full firmware: day/night brightness memory |
| `make flash-forward` | Forward-only: every byte passes unchanged. Useful for bring-up. |
| `make flash-sniff` | Forward-only, plus a raw copy of the body → head stream on J4 pin 3. Record it with `make rawlog LOGPORT=…`. |

**Options:**
- `REV=A-rework`: for a reworked Rev A board, see the `rev-a` branch. The default is Rev B.
- `PROG=serialupdi57k`: slower 57,600-baud programming for flaky adapters.

**Wiring.** The board is always powered through PB, by the radio or a 9–10 V supply on R1's left lead and TP2. Never connect the adapter's power pin.

| Use | J4 pin 1 | J4 pin 2 | J4 pin 3 |
|---|---|---|---|
| Programming, UPDI Friend | GND | UPDI | — |
| Programming, FT232 + 2.2 kΩ | GND | adapter RXD; 2.2 kΩ from TXD to RXD | — |
| Log or sniff | GND | — | adapter RXD |

> When logging, leave the adapter's TXD unconnected. An idle-high TXD back-powers the AVR through its pins whenever the board is unpowered.

> Some cheap CH340 USB-serial modules can't receive and won't program. Test an adapter with `tools/serial_loopback.py` (its TXD looped to its RXD) before blaming the board.

**Board settings** (in the Makefile's FQBN):
- 20 MHz internal clock, auto-tuned against the 32.768 kHz crystal. Its harmonics stay clear of 144–148 MHz.
- 1 ms start-up time.
- 2.85 V brown-out reset.
- EEPROM kept across reflashes, so the learned levels survive.

## Behaviour

- **Forwarding.** Each byte from the body goes to the head as it arrives. The added delay is about one byte time (0.17 ms).
- **Brightness messages** (`0x33 <digit> 0x0D`, see [`docs/protocol.md`](../docs/protocol.md)). The digit is held for one byte time until the `0x0D` confirms the message is complete. Then:
  - **First message ever:** the body's level is only recorded.
  - **Level differs from the body's last level:** this is a menu change by the user. It passes unchanged and is saved for the current lights state.
  - **Same level as last time** (for example at power-up): the firmware sends the saved level for the current lights state instead. Nothing is learned.
- **Insert.** On a lights change or at power-up, the saved level is sent right after the next message the body finishes. If the body is quiet for 20 ms, it's sent in that gap instead. An insert waits if the output queue is nearly full, so no bytes are ever dropped.
- **Lights input.** The input must be stable for 50 ms before the firmware switches between day and night.
- **EEPROM.** Holds the day level, night level and the body's last level, with a checksum. It's written 2 s after the last change, so stepping through the menu costs one write.
- **Empty slots.** Nothing is rewritten until each level has been set once in the menu.
- **Watchdog.** About 0.26 s.

## Event log

57,600 baud on J4 pin 3.

| Line | Meaning |
|---|---|
| `KP v1 rw=1 d=6 n=2 b=6 n` | Start-up: rewrite on, day level 6, night level 2, body's last level 6, lights on (`n`) |
| `X 1` / `X 0` | 2 s after start: the 32 kHz crystal is running / not running |
| `M n` / `M d` | Lights changed to night / day |
| `L n 3` | Learned level 3 for night |
| `R 6 2` | Body sent 6, head got 2 |
| `I n 2` | Inserted level 2 for night |
| `W` | EEPROM written |
| `O` | Head queue overflow (should never appear) |
