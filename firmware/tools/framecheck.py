#!/usr/bin/env python3
"""Work out the radio's character format (parity / stop bits) with a USB-serial adapter.

Usage: tools/framecheck.py PORT [baud] [seconds_per_format]

Same wiring as tools/sniff.py (adapter RXD on J5 pin 2, GND on J5 pin 1).
For each format it listens with the OS's parity and framing checks switched on and counts:
  ok       bytes received cleanly
  parity   bytes with a parity error
  framing  bytes with a framing error (no stop bit where one was expected)
The radio's real format is the one with (near) zero errors. Uses termios directly (macOS/Linux).
"""
import os
import sys
import termios
import time

port = sys.argv[1]
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 57600
dwell = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
SPEED = getattr(termios, f'B{baud}')

FORMATS = [  # name, cflag parity bits, stop bits
    ('8N1', 0, 1),
    ('8E1', termios.PARENB, 1),
    ('8O1', termios.PARENB | termios.PARODD, 1),
    ('8N2', 0, 2),
]


def listen(cpar, stop):
    fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        a = termios.tcgetattr(fd)
        # Mark bad bytes in the stream: parity/framing error -> FF 00 <byte>; a real FF -> FF FF.
        a[0] = termios.INPCK | termios.PARMRK
        a[1] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | cpar | (termios.CSTOPB if stop == 2 else 0)
        a[3] = 0
        a[4] = a[5] = SPEED
        a[6][termios.VMIN] = 0
        a[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIFLUSH)
        data = b''
        t0 = time.time()
        while time.time() - t0 < dwell:
            try:
                data += os.read(fd, 4096)
            except BlockingIOError:
                pass
            time.sleep(0.01)
    finally:
        os.close(fd)
    ok = bad = 0
    good_bytes = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF and i + 1 < len(data):
            if data[i + 1] == 0xFF:          # escaped real 0xFF
                ok += 1; good_bytes.append(0xFF); i += 2; continue
            if data[i + 1] == 0x00:          # error mark: FF 00 x
                bad += 1; i += 3; continue
        ok += 1; good_bytes.append(data[i]); i += 1
    return ok, bad, bytes(good_bytes)


print(f'{baud} baud, {dwell:.0f} s per format. Keep the radio busy (keys, dial, brightness).')
rows = []
for name, cpar, stop in FORMATS:
    ok, bad, good = listen(cpar, stop)
    rows.append((name, ok, bad))
    rate = bad / (ok + bad) if ok + bad else 0
    text = ''.join(chr(b) if 32 <= b < 127 else ('|' if b == 13 else '.') for b in good[:60])
    print(f'  {name}: {ok:5d} ok, {bad:5d} with errors ({rate:4.0%})   sample hex: {good[:24].hex(" ")}')
    print(f'        text: {text}')
total = [r for r in rows if r[1] + r[2] > 0]
if not total:
    print('No data in any format: check the RXD clip on R6\'s right lead and that the radio is on.')
else:
    best = min(total, key=lambda r: r[2] / (r[1] + r[2]))
    print(f'Fewest errors: {best[0]} ({best[2]} of {best[1] + best[2]} bytes bad).')
