#!/usr/bin/env freecadcmd
"""Fine VRML meshes of the case halves for the KiCad renders (case/render_kicad.py). CASE=alu (default) or print:
anodised space grey with a metal highlight, or a light grey print."""
import os, pathlib
import Part, MeshPart
OUT = pathlib.Path('/home/wero1414/mwave-experiments/hardware/fm1-midi-dongle/case/out')
MODE = os.environ.get('CASE', 'alu')
MAT = {'alu': 'diffuseColor 0.30 0.31 0.33\n          specularColor 0.55 0.55 0.58\n          shininess 0.45',
       'print': 'diffuseColor 0.80 0.80 0.80',
       'sheet': 'diffuseColor 0.72 0.73 0.75\n          specularColor 0.70 0.70 0.72\n          shininess 0.55'}[MODE]
for half in ('top', 'bottom'):
    n = f'{MODE}_{half}'
    s = Part.read(str(OUT / f'{n}.step'))
    m = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.004, AngularDeflection=0.04, Relative=False)
    m.write(str(OUT / f'{n}.wrl'))
    p = OUT / f'{n}.wrl'
    p.write_text(p.read_text().replace('diffuseColor 0.8 0.8 0.8', MAT, 1))
    print(n, m.CountFacets)
