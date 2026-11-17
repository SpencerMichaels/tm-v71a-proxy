# Brightness capture, 2026-11-15 (truck, reworked Rev A, sniff build, FT232 on J4 pin 3)

Raw data: `2026-11-15_brightness_sniff.bin`. Each record is a uint32 ms timestamp, a uint8 length, then the message bytes. The capture ran 79 s and ended when the adapter was unplugged.
The author stepped BRIGHT in the menu down to OFF and back up several times.

## Brightness message: confirmed
`0x33 <level> 0x0D`, where level is ASCII `'0'` (shown as OFF) to `'8'`. This matches config.h (KP_BRIGHT_CMD, MIN '0', MAX '8').

- The body sends brightness messages only when the level changes. There was no periodic re-broadcast in 79 s.
- **Every menu step sends two messages, `38` then `3N`, about 0-15 ms apart.** The `38` (full brightness) always comes first. Selecting 8 gives `38 38`.
- The menu display text follows straight after, for example `\501   BRIGHT     5..`. When the menu opens, the body sends `38` twice with no other level message.
- Power-up sequence (t = 5.4 s): `00`, `01`, `7`, `20`, `38`, `4HELLO `, `@..`, `ZA..`, `[A..`, `J.00`, `K.00`, ... There is a single `38`, and the level was 8 at the time.

## Power-up: answered (2026-11-15_powerup3_sniff.bin)
With BRIGHT saved as 3, the power-up sequence carried a single `33` in the same slot (`00`, `01`, `7`, `20`, `33`, `4HELLO`, ...), and the head came up at level 3.
So the power-up message is the body's **saved level**, sent once and with no `38` before it.
An attempt at level 6 came up as `38`, because the author had not saved the setting; `2026-11-15_powerup_sniff.bin` therefore shows level 8.
This fits the firmware: at power-up the body re-sends last_body, which counts as unchanged, so it is rewritten to the stored slot.

## Effect on proxy_core.c
- `38` then `3N`: two learns in a row, and the final slot is N. That is correct; the brief 8 is the body's own behaviour.
- No re-broadcasts: the "rewrite unchanged level" path rarely fires. In practice, day/night changes are handled by the insert after a terminator.
