#!/usr/bin/env python3
"""Record the sniff build's raw body->head copy from DBG_TX (J4 pin 3), 57600 8N1.
Usage: tools/rawlog.py /dev/cu.usbserial-XXXX [seconds] [out.bin]
Prints each CR-terminated message once per change (timestamp, hex, ASCII) and saves every
byte with a 4-byte millisecond timestamp per message to out.bin (default captures/raw_<time>.bin).
Wiring: adapter RXD -> J4 pin 3, adapter GND -> J4 pin 1, nothing on TXD.
"""
import os, sys, time, termios, struct
port = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else None
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), '..', 'captures',
                                                          time.strftime('raw_%Y%m%d_%H%M%S.bin'))
fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
a = termios.tcgetattr(fd)
a[0] = a[1] = a[3] = 0
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
a[4] = a[5] = termios.B57600
a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 2
termios.tcsetattr(fd, termios.TCSANOW, a)
termios.tcflush(fd, termios.TCIFLUSH)
t0 = time.time(); msg = b''; last = {}; n = 0
with open(out, 'wb') as f:
    try:
        while limit is None or time.time() - t0 < limit:
            for c in os.read(fd, 256):
                msg += bytes([c]); n += 1
                if c == 0x0D or len(msg) > 64:
                    t = time.time() - t0
                    f.write(struct.pack('<IB', int(t * 1000), len(msg)) + msg)
                    key = msg[:1]                      # message type
                    if last.get(key) != msg:           # print only changes per type
                        last[key] = msg
                        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in msg)
                        print(f'{t:8.3f}  {msg.hex(" "):<60} {asc}', flush=True)
                    msg = b''
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)
print(f'{n} bytes saved to {out}', file=sys.stderr)
