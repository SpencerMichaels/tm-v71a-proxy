#!/usr/bin/env python3
"""Reproducible ngspice behavioural verification of the exported Kenwood proxy netlist.

Board topology comes from checks/netlist.xml and design_intent.json. Radio-side interface models follow the
TM-V71A service manual (p.74 head: TC4S81F input, 47k pull-up CP913, varistor D988; p.84 body: TC74HC4050
output via R956 1k, RXD via R953 1k with 47k pull-up). Device models are engineering approximations, not
vendor SPICE models; the MCU is a pin-level stub, not firmware. Results support, but do not replace, bench tests.
Run with any python3:  python3 hardware/kenwood_proxy/simulation/run_simulation.py
"""
from pathlib import Path
import itertools, json, os, re, hashlib, time as _time, xml.etree.ElementTree as ET
SMOKE = bool(os.environ.get('KP_SMOKE'))
SECTIONS = set((os.environ.get('KP_SECTIONS') or 'data,ill,power').split(','))
from spice_engine import Spice

BASE = Path(__file__).resolve().parent.parent
OUT = BASE/'checks/simulation'; OUT.mkdir(parents=True, exist_ok=True)
xml = ET.parse(BASE/'checks/netlist.xml').getroot()
intent = json.loads((BASE/'design_intent.json').read_text())
N = {(nd.attrib['ref'], nd.attrib['pin']): net.attrib['name'] for net in xml.findall('./nets/net') for nd in net.findall('node')}
def nid(net): return '0' if net == 'GND' else 'n_' + re.sub(r'[^A-Za-z0-9]', '_', net)
def nd(ref, pin): return nid(N[(ref, str(pin))])
def val(ref):
    s = intent[ref]['value'].split()[0].lower()
    for suf, m in (('uf', 1e-6), ('nf', 1e-9), ('pf', 1e-12)):
        if s.endswith(suf): return float(s[:-len(suf)])*m
    if s.endswith('k'): return float(s[:-1])*1e3
    if s.endswith('r'): return float(s[:-1])
    return float(s)

BAUD = 57600.0; TB = 1/BAUD
# Receiver thresholds (V).  4000-series TC4S81F @5 V: VIL 1.5 / VIH 3.5.  HC4050 @5 V: 0.3/0.7 VCC.
# AVR DB I/O (DS40002247B tbl 39-6): Schmitt VIL 0.2 VDD / VIH 0.8 VDD (default input level).
RX_HEAD = (1.5, 3.5); RX_BODY = (1.5, 3.5)
def avr_thr(vdd, mode='schmitt'): return (0.2*vdd, 0.8*vdd)

MODELS = '''
.model DSIG D(Is=2.52n N=1.752 Rs=0.568 Cjo=4p M=0.4 tt=20n Bv=100 Ibv=100u)
.model DCLAMP D(Is=1f N=1.0 Rs=50 Cjo=1p)
.model DOPT D(Is=1.6e-13 N=1.8 Rs=2 Bv=6 Ibv=10u Cjo=20p)
.model DBODY D(Is=1p N=1.3 Rs=.1)
'''

DEFAULT = dict(
    vreg=5.0, imcu=4.4e-3, mcu='present',   # 'present' | 'removed' | 'tristate'
    mcu_rout=25.0, jp1=False,
    vpb=10.0, ihead=0.15,
    vbody=5.0, vhead=5.0, rbout=50.0, rhout=750.0, ccab_body=260e-12, ccab_head=20e-12, cvar=50e-12,
    ctr=0.7, tau=10e-6,
)

def pwl(name, pts):
    body = ' '.join(f'{t:.9g} {v:.6g}' for t, v in pts)
    # break only at spaces
    out = []; cur = ''
    for tok in body.split(' '):
        if len(cur) + len(tok) > 200: out.append(cur); cur = ''
        cur += tok + ' '
    out.append(cur)
    return f'{name} PWL(' + out[0] + '\n' + ''.join('+ ' + c + '\n' for c in out[1:]) + '+ )'

