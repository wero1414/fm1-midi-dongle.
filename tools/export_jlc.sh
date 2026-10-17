#!/bin/sh
# JLCPCB BOM from the schematic (the CPL/placement file comes from the PCB once it exists).
set -e
cd "$(dirname "$0")/.."
mkdir -p production
kicad-cli sch export bom fm1-midi-dongle.kicad_sch -o production/bom_jlcpcb.csv \
  --fields "Value,Reference,Footprint,LCSC#" --labels "Comment,Designator,Footprint,LCSC Part #" \
  --group-by "Value,Footprint,LCSC#" --exclude-dnp
echo "wrote production/bom_jlcpcb.csv"
