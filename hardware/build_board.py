#!/usr/bin/env python3
"""Build the placed Kenwood proxy PCB from the verified netlist. Requires KiCad's pcbnew Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 build_board.py
Without --session: writes the placed board and checks/placement.dsn for Freerouting.
With --session checks/routing.ses: rebuilds placement, imports the routing, adds ground pours.
Regeneration overwrites manual PCB edits; back up first.
"""
from pathlib import Path
import json, argparse, re, xml.etree.ElementTree as ET
import pcbnew as p

BASE = Path(__file__).resolve().parent
SYS = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
PCB = BASE/'kenwood_proxy.kicad_pcb'
ap = argparse.ArgumentParser(); ap.add_argument('--session'); opt = ap.parse_args()
intent = json.loads((BASE/'design_intent.json').read_text())
xml = ET.parse(BASE/'checks/netlist.xml')
W, H = 54.0, 52.0
ILL_REGION = (37.5, 0.0, W, 23.8)        # isolated ILL+/GND area (top right, J3 on the top edge): no pours, no foreign tracks
ILL_KEEPOUT = (36.3, 0.0, W, 24.2)       # autorouter keepout: >2 mm beyond all ILL copper
HOLES = [(3.5, 3.5), (W-3.5, 3.5), (W-3.5, H-3.5), (3.5, H-3.5)]

b = p.BOARD(); b.SetCopperLayerCount(2); b.SetFileName(str(PCB))
mm = p.FromMM
def v(x, y): return p.VECTOR2I(mm(x), mm(y))
ds = b.GetDesignSettings()
ds.m_MinClearance = mm(.2); ds.m_CopperEdgeClearance = mm(.5); ds.m_TrackMinWidth = mm(.2)
ds.m_MinThroughDrill = mm(.3); ds.m_HoleClearance = mm(.25)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mm(.25)); nc.SetTrackWidth(mm(.3)); nc.SetViaDiameter(mm(.8)); nc.SetViaDrill(mm(.4))

nets = {}
for n in xml.findall('./nets/net'):
    name = n.attrib['name'].replace('/', '{slash}'); net = p.NETINFO_ITEM(b, name); b.Add(net); nets[name] = net
padnets = {(nd.attrib['ref'], nd.attrib['pin']): n.attrib['name'].replace('/', '{slash}') for n in xml.findall('./nets/net') for nd in n.findall('node')}

# Footprint origins (pad 1) in mm from the upper-left board corner, rotation in degrees.
pos = {
 'J1': (11.8, 8.3, 180), 'J2': (24.8, 8.3, 180),
 'R6': (3, 20.6, 0), 'R7': (16, 20.6, 0),
 'R2': (3, 25.0, 0), 'JP1': (16.5, 25.0, 90), 'C1': (26.32, 25.0, 180),
 'U1': (6.0, 36.0, 90),
 'Y1': (36.0, 25.0, 180), 'C7': (42.4, 30.0, 90), 'C8': (45.8, 30.0, 90),
 'C2': (42.5, 35.5, 90), 'C3': (13.5, 39.8, 0),
 'R11': (51.5, 40.0, 90),
 'R13': (19.0, 39.8, 0),
 'J4': (10.0, 46.0, 90),    # 1x3 0.1 in header, pins left to right GND UPDI TX
 'J5': (3.0, 16.5, 90),     # Rev B: 1x4 data-tap header, pins left to right GND B>H H>B HRX
 # power: bottom right
 'R1': (32.2, 42.5, 0), 'C6': (19.0, 48.5, 0), 'C5': (24.5, 48.5, 0), 'U2': (36.5, 48.5, 180), 'C4': (40.5, 48.5, 0),
 'TP2': (46.5, 37.4, 0),
 # isolated ILL block: top right, J3 mating face on the top edge
 'J3': (39.5, 9.42, 0), 'R9': (52.1, 15.8, 180), 'U3': (52.3, 19.5, 270), 'R10': (39.4, 19.3, 0), 'D1': (39.4, 22.3, 0),
 **{f'H{i+1}': (hx, hy, 0) for i, (hx, hy) in enumerate(HOLES)},
}
SILK_REFS = {'J1','J2','J3','J4','J5','JP1','U1','U2','U3','Y1'}
# 3D models KiCad's library lacks (used by renders and the 3D viewer only).
#   Micro-Fit 43045-0200: simplified stand-in from 3dmodels/make_microfit_model.py
#   DS26 horizontal crystal: the near-identical C26-LF model (same pad pitch and origin)
MODEL_OVERRIDES = {
    'Molex_Micro-Fit_3.0_43045-0200_2x01_P3.00mm_Horizontal': '${KIPRJMOD}/3dmodels/Molex_Micro-Fit_3.0_43045-0200_simplified.step',
    'Crystal_DS26_D2.0mm_L6.0mm_Horizontal': '${KICAD10_3DMODEL_DIR}/Crystal.3dshapes/Crystal_C26-LF_D2.1mm_L6.5mm_Horizontal.step',
}