def uart_pts(data, t0, lo, hi, tr=20e-9, invert=False, tend=None):
    """PWL points for 8N1 frames starting at t0 (idle before/after)."""
    bits = []
    for b in data:
        bits += [0] + [(b >> i) & 1 for i in range(8)] + [1]
    def lvl(bit):
        x = (1 - bit) if invert else bit
        return hi if x else lo
    idle = lvl(1)
    pts = [(0, idle), (t0, idle)]
    cur = idle
    for k, bit in enumerate(bits):
        t = t0 + k*TB; v = lvl(bit)
        if v != cur:
            pts += [(t, cur), (t + tr, v)]; cur = v
    t = t0 + len(bits)*TB
    if cur != idle: pts += [(t, cur), (t + tr, idle)]
    pts.append((tend or t + 5*TB, idle))
    # de-duplicate monotone times
    clean = []
    for t, v in pts:
        if clean and t <= clean[-1][0]: t = clean[-1][0] + 1e-12
        clean.append((t, v))
    return clean

def board_lines(p):
    L = ['* --- board (from KiCad netlist) ---']
    # 1 Gohm DC reference on every board net: keeps nodes the model leaves floating (crystal, unused pins) solvable.
    for net in sorted(set(N.values())):
        if net != 'GND': L.append(f'Rref_{nid(net)} {nid(net)} 0 1G')
    for ref, c in intent.items():
        if ref.startswith('#'): continue
        if ref.startswith('R'):
            L.append(f'{ref} {nd(ref,1)} {nd(ref,2)} {val(ref):g}')
        elif ref.startswith('C'):
            esr = {'C4': 1.5, 'C6': 1.0}.get(ref)
            if esr:
                L += [f'{ref} {nd(ref,1)} {ref}_esr {val(ref):g}', f'R{ref}esr {ref}_esr {nd(ref,2)} {esr}']
            else:
                L.append(f'{ref} {nd(ref,1)} {nd(ref,2)} {val(ref):g}')
    L.append(f'D1 {nd("D1",2)} {nd("D1",1)} DSIG')
    # U3 SFH617A-3: LED + lagged CTR current source with soft saturation.
    c, e = nd('U3', 4), nd('U3', 3)
    L += [f'VU3s {nd("U3",1)} u3a 0', f'DU3 u3a {nd("U3",2)} DOPT', 'BU3f u3f 0 V=I(VU3s)', 'RU3f u3f u3g 1k',
          f'CU3f u3g 0 {p["tau"]/1e3:g}',
          f'BU3c {c} {e} I={p["ctr"]}*max(V(u3g),0)*tanh(max(V({c},{e}),0)/0.15)', f'CU3ce {c} {e} 5p']
    # U2 LM2936Z-5.0 behavioural: Vout=min(vreg, Vin-0.25) through 0.45 ohm; input draws output current + Iq.
    vin = nd('U2', 3); vo = nd('U2', 1)
    L += [f'BU2 u2x 0 V=min({p["vreg"]},max(V({vin})-0.25,0))', 'RU2o u2x u2o 0.45', f'VU2s u2o {vo} 0',
          f'FU2 {vin} 0 VU2s 1', f'IU2q {vin} 0 DC 0.1m']
    if p['jp1']: L.append(f'RJP1 {nd("JP1",1)} {nd("JP1",2)} 0.01')
    # U1 AVR stub
    v5 = nid('+5V')
    if p['mcu'] != 'removed':
        L.append(f'IU1 {v5} 0 DC {p["imcu"] if p["mcu"]=="present" else 1e-3:g}')
        for pin in ('3', '23', '7', '2', '22'):
            n = nd('U1', pin)
            L += [f'DU1h{pin} {n} {v5} DCLAMP', f'DU1l{pin} 0 {n} DCLAMP', f'CU1_{pin} {n} 0 4p']
        if p['mcu'] == 'present':
            for pin, lv in (('2', 'lv_tx'), ('22', 'lv_dbg')):
                L += [f'BU1d{pin} u1d{pin} 0 V=V({v5})*V({lv})', f'RU1o{pin} u1d{pin} {nd("U1",pin)} {p["mcu_rout"]}']
    return L

