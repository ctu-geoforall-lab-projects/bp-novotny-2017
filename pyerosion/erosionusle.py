import os
import time
from erosionbase import ErosionBase

from grass.script.core import run_command

class ErosionUSLE(ErosionBase):
    def __init__(self, epsg='5514', location_path=None):
        ErosionBase.__init__(self, epsg, location_path)
        os.environ['GRASS_OVERWRITE']='1'
        self._maps = { 'dmt' : 'dmt',
                       'slope' : 'svah' }
        
    def run(self):
        run_command('g.region', raster=self._maps['dmt'])
        run_command('r.slope.aspect', elevation=self._maps['dmt'], slope=self._maps['slope'])

    def test(self):
        run_command('g.region', flags='p')
        run_command('r.info', map=self._maps['slope'])
        time.sleep(10)