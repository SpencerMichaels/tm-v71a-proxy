"""Kenwood proxy design checks. Exports the native KiCad netlist and ERC, then checks
pin-level connectivity against design_intent.json plus explicit safety requirements.
Does not simulate parts; electrical limits below are hand calculations from datasheets.
"""
from pathlib import Path
import json, subprocess, xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CHK = HERE/'checks'; CHK.mkdir(exist_ok=True)
SCH = HERE/'kenwood_proxy.kicad_sch'
subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(CHK/'netlist.xml'),str(SCH)],check=True,capture_output=True)
subprocess.run(['kicad-cli','sch','erc','--format','json','--severity-all','-o',str(CHK/'erc.json'),str(SCH)],check=True,capture_output=True)

intent = json.loads((HERE/'design_intent.json').read_text())
root = ET.parse(CHK/'netlist.xml').getroot()
actual = {}; nets = {}
for n in root.iter('net'):
    name = n.get('name').lstrip('/')
    for nd in n.iter('node'):
        actual[(nd.get('ref'), nd.get('pin'))] = name
        nets.setdefault(name, set()).add((nd.get('ref'), nd.get('pin')))

results = []
def check(name, ok, detail=''):
    results.append({'check': name, 'pass': bool(ok), 'detail': detail})

# 1. ERC clean
erc = json.loads((CHK/'erc.json').read_text())
viol = [v for s in erc['sheets'] for v in s['violations']]
check('ERC: zero violations', not viol, '; '.join(v['description'] for v in viol))

# 2. Every intended pin is on its intended net (unconnected pins must be absent or single-pin)
bad = []
for ref, c in intent.items():
    if ref.startswith('#'): continue
    for pin, p in c['pins'].items():
        got = actual.get((ref, pin))
        want = p['net']
        if want is None:
            if got is not None and len(nets.get(got, ())) > 1: bad.append(f'{ref}.{pin} should be NC, is on {got}')
        elif got != want: bad.append(f'{ref}.{pin} want {want} got {got}')
check('Netlist parity with design intent', not bad, '; '.join(bad))

def on(net, ref, pin): return (ref, pin) in nets.get(net, set())

# 3. Jack pin mapping. Data directions MEASURED on the radio 2026-11-15: body TX on pin 3, head TX on pin 4.
for j in ('J1', 'J2'):
    check(f'{j} pin1 PB / pin2 GND / pin4 HEAD_TXD (head -> body, measured)',
          actual.get((j,'1'))=='PB' and actual.get((j,'2'))=='GND' and actual.get((j,'4'))=='HEAD_TXD')
check('J1 pin3 = BODY_TXD, J2 pin3 = HEAD_RXD (body -> head on pin 3, measured)', actual.get(('J1','3'))=='BODY_TXD' and actual.get(('J2','3'))=='HEAD_RXD')
check('HEAD_TXD direct copper J2.4 to J1.4', on('HEAD_TXD','J1','4') and on('HEAD_TXD','J2','4'))

# 4. PB never touches any MCU, opto, or signal net; PB only reaches U2 through R1
pb_nets = {'PB','PB_FILT'}
pb_refs = {r for n in pb_nets for r,_ in nets.get(n,())}
check('PB nets touch only jacks, R1, C5, C6, U2 and PWR_FLAG', pb_refs <= {'J1','J2','R1','C5','C6','U2','#FLG1'}, str(sorted(pb_refs)))
check('PB direct copper J1.1 to J2.1; board supply via R1', on('PB','J1','1') and on('PB','J2','1') and on('PB','R1','1') and on('PB_FILT','R1','2'))

# 5. Full-proxy data path: body -> MCU (tap) -> R2 -> head; JP1 is the only direct body/head bridge
hr = nets['HEAD_RXD']
check('HEAD_RXD connections limited to J2, JP1, R2, J5 (test tap)', {r for r,_ in hr} <= {'J2','JP1','R2','J5'}, str(sorted(hr)))
check('BODY_TXD connections limited to J1, JP1, R6 (tap)', {r for r,_ in nets['BODY_TXD']} <= {'J1','JP1','R6'}, str(sorted(nets['BODY_TXD'])))
check('Proxy output: U1 pin 2 (PC0, USART1 TX) -> R2 -> HEAD_RXD', on('HEAD_TX_MCU','U1','2') and on('HEAD_TX_MCU','R2','1') and on('HEAD_RXD','R2','2') and {r for r,_ in nets['HEAD_TX_MCU']} <= {'U1','R2'})
check('JP1 hard bypass is the only part bridging BODY_TXD and HEAD_RXD', ({r for r,_ in nets['BODY_TXD']} & {r for r,_ in nets['HEAD_RXD']}) == {'JP1'} and on('BODY_TXD','JP1','1') and on('HEAD_RXD','JP1','2'))
check('No U1 pin directly on any radio-line net', not any(r=='U1' for n in ('BODY_TXD','HEAD_RXD','HEAD_TXD') for r,_ in nets.get(n,())))

# 5b. Test header J5: listen-only taps, never directly on a radio line except the head input after R2
check('J5 taps: GND, TAP_BODY, TAP_HEAD, HEAD_RXD', [actual.get(('J5',k)) for k in '1234']==['GND','TAP_BODY','TAP_HEAD','HEAD_RXD'])
check('TAP_BODY/TAP_HEAD only reach the radio through R6/R7 10k', {r for r,_ in nets['TAP_BODY']} <= {'R6','U1','J5'} and {r for r,_ in nets['TAP_HEAD']} <= {'R7','U1','J5'})