def radio_lines(p, body_pts=None, head_pts=None, tx_pts=None, ill_v=0.0):
    vb, vh = p['vbody'], p['vhead']
    L = ['* --- radio body / head / Toyota ILL environment ---',
         f'Vpb pbsrc 0 DC {p["vpb"]}', f'Rpbsrc pbsrc {nd("J1",1)} 0.2', f'Ihead {nd("J2",1)} 0 DC {p["ihead"]}',
         f'Vb5 vb5 0 DC {vb}', f'Vh5 vh5 0 DC {vh}']
    L.append(pwl('Vbtx btxd 0', body_pts) if body_pts else f'Vbtx btxd 0 DC {vb}')
    L += [f'Rbout btxd btxo {p["rbout"]}', f'R956 btxo {nd("J1",4)} 1k', f'Cbcab4 {nd("J1",4)} 0 {p["ccab_body"]:g}',
          f'Cbcab3 {nd("J1",3)} 0 {p["ccab_body"]:g}', f'R953 {nd("J1",3)} brx 1k', 'Rbpu brx vb5 47k', 'Cbrx brx 0 10p']
    L += [f'Chcab4 {nd("J2",4)} 0 {p["ccab_head"]:g}', f'Chvar4 {nd("J2",4)} 0 {p["cvar"]:g}', f'Rhpu {nd("J2",4)} vh5 47k',
          f'Chin {nd("J2",4)} 0 5p']
    L.append(pwl('Vhtx htxd 0', head_pts) if head_pts else f'Vhtx htxd 0 DC {vh}')
    L += [f'Rhout htxd {nd("J2",3)} {p["rhout"]}', f'Chcab3 {nd("J2",3)} 0 {p["ccab_head"]:g}', f'Chvar3 {nd("J2",3)} 0 {p["cvar"]:g}']
    # MCU logic levels (0..1)
    L.append(pwl('Vlv_tx lv_tx 0', tx_pts) if tx_pts else 'Vlv_tx lv_tx 0 DC 1')   # USART idle = high
    L.append('Vlv_dbg lv_dbg 0 DC 1')
    # Toyota ILL as installed: J3-1 to ILL+ (TAIL), J3-2 to chassis ground; tail/marker lamps load ILL+ to ground.
    ip, im = nd('J3', 1), nd('J3', 2)
    L += [f'Vill ills 0 DC {ill_v}', f'Rills ills {ip} 0.5', f'Rgnd {im} 0 0.05', f'Rlamp {ip} 0 60']
    return L

def deck(p, title, analysis_lines=(), **kw):
    lines = [title, *board_lines(p), *radio_lines(p, **kw),
             MODELS,
             '.options method=gear reltol=1e-4 abstol=1e-11 vntol=1e-6 itl4=200', *analysis_lines, '.end']
    return '\n'.join(lines) + '\n'

def interp(t, v, x):
    import bisect
    i = bisect.bisect_left(t, x)
    if i <= 0: return v[0]
    if i >= len(t): return v[-1]
    t0, t1 = t[i-1], t[i]; return v[i-1] + (v[i]-v[i-1])*(x-t0)/(t1-t0 or 1)

def decode(t, v, thr, tstart, nbytes):
    """Sample 8N1 at bit centres after each detected start edge. Returns (bytes, min_margin_V)."""
    vil, vih = thr; mid = (vil + vih)/2
    out = []; margin = 1e9; k = 0
    while len(out) < nbytes:
        while k < len(t) and (t[k] < tstart or v[k] > mid): k += 1
        if k >= len(t): break
        te = t[k]; byte = 0; ok = True
        for i in range(10):
            x = interp(t, v, te + (i + 0.5)*TB)
            bit = 0 if x < mid else 1
            m = (vil - x) if bit == 0 else (x - vih)
            margin = min(margin, m)
            if 1 <= i <= 8: byte |= bit << (i-1)
            if (i == 0 and bit) or (i == 9 and not bit): ok = False
        out.append(byte if ok else -1)
        tstart = te + 9.6*TB
    return out, margin

def edge_skew(t, v, mid, ideal_edges, window=0.45):
    """Max |crossing time - ideal edge time| (s) over the given ideal edges."""
    worst = 0
    for te in ideal_edges:
        lo, hi = te - window*TB, te + window*TB
        prev = None; found = None
        for a, b in zip(range(len(t)-1), range(1, len(t))):
            if t[b] < lo: continue
            if t[a] > hi: break
            if (v[a]-mid)*(v[b]-mid) <= 0 and v[a] != v[b]:
                found = t[a] + (mid-v[a])*(t[b]-t[a])/(v[b]-v[a]); break
        if found is None: return None
        worst = max(worst, abs(found - te))
    return worst

def ideal_edges(data, t0):
    bits = []
    for b in data: bits += [0] + [(b >> i) & 1 for i in range(8)] + [1]
    edges = []; cur = 1
    for k, bit in enumerate(bits):
        if bit != cur: edges.append(t0 + k*TB); cur = bit
    if cur != 1: edges.append(t0 + len(bits)*TB)
    return edges

