"""Draw the assembly-guide board figures (docs/img/*.svg) from hardware/kenwood_proxy.kicad_pcb.

Run with KiCad's Python (KiCad 10), from the repo root:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 docs/tools/make_figures.py

Each figure is a top or underside view of the board. Highlighted parts are drawn in colour with
their reference; every other part is a faint outline. Rings mark individual pins ("U1.20").
Underside views are mirrored left to right, as the board looks after flipping it like a page.
"""
import math, os, sys
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs' / 'img'
board = p.LoadBoard(str(ROOT / 'hardware' / 'kenwood_proxy.kicad_pcb'))
mm = p.ToMM
W, H = 54.0, 52.0


def pt(v):
    return (mm(v.x), mm(v.y))


def shape_paths(g):
    """Return a list of polylines (list of (x, y)) and circles (cx, cy, r) for a PCB_SHAPE."""
    s = g.GetShape()
    if s == p.SHAPE_T_SEGMENT:
        return [[pt(g.GetStart()), pt(g.GetEnd())]], []
    if s == p.SHAPE_T_RECTANGLE:
        c = [pt(v) for v in g.GetRectCorners()]
        return [c + [c[0]]], []
    if s == p.SHAPE_T_CIRCLE:
        cx, cy = pt(g.GetCenter())
        return [], [(cx, cy, mm(g.GetRadius()))]
    if s == p.SHAPE_T_ARC:
        cx, cy = pt(g.GetCenter()); r = mm(g.GetRadius())
        a0 = math.atan2(pt(g.GetStart())[1] - cy, pt(g.GetStart())[0] - cx)
        a1 = math.atan2(pt(g.GetEnd())[1] - cy, pt(g.GetEnd())[0] - cx)
        am = math.atan2(pt(g.GetArcMid())[1] - cy, pt(g.GetArcMid())[0] - cx)
        # walk from a0 to a1 through am
        def norm(a): return a % (2 * math.pi)
        d1 = norm(a1 - a0); dm = norm(am - a0)
        sweep = d1 if dm <= d1 else d1 - 2 * math.pi
        n = max(6, int(abs(sweep) / 0.15))
        return [[(cx + r * math.cos(a0 + sweep * i / n), cy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]], []
    if s == p.SHAPE_T_POLY:
        o = g.GetPolyShape().Outline(0)
        c = [pt(o.CPoint(i)) for i in range(o.PointCount())]
        return [c + [c[0]]], []
    return [], []


# ---------------------------------------------------------------- collect geometry
parts = {}
for f in board.GetFootprints():
    ref = f.GetReference()
    lines, circles = [], []
    for g in f.GraphicalItems():
        if board.GetLayerName(g.GetLayer()) == 'F.Fab' and isinstance(g, p.PCB_SHAPE):
            l, c = shape_paths(g); lines += l; circles += c
    pads = []
    for pd in f.Pads():
        x, y = pt(pd.GetPosition())
        sx, sy = mm(pd.GetSize(p.F_Cu).x), mm(pd.GetSize(p.F_Cu).y)
        shp = pd.GetShape(p.F_Cu)
        kind = 'circle' if shp == p.PAD_SHAPE_CIRCLE else 'oval' if shp == p.PAD_SHAPE_OVAL else 'rect'
        drill = mm(pd.GetDrillSize().x)
        pads.append(dict(num=pd.GetNumber(), x=x, y=y, sx=sx, sy=sy, kind=kind,
                         rot=pd.GetOrientation().AsDegrees(), drill=drill,
                         plated=pd.GetAttribute() == p.PAD_ATTRIB_PTH))
    bb = f.GetBoundingBox(False)
    parts[ref] = dict(lines=lines, circles=circles, pads=pads,
                      cx=mm(bb.GetCenter().x), cy=mm(bb.GetCenter().y),
                      x0=mm(bb.GetLeft()), y0=mm(bb.GetTop()), x1=mm(bb.GetRight()), y1=mm(bb.GetBottom()))

# ---------------------------------------------------------------- render
CSS = '''
.bd{fill:#4b2f6e;stroke:#2c1a44;stroke-width:.3}
.fab{fill:none;stroke:#9c86b8;stroke-width:.15;stroke-linecap:round;stroke-linejoin:round}
.pad{fill:#b9a37a}.hole{fill:#2c1a44}.npth{fill:#1f122f}
.on .fab{stroke:#ffd23f;stroke-width:.35}
.on .pad{fill:#ffd23f}
.under .fab{stroke-dasharray:.6 .5;opacity:.6}
.ref{font:700 2.1px system-ui,-apple-system,Segoe UI,sans-serif;fill:#ffffff;paint-order:stroke;stroke:#2c1a44;stroke-width:.5px;text-anchor:middle;dominant-baseline:central}
.ring{fill:none;stroke:#3ff0ff;stroke-width:.4}
.rlab{font:700 1.7px system-ui,-apple-system,Segoe UI,sans-serif;fill:#3ff0ff;paint-order:stroke;stroke:#2c1a44;stroke-width:.4px;text-anchor:middle;dominant-baseline:central}
.cap{font:600 2.2px system-ui,-apple-system,Segoe UI,sans-serif;fill:#d9cdea}
.edge{font:600 1.7px system-ui,-apple-system,Segoe UI,sans-serif;fill:#d9cdea;text-anchor:middle}
'''


def pad_svg(pd):
    x, y, sx, sy = pd['x'], pd['y'], pd['sx'], pd['sy']
    out = []
    if not pd['plated']:
        return f'<circle class="npth" cx="{x:.3f}" cy="{y:.3f}" r="{pd["drill"]/2:.3f}"/>'
    if pd['kind'] == 'circle':
        out.append(f'<circle class="pad" cx="{x:.3f}" cy="{y:.3f}" r="{sx/2:.3f}"/>')
    else:
        rx = min(sx, sy) / 2 if pd['kind'] == 'oval' else 0.12
        out.append(f'<rect class="pad" x="{x-sx/2:.3f}" y="{y-sy/2:.3f}" width="{sx:.3f}" height="{sy:.3f}" rx="{rx:.3f}" '
                   f'transform="rotate({-pd["rot"]:.1f} {x:.3f} {y:.3f})"/>')
    if pd['drill'] > 0:
        out.append(f'<circle class="hole" cx="{x:.3f}" cy="{y:.3f}" r="{pd["drill"]/2:.3f}"/>')
    return ''.join(out)


def part_svg(ref, on):
    q = parts[ref]
    s = [f'<g class="{"on" if on else "off"}">']
    for l in q['lines']:
        s.append('<polyline class="fab" points="' + ' '.join(f'{x:.3f},{y:.3f}' for x, y in l) + '"/>')
    for cx, cy, r in q['circles']:
        s.append(f'<circle class="fab" cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}"/>')
    for pd in q['pads']:
        s.append(pad_svg(pd))
    s.append('</g>')
    return ''.join(s)


def figure(name, on=(), rings=(), under=False, zoom=None, caption=None, labels=None):
    """on: refs to highlight; rings: 'REF.pin' tokens; zoom: (x, y, w, h) in board mm (top-view coords)."""
    on = set(on)
    x0, y0, w, h = zoom or (-2, -4, W + 4, H + 7)
    if under:  # mirror the viewport too
        x0 = W - (x0 + w)
    mir = 'translate(54 0) scale(-1 1)' if under else ''
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.2f} {y0:.2f} {w:.2f} {h:.2f}" '
         f'width="{720 if not zoom else min(560, w * 24):.0f}" role="img"><style>{CSS}</style>',
         f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#1b1424"/>',
         f'<g class="{"under" if under else ""}" transform="{mir}">',
         f'<rect class="bd" x="0" y="0" width="{W}" height="{H}" rx="1"/>']
    for ref in sorted(parts):
        if ref not in on: s.append(part_svg(ref, False))
    for ref in sorted(on): s.append(part_svg(ref, True))
    s.append('</g>')

    def X(x): return W - x if under else x
    # references of highlighted parts
    ringed = {t.split('.')[0] for t in rings}
    for ref in sorted(on - ringed):
        q = parts[ref]
        lab = (labels or {}).get(ref, ref)
        y = q['cy'] if len(q['pads']) > 1 else q['y0'] - 1.6   # test pads: name above the pad
        s.append(f'<text class="ref" x="{X(q["cx"]):.2f}" y="{y:.2f}">{lab}</text>')
    # pin rings: the pin number goes outside the ring, away from the part's centre
    ring_refs = []
    lowest = {}
    for tok in rings:
        ref, num = tok.split('.')
        side = None
        if ':' in num: num, side = num.split(':')
        q = parts[ref]
        pd = next(d for d in q['pads'] if d['num'] == num)
        r = max(pd['sx'], pd['sy']) / 2 + .35
        s.append(f'<circle class="ring" cx="{X(pd["x"]):.3f}" cy="{pd["y"]:.3f}" r="{r:.2f}"/>')
        if len(q['pads']) > 1:
            if side:   # explicit label side: n/s/e/w as seen in the figure
                dx, dy = {'n': (0, -1), 's': (0, 1), 'e': (1, 0), 'w': (-1, 0)}[side]
            elif len({round(d['y'], 2) for d in q['pads']}) == 1:   # single row across: label below
                dx, dy = 0, 1
            elif len({round(d['x'], 2) for d in q['pads']}) == 1:   # single column: label to the side
                dx, dy = (-1 if under else 1), 0
            else:      # away from the part's centre, snapped to the dominant axis
                hw, hh = max(.5, (q['x1'] - q['x0']) / 2), max(.5, (q['y1'] - q['y0']) / 2)
                ex, ey = (pd['x'] - q['cx']) / hw, (pd['y'] - q['cy']) / hh
                dx, dy = ((1 if ex >= 0 else -1), 0) if abs(ex) > abs(ey) else (0, (1 if ey >= 0 else -1))
                if under: dx = -dx
            s.append(f'<text class="rlab" x="{X(pd["x"]) + dx * (r + 1.0):.3f}" y="{pd["y"] + dy * (r + 1.0):.3f}">{num}</text>')
        if ref not in ring_refs: ring_refs.append(ref)
        lowest[ref] = max(lowest.get(ref, -99), pd['y'] + r)
    for ref in ring_refs:  # name the parts whose pins are ringed
        q = parts[ref]
        n = len(q['pads'])
        y = q['cy'] if n >= 8 else q['y0'] - 1.6 if n == 1 else lowest[ref] + 3.2   # big parts: centre; else below the rings
        s.append(f'<text class="ref" x="{X(q["cx"]):.2f}" y="{y:.2f}">{ref}</text>')
    if not zoom:
        s.append(f'<text class="edge" x="{W/2}" y="-1.4">↑ connector edge</text>')
        s.append(f'<text class="cap" x="{x0 + .8:.2f}" y="{y0 + h - 1:.2f}">{"UNDERSIDE (mirrored)" if under else "TOP"}</text>')
    s.append('</svg>')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.svg').write_text(''.join(s))