fps = {}
for el in xml.findall('./components/comp'):
    ref = el.attrib['ref']; c = intent.get(ref, {})
    if not c.get('footprint'): continue
    lib, name = c['footprint'].split(':')
    libdir = BASE/'footprints'/(lib+'.pretty') if lib == 'Kenwood_Proxy' else SYS/(lib+'.pretty')
    fp = p.FootprintLoad(str(libdir), name)
    if fp is None: raise RuntimeError(c['footprint'])
    if name in MODEL_OVERRIDES:   # replace the library's model reference
        fp.Models().clear(); m = p.FP_3DMODEL(); m.m_Filename = MODEL_OVERRIDES[name]; fp.Add3DModel(m)
    fp.SetFPID(p.LIB_ID(lib, name)); fp.SetReference(ref); fp.SetValue(c['value'])
    for field in el.findall('./fields/field'):
        if field.attrib['name'] not in ('Reference', 'Value', 'Footprint'):
            fp.SetField(field.attrib['name'], field.text or ''); fp.GetField(field.attrib['name']).SetVisible(False)
    path = p.KIID_PATH()
    for s in (el.find('sheetpath').attrib['tstamps'] + el.findtext('tstamps')).split('/'):
        if s: path.push_back(p.KIID(s))
    fp.SetPath(path); fp.SetSheetname(el.find('sheetpath').attrib['names']); fp.SetSheetfile(c['sheet']+'.kicad_sch')
    if ref.startswith('H'): fp.SetAttributes(fp.GetAttributes() | p.FP_BOARD_ONLY)
    b.Add(fp)
    x, y, a = pos[ref]; fp.SetOrientationDegrees(a); fp.SetPosition(v(x, y)); fps[ref] = fp
    for pad in fp.Pads():
        nm = padnets.get((ref, pad.GetNumber()))
        if nm: pad.SetNet(nets[nm])
        pin = c['pins'].get(pad.GetNumber(), {})
        if pin: pad.SetPinFunction(pin.get('name', ''))
    fp.Value().SetVisible(False)
    r = fp.Reference(); r.SetTextSize(v(.9, .9)); r.SetTextThickness(mm(.14))
    r.SetTextAngle(p.EDA_ANGLE(0, p.DEGREES_T)); r.SetKeepUpright(True)
    r.SetLayer(p.F_SilkS)
    bb = fp.GetBoundingBox(False)
    if ref.startswith('H'): r.SetVisible(False)
    elif ref.startswith('TP'): r.SetPosition(v(x, y - 2.4)); r.SetTextSize(v(.8, .8))
    elif ref.startswith('C') and a in (0, 180):
        r.SetPosition(v(p.ToMM(bb.Centre().x), y - (3.6 if ref in ('C4', 'C6') else 2.2))); r.SetTextSize(v(.8, .8))   # above caps
    elif ref.startswith(('R', 'D')) and a in (0, 180):
        r.SetPosition(v(p.ToMM(bb.Centre().x), y))   # centred on the axial body
        r.SetTextSize(v(.8, .8))
    else:
        r.SetPosition(v(p.ToMM(bb.Centre().x), p.ToMM(bb.GetTop()) - 0.9))
    override = {'J1': (4.6, 11.4), 'J2': (33.4, 11.4), 'U1': (22.5, 32.2), 'J3': (45.3, 5.2), 'J4': (7.4, 46.0), 'C3': (10.8, 39.8), 'C4': (46.0, 48.5), 'C2': (42.5, 37.4), 'R11': (48.6, 32.6), 'JP1': (17.8, 22.9), 'C6': (20.0, 44.9), 'U3': (51.03, 23.3), 'J5': (13.4, 16.5)}
    if ref in override: r.SetPosition(v(*override[ref]))
    if ref == 'D1':   # cathode band on the body is enough; the 'K' text would sit on R10's pad
        for g in list(fp.GraphicalItems()):
            if g.GetClass() == 'PCB_TEXT' and g.GetText() == 'K': fp.Remove(g)