s = Spice(); s.command('version'); version = [m for m in s.messages if 'ngspice' in m.lower()][:2]
failures = []; records = {'data': [], 'ill': [], 'dc': [], 'power': []}
def fail(kind, **k): failures.append({'kind': kind, **k})

# ============================================================== A. data paths (full proxy)
BODY_DATA = [0x55, 0x00, 0xFF, 0x33, 0x0D]
PROXY_DATA = [0x33, 0x34, 0x0D, 0x55, 0x00]     # MCU retransmission to head (rewritten brightness + forwarded bytes)
HEAD_DATA = [0xFF, 0x0D, 0xC1, 0x30]
T0 = 20e-6
TX0 = T0 + 10*TB                                 # MCU starts forwarding one byte time after the body starts
TEND = T0 + 10*TB*len(BODY_DATA) + 14*TB
CORNERS = []
# Cable C per data wire (body side, head side): short/short, long/long (~8 m each), and as installed (4 m body ~260 pF, 0.3 m head ~20 pF).
for (cb, ch), cvar, v5, weak, rout in itertools.product([(100e-12, 100e-12), (470e-12, 470e-12), (260e-12, 20e-12)], [20e-12, 100e-12], [4.75, 5.25],
                                                    [False, True], [25.0, 117.0]):
    CORNERS.append(dict(ccab_body=cb, ccab_head=ch, cvar=cvar, vbody=v5, vhead=v5, rbout=100.0 if weak else 25.0,
                        rhout=1500.0 if weak else 400.0, mcu_rout=rout, vreg=4.85 if v5 == 4.75 else 5.15))
if SMOKE: CORNERS = CORNERS[:1] + CORNERS[-1:]
MODES = {
    'proxy':           dict(mcu='present'),                 # normal operation
    'mcu_reset':       dict(mcu='tristate'),                # reset / UPDI programming / unprogrammed: head must idle high
    'mcu_removed':     dict(mcu='removed'),
    'ldo_dead':        dict(mcu='tristate', vreg=0.0),      # fault: recorded
    'jp1_mcu_removed': dict(mcu='removed', jp1=True),       # recovery bypass
    'jp1_misuse':      dict(mcu='present', jp1=True),       # JP1 fitted with U1 running: damage check only
}
FAULT_MODES = ('ldo_dead', 'jp1_misuse')

