import os
import time
from erosionbase import ErosionBase

from grass.script.core import run_command

class ErosionUSLE(ErosionBase):
    def __init__(self, epsg='5514', location_path=None):
        """USLE constructor.

        Two modes are available
         - creating temporal location, input data are imported

         - use existing location, in this case specified location must
           contain maps defined by self.maps directory

        :param epgs: EPSG code for creating new temporal location
        :param location_path: path to existing location
        """
        ErosionBase.__init__(self, epsg, location_path)

        # overwrite existing maps/files by default
        os.environ['GRASS_OVERWRITE']='1'

        # internal map names
        self._input = { 'dmt' : 'dmt',
                        'hpj' : 'hpj',
                        'kpp' : 'kpp',
                        'landuse' : 'landuse',
        }
        self._tables = { 'hpj_k' : 'hpj_k',
                         'kpp_k' : 'kpp_k',
                         'lu_c' : 'lu_c'
        }
        self.output = { 'erosion' : 'g',
        }

        self._temp_maps = []

        self._map_counter = 0
        self._pid = os.getpid()
        
    def __del__(self):
        if self.temporal_location:
            return

        for map_name, map_type in self._temp_maps:
            run_command('g.remove', map_type=map_type, name=map_name)

    def _temp_map(self, map_type):
        map_name = 'map_{}_{}'.format(self._map_counter, self._pid)
        self._temp_maps.append((map_name, map_type))
        self._mapcounter += 1
        
        return map_type
    
    def run(self, terraflow=False):

        # set computation region based on input DMT
        print("Setting up computation region")
        run_command('g.region',
                    raster=self._maps['dmt']
        )
        
        print("Computing slope")
        slope = self._temp_map('raster')
        run_command('r.slope.aspect',
                    elevation=self._maps['dmt'],
                    slope=slope)
        )
        print("Setting up mask")
        run_command('r.mask',
                    raster=self._maps['dmt']
        )

        # TODO: discuss accumulation computation (which module, use
        # filled DMT?)
        print("Computing accumulation")
        accu = self._temp_map('raster')
        if terraflow:
            dmt_fill = self._temp_map('raster')
            direction = self._temp_map('raster')
            run_command('r.terraflow',
                        elevation=self._maps['dmt'],
                        filled=dmt_fill,
                        direction=self._maps['dir'],
                        swatershed=self._maps['sink'],
                        accumulation=accu,
                        tci=self._maps['tci']
            )
        else:
            run_command('r.watershed',
                        elevation=self._maps['dmt'],
                        accumulation=accu
            )
        #  LS Factor
        formula='ls = 1.6 * pow(' + self._maps['accu'] + '* (10.0 / 22.13), 0.6) * pow(sin(' + \
        slope + '* (3.1415926/180)) / 0.09, 1.3)'
        run_command('r.mapcalc',
                    expr=formula
        )
        #        KC Factor
        hpj_kpp = self._temp_map('vector')
        run_command('v.overlay',
                    ainput=self._maps['hpj'],
                    binput=self._maps['kpp'],
                    operator='or',
                    output=hpj_kpp)
        run_command('v.overlay',
                    ainput=hpj_kpp,
                    binput=self._maps['landuse'],
                    operator='and',
                    output=self._maps['hpj_kpp_land']
        )
        run_command('v.db.addcolumn',
                    map=self._maps['hpj_kpp_land'],
                    columns='K double, C double')
        run_command('v.db.join',
                    map=self._maps['hpj_kpp_land'],
                    column='a_a_HPJ',
                    other_table=self._tables['hpj_k'],
                    other_column='HPJ')
        run_command('db.execute',
                    sql='UPDATE hpj_kpp_land SET K = (SELECT b.K FROM hpj_kpp_land AS a JOIN kpp_k3 as b ON a.a_b_KPP = b.KPP) WHERE K IS NULL'
        )
        run_command('v.db.join',
                    map=self._maps['hpj_kpp_land'],
                    column='b_LandUse',
                    other_table='lu_c1',
                    other_column='LU'
        )
        run_command('v.db.addcolumn',
                    map=self._maps['hpj_kpp_land'],
                    columns='KC double'
        )
        run_command('v.db.update',
                    map=self._maps['hpj_kpp_land'],
                    column='KC',
                    query_column='K * C')
#        Final G Factor
        run_command('v.to.rast',
                    input=self._maps['hpj_kpp_land'],
                    output=self._maps['hpj_kpp_land_rastr'],
                    use='attr',
                    attribute_column='KC'
        )
        formula1=self._maps['erosion'] + ' = 40 * ls*' + self._maps['hpj_kpp_land_rastr'] + ' * 1'
        run_command('r.mapcalc',
                    expr=formula1
        )
        
    def test(self):
        """
        Run test.

        - prints output erosion map metadata
        """
        run_command('r.info', map=self._outputs['erosion'])