# Board edge
for a_, z_ in [((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))]:
    s = p.PCB_SHAPE(); s.SetShape(p.SHAPE_T_SEGMENT); s.SetStart(v(*a_)); s.SetEnd(v(*z_)); s.SetLayer(p.Edge_Cuts); s.SetWidth(mm(.05)); b.Add(s)

def track(net, pts, width=.4, layer=p.B_Cu):
    for a_, z_ in zip(pts, pts[1:]):
        t = p.PCB_TRACK(b); t.SetStart(v(*a_)); t.SetEnd(v(*z_)); t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); b.Add(t)

# Hand-routed isolated ILL nets (all inside ILL_REGION).
track('ILL_P',     [(39.5, 9.42), (50.8, 9.42), (52.1, 10.72), (52.1, 15.8)], layer=p.F_Cu)     # J3.1 -> R9.1
track('ILL_LED_A', [(39.4, 15.8), (39.4, 22.3)], layer=p.F_Cu)                                   # R9.2, R10.1, D1.K
track('ILL_LED_A', [(39.4, 15.8), (41.0, 17.4), (51.0, 17.4), (52.3, 18.7), (52.3, 19.5)])       # -> U3.1 (B.Cu)
track('ILL_GND',   [(39.5, 12.42), (45.8, 12.42), (47.02, 13.64), (47.02, 22.3)], layer=p.F_Cu)  # J3.2 -> R10.2, D1.A
track('ILL_GND',   [(47.02, 19.3), (49.56, 19.3), (49.76, 19.5)], layer=p.F_Cu)                  # -> U3.2

def zone_rule(rect, tracks=True, fills=True, vias=True):
    for layer in (p.F_Cu, p.B_Cu):
        z = p.ZONE(b); z.SetLayer(layer); z.SetIsRuleArea(True); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowZoneFills(fills)
        o = z.Outline(); o.NewOutline()
        x1, y1, x2, y2 = rect
        for xx, yy in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]: o.Append(mm(xx), mm(yy))
        b.Add(z)
# Mounting holes: keep copper away from screw heads.
for hx, hy in HOLES:
    zone_rule((hx-3.4, hy-3.4, hx+3.4, hy+3.4))
# ILL region: no copper pour (tracks allowed so the pre-routed ILL nets pass DRC).
zone_rule(ILL_REGION, tracks=False, vias=False, fills=True)

def label(t, x, y, size=1.0, layer=p.F_SilkS, angle=0):
    q = p.PCB_TEXT(b); q.SetText(t); q.SetPosition(v(x, y)); q.SetTextSize(v(size, size)); q.SetTextThickness(mm(.15))
    q.SetLayer(layer); q.SetTextAngle(p.EDA_ANGLE(angle, p.DEGREES_T)); b.Add(q)
label('BODY', 4.6, 13.0, .8); label('HEAD', 26.3, 13.9, .8)
label('1=ILL+ 2=GND', 48.3, 10.9, .8)
label('GND UPDI TX', 12.54, 48.9, .8)
label('KENWOOD PROXY REV B', 23.5, 15.4, .8)
label('JP1: ONLY WITH U1 REMOVED', 24.5, 17.2, .8)
label('GND B>H H>B HRX', 6.9, 18.65, .8)
# Isolation boundary line on silk
for a_, z_ in [((ILL_REGION[0], 14.0), (ILL_REGION[0], 24.5)), ((ILL_REGION[0], 24.5), (48.0, 24.5))]:
    s = p.PCB_SHAPE(); s.SetShape(p.SHAPE_T_SEGMENT); s.SetStart(v(*a_)); s.SetEnd(v(*z_)); s.SetLayer(p.F_SilkS); s.SetWidth(mm(.15)); b.Add(s)

