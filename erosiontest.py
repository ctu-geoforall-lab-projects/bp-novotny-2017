#!/usr/bin/env python

import os
import sys
from pyerosion.erosionusle import ErosionUSLE

location = None
if len(sys.argv) > 1:
    location=sys.argv[1]

er = ErosionUSLE(location_path=location)
# http://training.gismentors.eu/geodata/qgis/
if location is None:
    home = os.path.expanduser("~")
    er.import_files([os.path.join(home, 'geodata', 'hydrologie', 'dmt.tif'),
                     os.path.join(home, 'geodata', 'hydrologie', 'vzorek1', 'hpj.shp'),
                     os.path.join(home, 'geodata', 'hydrologie', 'vzorek1', 'kpp.shp'),
                     os.path.join(home, 'geodata', 'hydrologie', 'vzorek1', 'landuse.shp')]
    )
er.run()
er.test()
