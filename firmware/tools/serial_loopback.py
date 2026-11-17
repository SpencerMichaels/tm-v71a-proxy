#!/usr/bin/env python3
"""Loopback test for a USB-serial adapter (CH340 etc.) used as a SerialUPDI programmer.

Usage:
  tools/serial_loopback.py PORT            echo test at 9600..230400 baud, 8N1 and 8E2
  tools/serial_loopback.py PORT --blink    send bursts for 20 s so the TX/RX LEDs flash

Wire the adapter's TXD straight to RXD (nothing else connected) for the first test,
then with the 2.2 kohm programmer resistor in place. A good adapter returns the
exact text at every speed. SerialUPDI needs 230400 (normal) or 57600 (slow mode).

Needs pyserial: `pip install pyserial`, or point DXCORE_LIBS at DxCore's bundled copy, e.g.
  DXCORE_LIBS=~/Library/Arduino15/packages/DxCore/hardware/megaavr/1.6.2/tools/libs
"""
import os
import sys
import time

libs = os.environ.get('DXCORE_LIBS')
if libs:
    sys.path.insert(0, os.path.expanduser(libs))
try:
    import serial
except ImportError:
    sys.exit('pyserial not found: pip install pyserial, or set DXCORE_LIBS (see the docstring)')

if len(sys.argv) < 2:
    sys.exit(__doc__)
port = sys.argv[1]

if '--blink' in sys.argv:
    s = serial.Serial(port, 9600, timeout=0)
    t0, sent, got = time.time(), 0, 0
    while time.time() - t0 < 20:
        s.write(b'U' * 200); sent += 200
        time.sleep(0.25); got += len(s.read(4096)); time.sleep(0.25)
    got += len(s.read(4096))
    print(f'sent {sent} bytes, received {got} bytes (expect equal with TXD-RXD looped)')
    s.close()
    sys.exit(0)

payload = b'HELLO-123'
ok_all = True
for baud in (9600, 57600, 115200, 230400):
    for par, sb, name in ((serial.PARITY_NONE, 1, '8N1'), (serial.PARITY_EVEN, 2, '8E2')):
        s = serial.Serial(port, baud, parity=par, stopbits=sb, timeout=0.3)
        time.sleep(0.05); s.reset_input_buffer()
        s.write(payload); s.flush(); time.sleep(0.15)
        back = s.read(64)
        s.close()
        ok = back == payload
        ok_all &= ok
        print(f'{baud:>6} {name}: {"OK  " if ok else "FAIL"} got {back!r}')
print('PASS: adapter echoes cleanly at every speed' if ok_all else 'FAIL: see the troubleshooting doc')
sys.exit(0 if ok_all else 1)