if opt.session:
    assert p.ImportSpecctraSES(b, str(Path(opt.session).resolve()))
    # Ground pours on both layers, excluding the ILL region (L-shaped outline).
    x1, y2 = ILL_REGION[0], ILL_REGION[3]
    outline = [(0.4, 0.4), (x1-1.8, 0.4), (x1-1.8, y2+1.8), (W-0.4, y2+1.8), (W-0.4, H-0.4), (0.4, H-0.4)]
    for layer in (p.F_Cu, p.B_Cu):
        z = p.ZONE(b); z.SetLayer(layer); z.SetNet(nets['GND']); z.SetLocalClearance(mm(.3)); z.SetMinThickness(mm(.25))
        z.SetThermalReliefGap(mm(.4)); z.SetThermalReliefSpokeWidth(mm(.4)); z.SetPadConnection(p.ZONE_CONNECTION_THERMAL)
        o = z.Outline(); o.NewOutline()
        for xx, yy in outline: o.Append(mm(xx), mm(yy))
        z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)   # no copper islands fed by a single pad
        z.SetAssignedPriority(0); b.Add(z)
    # Remove autorouter stubs: tracks with a free end, then vias left without tracks.
    def connected(pt, layer, me):
        for t in b.GetTracks():
            if t is me or t.GetNetCode() != me.GetNetCode(): continue
            if t.GetClass() == 'PCB_VIA':
                if (t.GetPosition() - pt).EuclideanNorm() <= t.GetWidth(layer)//2: return True
            elif t.IsOnLayer(layer) and t.HitTest(pt, 0): return True
        for fp in b.GetFootprints():
            for pd in fp.Pads():
                if pd.GetNetCode() == me.GetNetCode() and pd.IsOnLayer(layer) and pd.HitTest(pt): return True
        return False
    removed = 0
    while True:
        dead = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and
                not (connected(t.GetStart(), t.GetLayer(), t) and connected(t.GetEnd(), t.GetLayer(), t))]
        vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and
                sum(1 for u in b.GetTracks() if u.GetClass() == 'PCB_TRACK' and u.GetNetCode() == t.GetNetCode()
                    and (u.GetStart() == t.GetPosition() or u.GetEnd() == t.GetPosition())) < 2]
        if not dead and not vias: break
        for t in dead + vias: b.Remove(t); removed += 1
    # Doubled-back spurs: an endpoint whose only incident tracks all return to one point, with no pad there.
    while True:
        from collections import defaultdict
        inc = defaultdict(list)
        for t in b.GetTracks():
            if t.GetClass() != 'PCB_TRACK': continue
            for e, o in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                inc[(t.GetLayer(), t.GetNetCode(), e.x, e.y)].append((t, (o.x, o.y)))
        spur = []
        for (layer, net, x, y), lst in inc.items():
            others = {o for _, o in lst}
            onpad = any(pd.GetNetCode() == net and pd.IsOnLayer(layer) and pd.HitTest(p.VECTOR2I(x, y))
                        for fp in b.GetFootprints() for pd in fp.Pads())
            if len(lst) >= 2 and len(others) == 1 and not onpad:
                spur += [t for t, _ in lst]
        spur = list({id(t): t for t in spur}.values())
        if not spur: break
        for t in spur: b.Remove(t); removed += 1
    print('Removed', removed, 'dangling track/via items')
    # Rev B hand fix: Freerouting (999 passes) left PB's via-to-track link beside J4 unrouted in the 0.6 mm
    # power class. Joins the PB via and the nearest PB bottom-layer track end at their exact positions
    # (clears J4 pin 1 by about 0.45 mm). Tied to checks/routing.ses; re-check if the routing is redone.
    pbn = nets['PB'].GetNetCode()
    def near(items, x, y):
        tgt = v(x, y); return min(items, key=lambda q: (q - tgt).EuclideanNorm())
    pb_via = near([t.GetPosition() for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == pbn], 8.3965, 45.3524)
    pb_end = near([e for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetCode() == pbn and t.GetLayer() == p.B_Cu
                   for e in (t.GetStart(), t.GetEnd())], 8.3965, 46.9458)
    assert (pb_via - v(8.3965, 45.3524)).EuclideanNorm() < mm(.05) and (pb_end - v(8.3965, 46.9458)).EuclideanNorm() < mm(.05)
    t = p.PCB_TRACK(b); t.SetStart(pb_via); t.SetEnd(pb_end); t.SetWidth(mm(.6)); t.SetLayer(p.B_Cu); t.SetNet(nets['PB']); t.SetLocked(True); b.Add(t)
    # GND stitching vias on a 3 mm grid wherever they clear all foreign copper; they also tie any
    # trace-enclosed pour fragments to the other layer. Vias not landing in pour on both layers are removed.
    def blocked(x, y):
        if ILL_KEEPOUT[0] - 1 <= x <= ILL_KEEPOUT[2] + 1 and ILL_KEEPOUT[1] - 1 <= y <= ILL_KEEPOUT[3] + 1: return True
        for hx, hy in HOLES:
            if abs(x-hx) < 4 and abs(y-hy) < 4: return True
        return not (1.5 < x < W-1.5 and 1.5 < y < H-1.5)
    probe = p.PCB_VIA(b); probe.SetWidth(mm(.8)); probe.SetDrill(mm(.4)); probe.SetLayerPair(p.F_Cu, p.B_Cu)
    others = []
    for t in b.GetTracks():
        for layer in (p.F_Cu, p.B_Cu):
            if t.IsOnLayer(layer): others.append((layer, t.GetNetname(), t.GetEffectiveShape(layer)))
    for fp in b.GetFootprints():
        for pd in fp.Pads():
            for layer in (p.F_Cu, p.B_Cu):
                if pd.IsOnLayer(layer) or pd.GetAttribute() == p.PAD_ATTRIB_NPTH:
                    others.append((layer, pd.GetNetname(), pd.GetEffectiveShape(layer)))
    stitch = []
    y = 3.0
    while y < H:
        x = 3.0
        while x < W:
            if not blocked(x, y):
                probe.SetPosition(v(x, y))
                ok = all(not shp.Collide(probe.GetEffectiveShape(layer), mm(.45 if net == 'GND' else .35))
                         for layer, net, shp in others)
                if ok:
                    via = p.PCB_VIA(b); via.SetPosition(v(x, y)); via.SetWidth(mm(.8)); via.SetDrill(mm(.4))
                    via.SetLayerPair(p.F_Cu, p.B_Cu); via.SetNet(nets['GND']); b.Add(via); stitch.append(via)
            x += 3.0
        y += 3.0
    filler = p.ZONE_FILLER(b); filler.Fill(b.Zones())
    def in_pour(via, layer):
        return any(z.GetNetname() == 'GND' and z.IsOnLayer(layer) and z.GetFilledPolysList(layer).Contains(via.GetPosition())
                   for z in b.Zones() if not z.GetIsRuleArea())
    dead = [vv for vv in stitch if not (in_pour(vv, p.F_Cu) and in_pour(vv, p.B_Cu))]
    for vv in dead: b.Remove(vv)
    print('Stitching vias:', len(stitch) - len(dead))
    filler.Fill(b.Zones())

