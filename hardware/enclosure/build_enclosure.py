"""Kenwood proxy Rev A enclosure: base tray + cover, generated with FreeCAD.

Run:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_enclosure.py
Writes kp_case_base.stl, kp_case_cover.stl, kp_case.step and preview PNGs next to this file,
and checks the case against envelopes of the tall parts.

Coordinates: X = board x (mm, left to right), Y = -board y (the connector edge is at Y = 0,
the board extends to Y = -52), Z up with the base floor underside at Z = 0. Board positions
come from build_board.py (54 x 52 mm, M3 holes 3.5 mm in from each corner).
"""
import os, sys
import FreeCAD as App
import Part, Mesh

_report = []
def log(*a):
    _report.append(' '.join(str(x) for x in a))

HERE = os.path.dirname(os.path.abspath(__file__))
V = App.Vector

# ---------------------------------------------------------------- parameters
BW, BD, PCB = 54.0, 52.0, 1.6
HOLES = [(3.5, 3.5), (50.5, 3.5), (50.5, 48.5), (3.5, 48.5)]   # board coords
GAP = 0.5            # board edge to inner wall
WALL = 2.0
FLOOR = 2.0
STANDOFF = 4.0       # under-board clearance for leads and connector pegs
HEADROOM = 16.0      # board top to ceiling (tallest part: 4P4C jack, 14.5 mm)
TOP = 2.0
TONGUE_W, TONGUE_H, FIT = 1.0, 1.5, 0.2    # base-to-cover locating lip and clearance
WIN_CLR = 0.5        # clearance around each connector face
SCREW_L = 14.0       # M3 screw length; heads sit proud under the floor (no counterbore)
CORNER_R = 3.0       # outer vertical corner radius (wall stays >= 1.5 mm at the corners)

# Connector faces on the front edge: (name, x_left, x_right, height above board top).
JACK_H = 14.5        # Wurth 615004143821 datasheet
MICROFIT_H = 10.3    # Molex 43045 mated height 10.29 mm; measure the real part before printing
CONNECTORS = [
    ('BODY', 8.33, 18.33, JACK_H),
    ('HEAD', 21.33, 31.33, JACK_H),
    ('ILL', 35.42, 43.58, MICROFIT_H + 3.0),   # extra height: receptacle latch lever + fingertip
]

# Tall-part envelopes for the interference check: (name, x0, x1, y0, y1, height).
PARTS = [
    ('J1', 8.33, 18.33, 0.0, 13.0, JACK_H), ('J2', 21.33, 31.33, 0.0, 13.0, JACK_H),
    ('J3', 35.42, 43.58, 0.0, 13.7, MICROFIT_H + 1.0),
    ('U1+socket', 4.6, 40.4, 27.0, 37.4, 9.5), ('C4', 38.7, 44.8, 45.5, 51.5, 12.0),
    ('C6', 17.0, 23.0, 46.0, 51.0, 8.0), ('U2', 30.6, 37.3, 46.0, 51.0, 6.0),
    ('R1', 30.8, 47.4, 40.2, 44.8, 5.0), ('J4', 8.7, 16.4, 44.7, 47.3, 8.6),
    ('JP1', 15.2, 20.4, 21.6, 26.4, 8.6), ('U3', 48.2, 53.9, 18.4, 28.2, 5.0),
]

# Derived heights
Z_BOARD = FLOOR + STANDOFF           # board underside
Z_SPLIT = Z_BOARD + PCB              # board top = base/cover split
Z_CEIL = Z_SPLIT + HEADROOM
Z_TOP = Z_CEIL + TOP

X0, X1 = -GAP, BW + GAP              # cavity
Y0, Y1 = -(BD + GAP), GAP
OX0, OX1, OY0, OY1 = X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rbox(x0, x1, y0, y1, z0, z1, r):
    """Box with rounded vertical edges."""
    b = box(x0, x1, y0, y1, z0, z1)
    if r <= 0.05:
        return b
    vert = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(r, vert)


def outer(z0, z1, inset=0.0):
    """Outer shell outline, inset from the outside surface, with matching corner radius."""
    return rbox(OX0 + inset, OX1 - inset, OY0 + inset, OY1 - inset, z0, z1, CORNER_R - inset)


def cyl(x, y, r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0))


def ring(z0, z1, inset0, inset1):
    """Band of the outer wall between insets inset0..inset1 measured from the outside."""
    return outer(z0, z1, inset0).cut(outer(z0 - 1, z1 + 1, inset1))


