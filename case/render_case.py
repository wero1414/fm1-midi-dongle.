#!/usr/bin/env python3
"""Shaded renders of the case STLs (matplotlib, no GUI): assembled, exploded, side profile, each half.
Run: python3 case/render_case.py   ->  case/out/render_*.png"""
import pathlib, struct
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = pathlib.Path(__file__).resolve().parent / 'out'


def load(name):
    data = (HERE / name).read_bytes()
    if data[:5] == b'solid' and b'facet' in data[:300]:
        tris = []
        cur = []
        for line in data.decode().splitlines():
            t = line.split()
            if t and t[0] == 'vertex':
                cur.append([float(v) for v in t[1:4]])
                if len(cur) == 3:
                    tris.append(cur); cur = []
        return np.array(tris)
    n = struct.unpack('<I', data[80:84])[0]
    arr = np.frombuffer(data[84:84 + n * 50], dtype=np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')]))
    return arr['v'].reshape(-1, 3, 3).astype(float)


def shade(tris, base, light=(0.35, -0.55, 0.75)):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.array(light) / np.linalg.norm(light)
    k = 0.38 + 0.62 * np.clip(np.abs(n @ L), 0, 1)
    return np.clip(np.array(base)[None, :] * k[:, None], 0, 1)


def draw(ax, parts, elev, azim, title):
    for tris, color, alpha in parts:
        pc = Poly3DCollection(tris, facecolors=shade(tris, color), edgecolors='none', alpha=alpha)
        ax.add_collection3d(pc)
    allp = np.concatenate([p[0].reshape(-1, 3) for p in parts])
    lo, hi = allp.min(0), allp.max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_title(title, fontsize=11)


def shift(t, dz=0.0, dy=0.0):
    t = t.copy(); t[..., 2] += dz; t[..., 1] += dy
    return t


top, bot, board = load('case_top.stl'), load('case_bottom.stl'), load('board.stl')
SHELL_T, SHELL_B, PCB = (0.92, 0.92, 0.90), (0.80, 0.81, 0.83), (0.15, 0.45, 0.25)

views = [
    ('render_assembled.png', [(top, SHELL_T, 1), (bot, SHELL_B, 1)], [(28, -60, 'assembled, jack end'), (25, 120, 'assembled, USB-A end'), (-30, -130, 'from below')]),
    ('render_exploded.png', [(shift(top, 9), SHELL_T, 1), (board, PCB, 1), (shift(bot, -9), SHELL_B, 1)], [(18, -55, 'exploded'), (18, 125, 'exploded, other side'), (0, -90, 'side')]),
    ('render_halves.png', [(top, SHELL_T, 1)], [(-60, -60, 'top half, inside')]),
]
for fname, parts, cams in views:
    fig = plt.figure(figsize=(6 * len(cams), 6.5), dpi=130)
    for i, (el, az, title) in enumerate(cams):
        ax = fig.add_subplot(1, len(cams), i + 1, projection='3d')
        draw(ax, parts, el, az, title)
    fig.tight_layout(); fig.savefig(HERE / fname, facecolor='white'); plt.close(fig)
    print('wrote', fname)

fig = plt.figure(figsize=(12, 6.5), dpi=130)
ax = fig.add_subplot(1, 2, 1, projection='3d'); draw(ax, [(bot, SHELL_B, 1)], 60, -60, 'bottom half, inside')
ax = fig.add_subplot(1, 2, 2, projection='3d'); draw(ax, [(bot, SHELL_B, 1), (board, PCB, 1)], 60, -60, 'bottom half + board')
fig.tight_layout(); fig.savefig(HERE / 'render_bottom.png', facecolor='white'); plt.close(fig)
print('wrote render_bottom.png')
