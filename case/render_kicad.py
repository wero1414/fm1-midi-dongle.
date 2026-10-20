#!/usr/bin/env python3
"""Photo-style renders of the case with KiCad's raytracer: the two case STEP files are mounted as 3D models on a
scratch copy of the board (case/out/render.kicad_pcb), then kicad-cli renders it.
Run: python3 case/render_kicad.py   ->  case/out/case_*.png"""
import pathlib, shutil, subprocess
import pcbnew
from pcbnew import VECTOR2I_MM as MM
if not hasattr(pcbnew.SwigPyIterator, 'next'):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
SRC = HERE.parent / 'fm1-midi-dongle.kicad_pcb'


def build(name, top_opacity=1.0, bottom=True, top=True):
    b = pcbnew.LoadBoard(str(SRC))
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference('CASE'); fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetPosition(MM(0, 0))
    for part, op, on in (('case_top', top_opacity, top), ('case_bottom', 1.0, bottom)):
        if not on:
            continue
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = str(OUT / f'{part}.wrl')           # fine mesh (KiCad tessellates the STEP's curves coarsely)
        m.m_Scale = pcbnew.VECTOR3D(1 / 2.54, 1 / 2.54, 1 / 2.54)   # KiCad reads VRML in 0.1 inch units
        m.m_Offset = pcbnew.VECTOR3D(0, 0, -0.8)          # case frame: board bottom at z 0; KiCad: board top
        m.m_Opacity = op
        fp.Models().push_back(m)
    b.Add(fp)
    path = SRC.parent / f'_case_{name}.kicad_pcb'      # next to the real board, so ${KIPRJMOD} models resolve
    b.Save(str(path))
    return path


def render(pcb, png, rotate, side='top', zoom=1.0, w=1600, h=1100):
    subprocess.run(['kicad-cli', 'pcb', 'render', '--quality', 'high', '--floor', '--perspective',
                    '--background', 'opaque', '--side', side, '--rotate', rotate, '--zoom', str(zoom),
                    '-w', str(w), '-h', str(h), '-o', str(OUT / png), str(pcb)], check=True, capture_output=True)
    print('wrote', png)


full = build('render_full')
ghost = build('render_ghost', top_opacity=0.25)
open_ = build('render_open', top=False)
render(full, 'case_jack_end.png', '-55,0,-25', zoom=0.75)
render(full, 'case_usb_end.png', '-55,0,155', zoom=0.75)
render(full, 'case_underside.png', '-125,0,30', zoom=0.75)
render(full, 'case_side.png', '-90,0,90', zoom=0.85)
render(ghost, 'case_ghost.png', '-50,0,-30', zoom=0.75)
render(open_, 'case_open.png', '-45,0,-30', zoom=0.75)
for f in SRC.parent.glob('_case_*'):
    f.unlink()