def run_data(mode, corner):
    p = {**DEFAULT, **corner, **MODES[mode]}
    vb, vh = p['vbody'], p['vhead']
    body = uart_pts(BODY_DATA, T0, 0, vb, tend=TEND)
    head = uart_pts(HEAD_DATA, T0 + 3*TB, 0, vh, tend=TEND)
    tx = uart_pts(PROXY_DATA, TX0, 0, 1, tend=TEND) if p['mcu'] == 'present' else None
    s.load(deck(p, f'Kenwood proxy data {mode}', body_pts=body, head_pts=head, tx_pts=tx)); s.command(f'tran 40n {TEND:g}')
    t = s.vector('time')
    vhead_rx = s.vector(nd('J2', 4)); vbody_rx = s.vector('brx')
    rec = {'mode': mode, **{k: corner[k] for k in corner}}
    if mode in ('proxy', 'jp1_mcu_removed'):
        want, t0 = (PROXY_DATA, TX0) if mode == 'proxy' else (BODY_DATA, T0)
        got, mg = decode(t, vhead_rx, RX_HEAD, t0 - 1e-6, len(want))
        sk = edge_skew(t, vhead_rx, 2.5, ideal_edges(want, t0))
        rec.update(head_got=got, head_margin_V=round(mg, 3), head_edge_skew_us=None if sk is None else round(sk*1e6, 3))
        if got != want: fail('head_decode', mode=mode, corner=corner, got=got, want=want)
        elif mg < 0: fail('head_threshold_margin', mode=mode, corner=corner, margin=mg)
        if sk is None or sk > 0.15*TB: fail('head_edge_timing', mode=mode, corner=corner, skew=sk)
        if mode == 'proxy':
            # Before the MCU starts forwarding, the body's stream must not reach the head at all.
            seg = [x for tt, x in zip(t, vhead_rx) if T0 <= tt <= TX0 - 0.5*TB]
            rec['head_min_before_tx_V'] = round(min(seg), 3)
            if min(seg) < RX_HEAD[1]: fail('body_leak_to_head', corner=corner, vmin=min(seg))
    elif mode in ('mcu_reset', 'mcu_removed', 'ldo_dead'):
        vmin = min(x for tt, x in zip(t, vhead_rx) if tt >= T0)
        rec['head_idle_min_V'] = round(vmin, 3)
        if vmin < RX_HEAD[1] and mode not in FAULT_MODES: fail('head_not_idle', mode=mode, corner=corner, vmin=vmin)
    elif mode == 'jp1_misuse':
        i956 = [(b - a)/1e3 for a, b in zip(s.vector(nd('J1', 4)), s.vector('btxo'))]
        iR2 = [(a - b)/val('R2') for a, b in zip(s.vector(nd('U1', 2)), s.vector(nd('J2', 4)))]
        rec['body_output_peak_mA'] = round(max(abs(x) for x in i956)*1e3, 3)
        rec['mcu_pin_peak_mA'] = round(max(abs(x) for x in iR2)*1e3, 3)
        if max(abs(x) for x in i956) > 25e-3 or max(abs(x) for x in iR2) > 20e-3: fail('jp1_contention', corner=corner, **{k: rec[k] for k in ('body_output_peak_mA', 'mcu_pin_peak_mA')})
    # Body receives head's stream (direct copper path) in every mode.
    gotb, mgb = decode(t, vbody_rx, RX_BODY, T0 + 3*TB - 1e-6, len(HEAD_DATA))
    rec.update(body_got=gotb, body_margin_V=round(mgb, 3))
    if gotb != HEAD_DATA or (mgb < 0 and mode not in FAULT_MODES): fail('body_decode', mode=mode, corner=corner, got=gotb, margin=mgb)
    # MCU taps at the default Schmitt input levels
    if p['mcu'] == 'present' and not p['jp1']:
        for name, node_, data, t0 in (('tap_body', nd('U1', 23), BODY_DATA, T0), ('tap_head', nd('U1', 3), HEAD_DATA, T0 + 3*TB)):
            g2, m2 = decode(t, s.vector(node_), avr_thr(p['vreg'], 'schmitt'), t0 - 1e-6, len(data))
            rec[f'{name}_schmitt_margin_V'] = round(m2, 3)
            if g2 != data or m2 < 0: fail('mcu_tap_decode', tap=name, mode=mode, corner=corner, got=g2, margin=m2)
    records['data'].append(rec)
    return rec

t_start = _time.time()
for mode in (MODES if 'data' in SECTIONS else ()):
    for corner in CORNERS:
        run_data(mode, corner)
data_runs = len(records['data'])

# ============================================================== B. ILL input
# As installed (J3 to ILL+ and chassis ground). Lights off: ILL+ <1 V per the Toyota terminal spec (2 V margin case added).
ILL = 'ill' in SECTIONS
for ctr, vill in itertools.product([0.24, 2.0], [0.0, 1.0, 2.0]) if ILL else ():
    p = {**DEFAULT, 'ctr': ctr}
    s.load(deck(p, 'ILL off', ill_v=vill)); s.op()
    vs = s.value(nd('U3', 4)); ok = vs > avr_thr(p['vreg'], 'schmitt')[1]
    rec = dict(test='ill_lights_off', ctr=ctr, vill=vill, ill_sense_V=round(vs, 3), reads_high=ok)
    records['dc'].append(rec)
    if not ok: fail('ill_false_on', **rec)
# Lights on: weakest corner must read LOW.
for vill, ctr in itertools.product([9.0, 11.0, 14.5], [0.24, 0.34, 2.0]) if ILL else ():
    p = {**DEFAULT, 'ctr': ctr}
    s.load(deck(p, 'ILL on', ill_v=vill)); s.op()
    vs = s.value(nd('U3', 4)); ok = vs < avr_thr(p['vreg'], 'schmitt')[0]
    rec = dict(test='ill_lights_on', vill=vill, ctr=ctr, ill_sense_V=round(vs, 3), reads_low=ok)
    records['dc'].append(rec)
    if not ok and vill >= 11.0: fail('ill_weak_on', **rec)
    if not ok and vill < 11.0: rec['note'] = 'below Toyota 11 V spec: informational'
