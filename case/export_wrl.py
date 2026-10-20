#!/usr/bin/env freecadcmd
"""Fine VRML meshes of the case halves for the KiCad renders (case/render_kicad.py)."""
import Part, Mesh, MeshPart
for n in ('case_top', 'case_bottom'):
    s = Part.read(f'/home/wero1414/mwave-experiments/hardware/fm1-midi-dongle/case/out/{n}.step')
    m = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.004, AngularDeflection=0.04, Relative=False)
    m.write(f'/home/wero1414/mwave-experiments/hardware/fm1-midi-dongle/case/out/{n}.wrl')
    print(n, m.CountFacets)
