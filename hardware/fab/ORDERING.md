# Kenwood proxy Rev B: ordering

**Rev B changes from Rev A:** the jack data pins are swapped to match the radio (measured 2026-11-15: body transmits on pin 3, head on pin 4); new 1×4 data-tap header J5 (GND, body→head, head→body, head input); crystal changed to the long-lead through-hole AB26T. Same 54 × 52 mm outline, holes and case. The firmware defaults to Rev B.

## PCB (OSH Park, 2-layer)

- **Upload:** `kenwood_proxy_revB_oshpark_gerbers.zip`. It contains Gerbers for both copper layers, mask and silk on both sides, the outline (`Edge_Cuts.gm1`) and one merged Excellon drill file (decimal, absolute, alternate oval mode, per OSH Park's KiCad guide).
- **Review the preview before ordering.**
  - Outline 54.0 × 52.0 mm (4.35 in²).
  - J1, J2 and J3 on the top edge; the 3-pin programming header J4 at the bottom left; the 4-pin data-tap header J5 at the top left, below J1.
  - A bare, pour-free ILL area at the top right, around J3.
- **Expected price:** 4.35 in² × $5/in² ≈ **$22 for 3 boards**, standard service, 1.6 mm, 1 oz.
- **Design limits vs. OSH Park:**
  - Minimum track and clearance 0.2 mm (OSH Park 0.152 mm).
  - Minimum drill 0.4 mm (OSH Park 0.254 mm).
  - Minimum annular ring 0.2 mm (OSH Park 0.127 mm).
- **Non-plated holes.** The four 2.36 mm jack-peg holes and four 3.2 mm mounting holes are marked non-plated in the drill file. If OSH Park plates them anyway, nothing changes: they connect to no net, and the pegs are plastic.
- **Spare boards.** One fitted with only J1, J2 and a JP1 shunt (or wire) is a known-good straight-through coupler.
- **Fallback.** OSH Park also accepts the KiCad board file directly (`../kenwood_proxy.kicad_pcb`). Prefer the Gerbers, since their importer may lag KiCad 10.

## Parts

- **`BOM_purchasing.csv`** lists every part with MPN, Newark stock and price where known (read 2026-10-09 via Findchips), DigiKey/Mouser search links, alternates and notes.
  - Expect roughly **$30** in parts at the suggested buy quantities.
  - "Suggested buy" includes spares: a second AVR, opto, regulator and crystal; two extra 4P4C jacks (to build a spare board as a straight-through coupler); 10 of each resistor value; and one 40-pin breakaway header strip for JP1, J4 and J5.
  - The J3 mating receptacle comes from the pre-crimped Micro-Fit kit, so it is not in the upload file.
- **`BOM_upload_digikey_mouser.csv`** has the same parts as MPN, manufacturer and quantity. Upload it to DigiKey's BOM Manager or Mouser's BOM tool to see live stock and price in one step.

**Check before ordering:**
1. **U2:** LM2936Z-5.0/NOPB is out of stock at TI and on backorder at DigiKey. If Mouser has none either, buy the Diodes **AP7381-50V-A**. It has the same TO-92 pinout and is fine with C4.
2. **C6:** Panasonic EEA-FC1E100, the plain bulk part (UPW1E100MDD is obsolete). It is 4 × 7 mm with 1.5 mm leads: spread them slightly into the 2.0 mm holes. Any 10 µF ≥25 V **105 °C** radial, 4–5 mm diameter, also works.
3. **C7/C8:** if C315C150J1G5TA is out, any 15 pF C0G with 2.5 mm lead spacing works.
4. **470 Ω and 680 Ω resistors:** any 1/4 W 1 % metal film with a 6.3 mm body.

## Loose items (not on the PCB BOM)

- **Programming:** an FT232-based 5 V USB-serial adapter wired as SerialUPDI (TXD → 2.2 kΩ → RXD, RXD to UPDI). Some cheap CH340 modules can't receive and fail to program; check an adapter with `firmware/tools/serial_loopback.py` first. An Adafruit UPDI Friend also works, plus female jumper wires: GND to J4 pin 1, UPDI to J4 pin 2. Leave the adapter's power pin unconnected; the radio powers the board.
- **Logging:** a 5 V USB-serial adapter, RX to J4 pin 3 (DBG_TX) and GND to J4 pin 1.
- **J3 mating plug:** a Micro-Fit 3.0 2-circuit receptacle (Molex 43025-0200) with pre-crimped 22 AWG leads, e.g. from a pre-crimped Micro-Fit kit. It latches onto J3. Splice or extend the leads to ILL+ and chassis ground. The pin numbers are molded on the housing: pin 1 = ILL+, pin 2 = GND. Check with a meter after wiring.