# ---------------------------------------------------------------- the figures used by docs/assembly.md
ALL = sorted(r for r in parts if not r.startswith('H'))
F = figure
F('map', on=ALL)
F('bare_continuity', under=True, rings=['J1.1:n', 'J1.2:s', 'J1.3:n', 'J1.4:s', 'J2.1:n', 'J2.2:s', 'J2.3:n', 'J2.4:s'], zoom=(4, 2, 26, 14))
F('bare_short', under=True, rings=['R1.1', 'TP2.1'])
F('r_10k', on=['R6', 'R7', 'R11'])
F('r_470', on=['R2', 'R13'])
F('r_680', on=['R10'])
F('r_2k2', on=['R9'])
F('r_150', on=['R1'])
F('d1', on=['D1'], zoom=(30, 13, 20, 14))
F('y1', on=['Y1'], zoom=(28, 18, 22, 14))
F('y1_check', on=['Y1'], rings=['Y1.1:n', 'Y1.2:n', 'U1.16:s', 'U1.17:s'], zoom=(28, 18, 22, 14))
F('socket', on=['U1'])
F('u3', on=['U3'], zoom=(38, 10, 16, 20))
F('c_100n', on=['C1', 'C2', 'C3', 'C5'])
F('c_15p', on=['C7', 'C8'], zoom=(36, 22, 16, 14))
F('headers', on=['JP1', 'J4', 'J5'])
F('u2', on=['U2'], zoom=(26, 40, 24, 12))
F('c4', on=['C4'], zoom=(30, 40, 20, 12))
F('c6', on=['C6'], zoom=(12, 40, 20, 12))
F('j3', on=['J3'], zoom=(28, -1, 26, 18))
F('jacks', on=['J1', 'J2'], zoom=(0, -1, 34, 20))
F('power_check', on=['R1', 'TP2'], rings=['R1.1', 'TP2.1', 'U1.20', 'U1.21', 'U1.6', 'U1.14'])
F('ill_check', on=['J3'], rings=['J3.1', 'J3.2', 'U1.7'])
F('j2_check', under=True, on=['TP2'], rings=['J2.1:n', 'J2.2:s', 'J2.3:n', 'J2.4:s', 'TP2.1'])
F('prog', on=['J4'], rings=['J4.1', 'J4.2', 'J4.3'], zoom=(2, 38, 22, 13))
F('j5', on=['J5'], rings=['J5.1', 'J5.2', 'J5.3', 'J5.4'], zoom=(-1, 10, 20, 12))
F('bypass', on=['JP1', 'U1'])
print('figures written to', OUT)