# Abuse: reversed ILL wiring and over-voltage (DC worst case).
for vill in (-14.5, 24.0, 40.0) if ILL else ():   # reversed wiring; 24 V continuous (jump start); 40 V load-dump pulse
    p = {**DEFAULT}
    s.load(deck(p, 'ILL abuse', ill_v=vill)); s.op()
    vled = s.value('u3a') - s.value(nd('U3', 2))
    r9v = val('R9'); ir9 = (s.value(nd('R9', 1)) - s.value(nd('R9', 2)))/r9v
    rec = dict(test='ill_abuse', vill=vill, led_V=round(vled, 3), r9_mA=round(ir9*1e3, 2), r9_W=round(ir9**2*r9v, 3))
    records['dc'].append(rec)
    if vled < -5.5: fail('ill_led_reverse', **rec)
    if abs(ir9) > 0.060: fail('ill_overcurrent', **rec)
    rec['r9_pulse_J_400ms'] = round(ir9**2*r9v*0.4, 3)
    if abs(vill) <= 24 and ir9**2*r9v > 0.5: fail('ill_r9_power', **rec)

# ============================================================== C. power / fail-safe DC
def i_through(rref):
    return (s.value(nd(rref, 1)) - s.value(nd(rref, 2)))/val(rref)
for vpb, ihead, (rout, vreg) in ([] if 'power' not in SECTIONS else itertools.product(
        [9.5, 10.0, 10.5], [0.05, 0.3], [(25.0, 5.15), (117.0, 4.85)])):
    p = {**DEFAULT, 'vpb': vpb, 'ihead': ihead, 'mcu_rout': rout, 'vreg': vreg}
    s.load(deck(p, 'power')); s.op()
    # MCU output pins are ideal behavioural sources in the stub; add their sourced current to the rail load.
    pin_mA = 0.0
    for pin in ('2', '22'):
        try: pin_mA += max(-s.value(f'bu1d{pin}#branch'), 0.0)
        except RuntimeError: pass
    ib = i_through('R1') + pin_mA; vin = s.value(nd('U2', 3)); v5 = s.value(nid('+5V'))
    rec = dict(mode='proxy', vpb=vpb, ihead=ihead, mcu_rout=rout, vreg=vreg, board_mA=round(ib*1e3, 2), ldo_in_V=round(vin, 3),
               v5=round(v5, 3), head_PB_V=round(s.value(nd('J2', 1)), 3))
    if vin - v5 < 0.4 and vreg > 0: fail('ldo_headroom', **rec)
    records['power'].append(rec)
# +5V shorted to GND: R1 dissipation and head PB.
p = {**DEFAULT, 'vpb': 10.5}
cir = deck(p, '5V short').replace('.options', f'Rshort {nid("+5V")} 0 0.01\n.options')
s.load(cir); s.op()
ir1 = i_through('R1'); rec = dict(test='5V_short', r1_mA=round(ir1*1e3, 1), r1_W=round(ir1**2*val('R1'), 3), head_PB_V=round(s.value(nd('J2', 1)), 3))
records['dc'].append(rec)
if ir1**2*val('R1') > 0.9: fail('r1_fault_power', **rec)
# LDO dead: MCU tap clamp currents back-feeding the dead rail
p = {**DEFAULT, 'vreg': 0.0, 'mcu': 'tristate'}
s.load(deck(p, 'ldo dead')); s.op()
rec = dict(test='ldo_dead_backfeed', v5_rail=round(s.value(nid('+5V')), 3), head_rx_V=round(s.value(nd('J2', 4)), 3),
           body_txd_V=round(s.value(nd('J1', 4)), 3))
records['dc'].append(rec)
rec['note'] = 'fault state: with no MCU supply the head RX is clamped low through R2 (display gets no data, as with any proxy failure); recorded, not a pass criterion'

elapsed = _time.time() - t_start
summary = dict(
    status='PASS_WITH_MODEL_LIMITATIONS' if not failures else 'FAILURES',
    ngspice=version, elapsed_s=round(elapsed, 1),
    netlist_sha256=hashlib.sha256((BASE/'checks/netlist.xml').read_bytes()).hexdigest(),
    counts=dict(data_transients=data_runs, dc_ops=len(records['dc']), power_ops=len(records['power'])),
    failure_count=len(failures),
)
tag = '_'.join(sorted(SECTIONS))
(OUT/f'results_{tag}.json').write_text(json.dumps(dict(summary=summary, failures=failures, records=records), indent=1) + '\n')
(OUT/'example_proxy.cir').write_text(deck({**DEFAULT}, 'example proxy', body_pts=uart_pts(BODY_DATA, T0, 0, 5, tend=TEND), tx_pts=uart_pts(PROXY_DATA, TX0, 0, 1, tend=TEND)))
print(json.dumps(summary, indent=1))
from collections import Counter
print(Counter(f['kind'] for f in failures))