def windows(z0, z1):
    s = None
    for _, xl, xr, h in CONNECTORS:
        w = box(xl - WIN_CLR, xr + WIN_CLR, Y1 - 1, OY1 + 1, z0, min(z1, Z_SPLIT + h + WIN_CLR))
        s = w if s is None else s.fuse(w)
    return s


# ---------------------------------------------------------------- base
base = outer(0, Z_SPLIT).cut(box(X0, X1, Y0, Y1, FLOOR, Z_SPLIT + 1))
base = base.fuse(ring(Z_SPLIT, Z_SPLIT + TONGUE_H, 0, TONGUE_W))     # locating lip, outer edge
base = base.cut(windows(Z_SPLIT - 0.01, Z_SPLIT + TONGUE_H + 1))     # lip must not block the plugs
for hx, hy in HOLES:
    x, y = hx, -hy
    base = base.fuse(cyl(x, y, 3.25, FLOOR - 0.01, Z_BOARD))
    base = base.cut(cyl(x, y, 1.7, -1, Z_BOARD + 1))                 # M3 clearance
base = base.removeSplitter()

# ---------------------------------------------------------------- cover
cover = outer(Z_SPLIT, Z_TOP).cut(box(X0, X1, Y0, Y1, Z_SPLIT - 1, Z_CEIL))
cover = cover.cut(ring(Z_SPLIT - 1, Z_SPLIT + TONGUE_H + FIT, -1, TONGUE_W + FIT))   # seat over the lip
cover = cover.cut(windows(Z_SPLIT - 1, Z_CEIL))
for hx, hy in HOLES:
    x, y = hx, -hy
    cover = cover.fuse(cyl(x, y, 3.0, Z_SPLIT, Z_CEIL + 0.01))       # posts clamp the board
    cover = cover.cut(cyl(x, y, 1.3, Z_SPLIT - 1, Z_SPLIT + 12.0))   # 2.6 mm pilot for M3, 12 deep

# Engraved labels on the top, above each opening.
FONT = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def engrave(shape, text, xc, yc, size, depth=0.6):
    try:
        chars = Part.makeWireString(text, os.path.dirname(FONT) + '/', os.path.basename(FONT), size, 0)
    except Exception as e:
        log('label skipped:', text, e)
        return shape
    faces = []
    for ch in chars:
        if ch:
            faces.append(Part.makeFace(ch, 'Part::FaceMakerBullseye'))
    if not faces:
        return shape
    comp = Part.Compound(faces)
    bb = comp.BoundBox
    comp.translate(V(xc - (bb.XMin + bb.XMax) / 2, yc - (bb.YMin + bb.YMax) / 2, Z_TOP - depth))
    comp.rotate(V(xc, yc, Z_TOP), V(0, 0, 1), 180)   # read from the connector side
    return shape.cut(comp.extrude(V(0, 0, depth + 1)))

for name, xl, xr, _ in CONNECTORS:
    cover = engrave(cover, name, (xl + xr) / 2, -6.0, 2.8)
cover = engrave(cover, 'KENWOOD PROXY', BW / 2, -BD + 8.0, 4.0)
cover = cover.removeSplitter()

# ---------------------------------------------------------------- checks
fails = []
for name, x0, x1, y0, y1, h in PARTS:
    env = box(x0, x1, -y1, -y0, Z_SPLIT, Z_SPLIT + h)
    for pname, part in (('cover', cover), ('base', base)):
        v = env.common(part).Volume
        if v > 1e-3:
            fails.append(f'{name} intersects {pname} ({v:.2f} mm3)')
# Each connector face must be fully open in the front wall.
for name, xl, xr, h in CONNECTORS:
    face = box(xl, xr, Y1 - 0.01, OY1 + 2, Z_SPLIT + 0.01, Z_SPLIT + min(h, JACK_H))
    for pname, part in (('cover', cover), ('base', base)):
        v = face.common(part).Volume
        if v > 1e-3:
            fails.append(f'{name} opening blocked by {pname} ({v:.2f} mm3)')
# Board must fit the cavity and rest on the standoffs.
board = box(0, BW, -BD, 0, Z_BOARD, Z_SPLIT)
for hx, hy in HOLES:
    board = board.cut(cyl(hx, -hy, 1.6, Z_BOARD - 1, Z_SPLIT + 1))
for pname, part in (('cover', cover), ('base', base)):
    v = board.common(part).Volume
    if v > 1e-3:
        fails.append(f'board intersects {pname} ({v:.2f} mm3)')