p.SaveBoard(str(PCB), b)

if not opt.session:
    dsnp = BASE/'checks/placement.dsn'
    assert p.ExportSpecctraDSN(b, str(dsnp))
    text = dsnp.read_text()
    # Wider supply class
    power = ['PB', 'PB_FILT', '+5V']
    start = text.index('(class kicad_default'); end = text.index('(circuit', start)
    block = text[start:end]
    for name in power:
        block = re.sub(r'(?<![A-Za-z0-9_+"])' + re.escape(name) + r'(?![A-Za-z0-9_])', '', block)
        block = block.replace(' "'+name+'"', '')
    text = text[:start] + block + text[end:]
    quoted = ' '.join('"'+n+'"' if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', n) else n for n in power)
    text = text.replace('(class kicad_default', '(class power ' + quoted + ' (circuit (use_via "Via[0-1]_800:400_um")) (rule (width 600) (clearance 250)))\n    (class kicad_default', 1)
    # Autorouter keepout over the isolated ILL region (DSN units um, y inverted).
    x1, y1, x2, y2 = ILL_KEEPOUT
    ko = ''.join(f'\n    (keepout "ill_iso_{l}" (rect {l} {x1*1000:.0f} {-y2*1000:.0f} {x2*1000:.0f} {-y1*1000:.0f}))' for l in ('F.Cu', 'B.Cu'))
    text = text.replace('(structure', '(structure' + ko, 1)
    dsnp.write_text(text)
    print('Wrote', dsnp)

proj = BASE/'kenwood_proxy.kicad_pro'
settings = json.loads(proj.read_text())
settings.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {}).update(
    {'min_clearance': .2, 'min_through_hole_diameter': .3, 'min_track_width': .2, 'min_copper_edge_clearance': .5, 'min_hole_clearance': .25})
settings['text_variables'] = {'REVISION': 'B'}
proj.write_text(json.dumps(settings, indent=2)+'\n')
print('Placed', len(fps), 'footprints on', W, 'x', H, 'mm')
