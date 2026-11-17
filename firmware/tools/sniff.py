#!/usr/bin/env python3
"""Find the radio's serial settings with a USB-serial adapter used as a passive sniffer.

Usage: tools/sniff.py PORT [seconds_per_setting]

Wiring (radio running; the J5 taps carry the radio's own traffic whatever the AVR is doing):
  adapter GND -> J5 pin 1
  adapter RXD -> J5 pin 2 (body -> head)   [or J5 pin 3 for head -> body]
  adapter TXD -> NOT CONNECTED
While it runs, keep the radio busy: press keys, turn the dial, step brightness in the menu.

For each baud rate it prints what arrived, as hex and as text, plus a score. The right
setting gives readable, repeating messages (the protocol is expected to be ASCII lines ending
in CR, e.g. '33 3x 0D'). Wrong speeds give mostly 00/FF/random bytes. Garbage at every speed,
or lots of 00 bytes, suggests the line is inverted (idles low) rather than a speed problem.
"""
import os
import sys
import time

libs = os.environ.get('DXCORE_LIBS', '~/Library/Arduino15/packages/DxCore/hardware/megaavr/1.6.2/tools/libs')
sys.path.insert(0, os.path.expanduser(libs))
import serial  # noqa: E402

port = sys.argv[1]
dwell = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
BAUDS = (4800, 9600, 19200, 38400, 57600, 115200)


def score(data):
    if not data:
        return 0.0
    good = sum(1 for b in data if 32 <= b < 127 or b in (10, 13))
    return good / len(data)


results = []
for baud in BAUDS:
    s = serial.Serial(port, baud, timeout=0.2)
    time.sleep(0.05)
    s.reset_input_buffer()
    t0 = time.time()
    data = b''
    while time.time() - t0 < dwell:
        data += s.read(512)
    s.close()
    sc = score(data)
    results.append((sc, baud, len(data)))
    text = ''.join(chr(b) if 32 <= b < 127 else ('|' if b == 13 else '.') for b in data[:120])
    print(f'\n{baud:>6} baud: {len(data):5d} bytes, printable {sc:4.0%}')
    print('   hex :', data[:48].hex(' '))
    print('   text:', text)

best = max(results)
print('\nMost readable: %d baud (%d%% printable, %d bytes).' % (best[1], best[0] * 100, best[2]))
if best[2] == 0:
    print('No data at any speed: check RXD is on the R6 right lead, GND is connected, and the radio is on.')
elif best[0] < 0.6:
    print('Nothing readable at any speed: the line may be inverted (idles low). Measure R6\'s left lead to TP2 with the radio idle.')
