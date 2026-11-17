# TM-V71A head ↔ body link

These are the facts this project relies on. Everything marked **measured** was captured from a real TM-V71A in 2026-11 with a USB-serial adapter. The brightness message was first published by [KK4HEJ](https://kk4hej.wordpress.com/decoding-the-tm-v71a-display-protocol/).

## Cable

The separation cable is a 4-conductor 4P4C (RJ9-style) cable. The pin numbers below are the PCB footprint numbers of the Würth 615004143821 jack used on the board (J1 and J2).

| Pin | Signal | Direction | Notes |
|---|---|---|---|
| 1 | PB | body → head | about 10 V from the radio's own regulator; present whenever the radio has DC |
| 2 | GND | — | |
| 3 | data | **body → head** | display stream (measured) |
| 4 | data | **head → body** | key presses and knob turns (measured) |

The design was first drawn from a service-manual reading that had pins 3 and 4 the other way round. That is the one difference between Rev A and Rev B. **If you adapt this design to another radio, sniff each data pin to confirm its direction before laying out a board.**

## Serial format (measured)

- **57,600 baud, 8 data bits, no parity, 1 stop bit, idle high, 5 V logic.**
- Messages end with a carriage return, `0x0D`.
- There are no acknowledgements or retries. Messages from the body set the display state.
- Body → head traffic is heavy while the radio is in use: about 3 kB in 15 s. Messages vary in length. Typical examples are `K.70`, `J.00`, a 28-byte `[A 4WX   4…` channel line, and menu text such as `\501   BRIGHT     5..`.
- Head → body traffic is light: short codes such as `81`, `89`, `8a`, `b0`, `c4 46 46`, each followed by `0D`.

## Brightness (measured)

```
33 <level> 0D        level = ASCII '0' (0x30, shown as OFF) … '8' (0x38)
```

- **Menu changes:** every step in the BRIGHT menu sends **two** messages a few milliseconds apart: `33 38 0D` (level 8), then `33 3N 0D`, the level you picked. Picking 8 sends `38` twice.
- **No periodic repeat:** the body sends brightness only when the level changes or the radio powers up. A 79-second capture had none otherwise.
- **Power-up:** the start-up sequence contains one brightness message carrying the **saved** level. For example, with the level saved as 3:

  ```
  00 0D | 0D | 30 31 0D | 37 0D | 32 30 0D | 33 33 0D | 34 48 45 4C 4C 4F 20 0D ("4HELLO ") | …
  ```

  A menu change only becomes the saved level once the setting is stored by the radio.

### How the firmware uses this

- A brightness message whose level differs from the body's last level is a **menu change**. It goes to the head unchanged and is remembered for the current lights state (day or night).
- A message repeating the body's last level, as at power-up, is **rewritten** to the remembered level for the current lights state.
- When the vehicle lights change state, the firmware inserts its own brightness message between two body messages.

The `38`-then-`3N` pair is learned twice in a row, and the final value is the one you picked. The host tests in `firmware/test` replay the captured menu-step and power-up sequences.

## Power behaviour (measured)

- If DC is removed while the radio is **on**, it switches itself back on when DC returns. Feeding the radio from an ignition-switched (ACC) supply therefore gives automatic power-on. The board needs nothing for this.
- The board is powered from PB, so it runs whenever the radio has DC.

## Captures

Raw captures are in [`captures/`](captures/). Each `.bin` file is a sequence of records:

```
uint32 little-endian  milliseconds since start
uint8                 message length
bytes                 the message, including its 0x0D
```

| File | What |
|---|---|
| `2026-11-15_ft232_sniff.md` | First sniff of both lines, which established the pin directions |
| `2026-11-15_brightness_sniff.bin/.md` | Stepping BRIGHT down to OFF and back up, several times |
| `2026-11-15_powerup3_sniff.bin` | Power-up with the level saved as 3 |
| `2026-11-15_powerup_sniff.bin` | Power-up with the level at 8 |

Record your own with the sniff firmware (`make flash-sniff`) and `make rawlog`; see [`firmware/README.md`](../firmware/README.md).
