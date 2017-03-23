import os
import time
from erosionbase import ErosionBase

from grass.script.core import run_command

class ErosionUSLE(ErosionBase):
    def __init__(self, epsg='5514', location_path=None):
        ErosionBase.__init__(self, epsg, location_path)
        os.environ['GRASS_OVERWRITE']='1'
        self._maps = { 'dmt' : 'dmt',
                                'slope' : 'svah' ,
                                'dmt_fill' : 'dmt_fill',
                                'dir' : 'dir',
                                'sink' : 'sink',
                                'accu' : 'accu',
                                'tci' : 'tci',
                                'hpj' : 'hpj',
                                'kpp' : 'kpp',
                                'hpj_kpp' : 'hpj_kpp'}
        
    def run(self):
        run_command('g.region', raster=self._maps['dmt'])
        run_command('r.slope.aspect', elevation=self._maps['dmt'], slope=self._maps['slope'])
        run_command('r.mask', raster=self._maps['dmt'])
        run_command('r.terraflow', elevation=self._maps['dmt'], filled=self._maps['dmt_fill'], direction=self._maps['dir'], swatershed=self._maps['sink'], accumulation=self._maps['accu'], tci=self._maps['tci'])
#        LS Factor
        formula='ls = 1.6 * pow(' + self._maps['accu'] + '* (10.0 / 22.13), 0.6) * pow(sin(' + self._maps['slope'] + '* (3.1415926/180)) / 0.09, 1.3)'
        run_command('r.mapcalc', expr=formula)
#        KC Factor
        run_command('v.overlay', ainput=self._maps['hpj'], binput=self._maps['kpp'], operator='or', output=self._maps['hpj_kpp'])

    def test(self):
        run_command('g.region', flags='p')
        run_command('r.info', map=self._maps['slope'])
        time.sleep(10)