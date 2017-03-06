#!/usr/bin/env python

import os
from pyerosion.erosionbase import ErosionBase

er = ErosionBase()
# http://training.gismentors.eu/geodata/qgis/
home = os.path.expanduser("~")
er.import_files([os.path.join(home, 'geodata', 'shp', 'dibavod', 'povodi_i.shp'),
                 os.path.join(home, 'geodata', 'shp', 'dibavod', 'povodi_ii.shp')]
)
er.test()