log('checks:', 'PASS' if not fails else 'FAIL')
for f in fails:
    log('  ', f)

# ---------------------------------------------------------------- export
def stl(shape, name):
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.25, Relative=False)
    if m.hasSelfIntersections():
        m.fixSelfIntersections()
    m.write(os.path.join(HERE, name))
    log(f'{name}: {m.CountFacets} facets, watertight={m.isSolid()}, '
        f'non-manifold={m.hasNonManifolds()}, self-intersecting={m.hasSelfIntersections()}')

stl(base, 'kp_case_base.stl')
cover_print = cover.copy()
cover_print.rotate(V(0, 0, Z_TOP / 2), V(1, 0, 0), 180)   # print top-down: flat top on the bed
stl(cover_print, 'kp_case_cover.stl')
Part.Compound([base, cover]).exportStep(os.path.join(HERE, 'kp_case.step'))

bb = base.fuse(cover).BoundBox
log(f'outer size: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm')
log(f'board top at Z={Z_SPLIT:.1f}, ceiling Z={Z_CEIL:.1f}')
log(f'screw: M3 x {SCREW_L:.0f} from below, head under the floor; thread engagement in cover post = {SCREW_L - Z_SPLIT:.1f} mm')

# ---------------------------------------------------------------- previews
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def render(items, fname, elev, azim, title, px=900):
    """Orthographic z-buffer render with simple shading (no GUI needed)."""
    e, a = np.radians(elev), np.radians(azim)
    # camera basis: view direction d points from the camera toward the scene
    d = -np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    r = np.cross(d, [0, 0, 1.0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    light = -d + 0.6 * u + 0.3 * r; light /= np.linalg.norm(light)
    tris_all, cols = [], []
    for shape, color in items:
        pts, tris = shape.tessellate(0.1)
        P = np.array([[p.x, p.y, p.z] for p in pts])
        T = P[np.array(tris)]
        tris_all.append(T); cols.append(np.tile(matplotlib.colors.to_rgb(color), (len(T), 1)))
    T = np.concatenate(tris_all); C = np.concatenate(cols)
    S = np.stack([T @ r, T @ u, T @ d], axis=-1)       # screen x, y, depth
    lo, hi = S[..., :2].reshape(-1, 2).min(0), S[..., :2].reshape(-1, 2).max(0)
    scale = (px - 40) / (hi - lo).max()
    W = int((hi[0] - lo[0]) * scale) + 40; H = int((hi[1] - lo[1]) * scale) + 40
    zbuf = np.full((H, W), np.inf); img = np.ones((H, W, 3))
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    shade = 0.35 + 0.65 * np.abs(n @ light)
    for k in range(len(S)):
        x = (S[k, :, 0] - lo[0]) * scale + 20; y = H - ((S[k, :, 1] - lo[1]) * scale + 20); z = S[k, :, 2]
        x0, x1 = int(max(np.floor(x.min()), 0)), int(min(np.ceil(x.max()), W - 1))
        y0, y1 = int(max(np.floor(y.min()), 0)), int(min(np.ceil(y.max()), H - 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-9: continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any(): continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = m & (zz < sub)
        sub[upd] = zz[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = C[k] * shade[k]
    fig = plt.figure(figsize=(W / 110, H / 110 + 0.4), dpi=110)
    plt.imshow(img); plt.axis('off'); plt.title(title, fontsize=10)
    fig.savefig(os.path.join(HERE, fname), bbox_inches='tight'); plt.close(fig)

parts_env = None
for name, x0, x1, y0, y1, h in PARTS:
    eb = box(x0, x1, -y1, -y0, Z_SPLIT, Z_SPLIT + h)
    parts_env = eb if parts_env is None else parts_env.fuse(eb)
render([(base, '#5b8def'), (board, '#2e8b57'), (parts_env, '#d9a441')],
       'preview_base_with_board.png', 40, 60, 'Base with board and tall-part envelopes (connector side at right-front)')
render([(base, '#5b8def'), (cover, '#c8c8c8'), (parts_env, '#d9a441')],
       'preview_assembled_front.png', 18, 75, 'Assembled: connector openings (BODY, HEAD, ILL)')
render([(cover, '#c8c8c8')], 'preview_cover_top.png', 60, 100, 'Cover top: engraved labels')
render([(base, '#5b8def')], 'preview_base_bottom.png', -50, 60, 'Base underside: screw holes')
open(os.path.join(HERE, 'build_report.txt'), 'w').write('\n'.join(_report) + '\n')
sys.exit(0 if not fails else 1)
