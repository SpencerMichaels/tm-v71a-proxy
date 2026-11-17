#!/usr/bin/env python3
"""Print the proxy's DBG_TX event log with timestamps (no pyserial needed).
Usage: tools/log.py /dev/cu.usbserial-XXXX [seconds]
Lines: 'KP v1 rw=1 d=6 n=2 b=6 n' banner (slots day/night, body level, lights);
M n|d lights change, L <mode> <lvl> learned, R <from> <to> rewritten, I <mode> <lvl> inserted, W EEPROM saved,
X 1|0 32 kHz crystal running / not running (once, 2 s after start).

Wiring: adapter RXD -> J4 pin 3, adapter GND -> J4 pin 1. Nothing on the adapter's TXD: an idle-high
TXD (directly or through the programmer's 2.2 kohm) back-powers the AVR through its pin when the
board is unpowered, and the log fills with partial 'KP ' lines from brown-out resets.
"""
import os, sys, time, termios
port = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else None
# Configure the descriptor we keep open: macOS resets a port's settings when the last
# descriptor closes, so a separate `stty` call does not stick.
fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
attrs = termios.tcgetattr(fd)
attrs[0] = 0                                                        # iflag: raw
attrs[1] = 0                                                        # oflag
attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL             # cflag: 8N1, no flow control
attrs[3] = 0                                                        # lflag: non-canonical, no echo
attrs[4] = attrs[5] = termios.B57600
attrs[6][termios.VMIN] = 0       # return after VTIME even with no data, so the time limit works
attrs[6][termios.VTIME] = 2      # 0.2 s
termios.tcsetattr(fd, termios.TCSANOW, attrs)
termios.tcflush(fd, termios.TCIFLUSH)
t0 = time.time(); line = b''
try:
    while limit is None or time.time() - t0 < limit:
        b = os.read(fd, 64)
        for c in b:
            if c == 10:
                print(f'{time.time() - t0:9.3f}  {line.decode(errors="replace").rstrip()}', flush=True); line = b''
            elif c != 13:
                line += bytes([c])
except KeyboardInterrupt:
    pass
finally:
    os.close(fd)