# 6. ILL isolation: ILL_P/ILL_GND/ILL_LED_A never touch board nets
ill = {'ILL_P','ILL_GND','ILL_LED_A'}
ill_refs = {(r,p) for n in ill for r,p in nets.get(n,())}
check('ILL side isolated (only J3, R9, R10, D1, U3 LED pins)', {r for r,_ in ill_refs} <= {'J3','R9','R10','D1','U3'} and not ({('U3','3'),('U3','4')} & ill_refs))

# 7. UART pin plan matches AVR DB SPDIP-28 multiplexing (DS40002247B table 3-1)
plan = {'23':'TAP_BODY','22':'DBG_TX_MCU','3':'TAP_HEAD','2':'HEAD_TX_MCU','16':'XTAL32K1','17':'XTAL32K2','19':'UPDI'}
check('U1 USART0 PA1/PA0, USART1 PC1/PC0, XOSC32K PF0/PF1, UPDI', all(actual.get(('U1',k))==v for k,v in plan.items()))
check('U1 VDD/AVDD/VDDIO2 on +5V, GND/AGND on GND', all(actual.get(('U1',k))=='+5V' for k in ('6','14','20')) and all(actual.get(('U1',k))=='GND' for k in ('15','21')))

# 8. Hand calculations (datasheet values)
calc = {}
Vb = 5.0
R956 = 1000   # body TXD series resistor inside the radio (service manual p.84, IC951 3Y -> R956 1k -> J952-4)
R2 = 470; RPU_HEAD = 47000; ROUT_MCU_MAX = 117   # head CP913 pull-up (p.74); AVR output resistance worst case (VDD-0.7 V at 6 mA)
calc['proxy_low_at_head_V'] = 5.25*(R2+ROUT_MCU_MAX)/(R2+ROUT_MCU_MAX+RPU_HEAD)       # MCU low against head pull-up
calc['proxy_head_rc_us'] = (R2+ROUT_MCU_MAX)*570e-12*1e6                                # worst head-side C: 470 pF cable + 100 pF varistor
calc['jp1_with_u1_contention_mA'] = 5.25/(R956+25+R2+25)*1000                           # JP1 fitted while U1 still drives (misuse)
calc['jp1_bypass_low_at_head_V'] = 5.25*(R956+25)/(R956+25+RPU_HEAD)                    # U1 removed, JP1 fitted
def rv(ref):
    x = intent[ref]['value'].split()[0].lower()
    return float(x[:-1])*1e3 if x.endswith('k') else float(x.rstrip('r'))
R9, R10 = rv('R9'), rv('R10')
calc['ill_led_mA_at_13V'] = (13-1.15)/R9*1000 - 1.15/R10*1000
calc['ill_led_mA_at_9V'] = (9-1.15)/R9*1000 - 1.15/R10*1000
calc['ill_R9_W_at_14V'] = ((14-1.15)/R9)**2*R9
calc['ill_led_mA_at_2V'] = max(0.0, (2.0-1.15)/R9*1000 - 1.15/R10*1000)   # ILL+ residual/floating 2 V with lights off: R10 shunts all of it
calc['pb_fault_current_mA_R1_short'] = 10/150*1000
calc['R1_fault_W'] = 10**2/150
calc['est_board_current_mA'] = {'mcu_20MHz_active_typ':4.4,'ldo_iq':0.2,'opto_pullup_max':0.5,'taps':0.0}
calc['est_board_total_mA'] = round(sum(calc['est_board_current_mA'].values()),2)
check('Proxy low level at head < 1.5 V (TC4S81F VIL max)', calc['proxy_low_at_head_V'] < 1.5, f"{calc['proxy_low_at_head_V']:.2f} V")
check('Proxy edge RC at head < 1 us (bit = 17.4 us)', calc['proxy_head_rc_us'] < 1.0, f"{calc['proxy_head_rc_us']:.2f} us")
check('JP1 fitted with U1 present: contention <= 4 mA (HC4050 recommended)', calc['jp1_with_u1_contention_mA'] <= 4.0, f"{calc['jp1_with_u1_contention_mA']:.2f} mA")
check('JP1 bypass (U1 removed) low level at head < 1.5 V', calc['jp1_bypass_low_at_head_V'] < 1.5, f"{calc['jp1_bypass_low_at_head_V']:.2f} V")
check('ILL LED off with ILL+ at 2 V (lights off)', calc['ill_led_mA_at_2V'] == 0.0, f"{calc['ill_led_mA_at_2V']:.2f} mA")
check('ILL LED current >= 1.0 mA at 9 V input', calc['ill_led_mA_at_9V'] >= 1.0, f"{calc['ill_led_mA_at_9V']:.2f} mA")
check('Estimated board draw <= 10 mA PB target', calc['est_board_total_mA'] <= 10, f"{calc['est_board_total_mA']} mA (typical, not measured)")

out = {'results': results, 'calculations': calc, 'net_count': len(nets)}
(CHK/'design_checks.json').write_text(json.dumps(out, indent=2)+'\n')
for r in results: print(('PASS ' if r['pass'] else 'FAIL ')+r['check']+(' -- '+r['detail'] if r['detail'] and not r['pass'] else (' ('+r['detail']+')' if r['detail'] else '')))
print(f"{sum(r['pass'] for r in results)}/{len(results)} checks passed")
raise SystemExit(0 if all(r['pass'] for r in results) else 1)
