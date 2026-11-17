#!/usr/bin/env python3
"""Summarise checks/simulation/results_<sections>.json into the tables used by simulation_review.md (printed to stdout)."""
from pathlib import Path
import json, sys

BASE = Path(__file__).resolve().parent.parent
d = json.loads((BASE/'checks/simulation'/(sys.argv[1] if len(sys.argv) > 1 else 'results_data_ill_power.json')).read_text())
S, F, R = d['summary'], d['failures'], d['records']
print('Status:', S['status'], '| failures:', S['failure_count'], '| counts:', S['counts'], '| elapsed s:', S['elapsed_s'])
for f in F: print('  FAIL', f)

def agg(rs, k, fn):
    v = [r[k] for r in rs if r.get(k) is not None]
    return round(fn(v), 3) if v else '—'
print('\n## Data paths: worst case over all corners / as installed (260 pF body, 20 pF head)')
print('| mode | runs | head margin V | head edge skew us | head idle min V | body margin V | MCU tap margin V (body / head) | JP1 misuse peak mA (body / MCU) |')
for m in dict.fromkeys(r['mode'] for r in R['data']):
    rs = [r for r in R['data'] if r['mode'] == m]; inst = [r for r in rs if r['ccab_body'] == 260e-12]
    print(f"| {m} | {len(rs)} | {agg(rs,'head_margin_V',min)} / {agg(inst,'head_margin_V',min)} | {agg(rs,'head_edge_skew_us',max)} / {agg(inst,'head_edge_skew_us',max)} "
          f"| {agg(rs,'head_idle_min_V',min)} | {agg(rs,'body_margin_V',min)} | {agg(rs,'tap_body_schmitt_margin_V',min)} / {agg(rs,'tap_head_schmitt_margin_V',min)} | {agg(rs,'body_output_peak_mA',max)} / {agg(rs,'mcu_pin_peak_mA',max)} |")
print('Body stream at head before MCU forwards (min V):', agg([r for r in R['data'] if r['mode'] == 'proxy'], 'head_min_before_tx_V', min))

print('\n## ILL (J3 to ILL+ and chassis ground)')
for r in R['dc']:
    if r.get('test', '').startswith('ill'): print(r)
print('\n## Other DC'); [print(r) for r in R['dc'] if r.get('test') in ('5V_short', 'ldo_dead_backfeed')]
print('\n## Power (board current from PB)')
for r in R['power']:
    print(f"| PB {r['vpb']} V | head {r['ihead']} A | rout {r['mcu_rout']} | {r['board_mA']} mA | LDO in {r['ldo_in_V']} V | head PB {r['head_PB_V']} V |")
