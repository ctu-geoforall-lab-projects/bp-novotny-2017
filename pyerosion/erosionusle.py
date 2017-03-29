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

        # internal input map names
        self._input = { 'dmt' : 'dmt',
                        'hpj' : 'hpj',
                        'kpp' : 'kpp',
                        'landuse' : 'landuse'
        }
        # internal input tables names
        self._table = { 'hpj_k' : 'hpj_k',
                        'kpp_k' : 'kpp_k',
                        'lu_c' : 'lu_c'
        }
        # output names
        self._output = { 'erosion' : 'g',
        }

    def run(self, terraflow=False):
        """
        Erosion computing
        :param terraflow: True : computing direction by method terraflow
                                    False : computing direction by method wattershed
        """
        # set computation region based on input DMT
        print("Setting up computation region")
        run_command('g.region',
                    raster=self._input['dmt'], res=50
        )
        # computing slope on input DMT
        print("Computing slope")
        slope = self._temp_map('raster')
        run_command('r.slope.aspect',
                    elevation=self._input['dmt'],
                    slope=slope
        )
        # setting up mask
        print("Setting up mask")
        run_command('r.mask',
                    raster=self._input['dmt']
        )
        # computing accumulation
        # TODO: discuss accumulation computation (which module, use
        # filled DMT?)
        print("Computing accumulation")
        accu = self._temp_map('raster')
        if terraflow:
            dmt_fill = self._temp_map('raster')
            direction = self._temp_map('raster')
            swatershed = self._temp_map('raster')
            tci = self._temp_map('raster')
            run_command('r.terraflow',
                        elevation=self._input['dmt'],
                        filled=dmt_fill,
                        direction=direction,
                        swatershed=swatershed,
                        accumulation=accu,
                        tci=tci
            )
        else:
            run_command('r.watershed',
                        elevation=self._input['dmt'],
                        accumulation=accu
            )
        #  computing LS Factor
        print("Computing LS factor")
        formula='ls = 1.6 * pow(' + accu + '* (10.0 / 22.13), 0.6) * pow(sin(' + \
        slope + '* (3.1415926/180)) / 0.09, 1.3)'
        run_command('r.mapcalc',
                    expr=formula
        )
        # computing KC Factor
        print("Computing KC factor")
        # overlay layers: hpj, kpp and landuse
        hpj_kpp = self._temp_map('vector')
        run_command('v.overlay',
                    ainput=self._input['hpj'],
                    binput=self._input['kpp'],
                    operator='or',
                    output=hpj_kpp
        )
        hpj_kpp_land = self._temp_map('vector')
        run_command('v.overlay',
                    ainput=hpj_kpp,
                    binput=self._input['landuse'],
                    operator='and',
                    output= hpj_kpp_land
        )
        # add columns K and C to layer hpj_kpp_land
        run_command('v.db.addcolumn',
                    map=hpj_kpp_land,
                    columns='K double, C double')
        run_command('v.db.join',
                    map=hpj_kpp_land,
                    column='a_a_HPJ',
                    other_table=self._table['hpj_k'],
                    other_column='HPJ')
        run_command('db.execute',
                    sql='UPDATE ' + hpj_kpp_land + ' SET K = (SELECT b.K FROM ' + hpj_kpp_land +' AS a JOIN '+ self._table['kpp_k'] +' as b ON a.a_b_KPP = b.KPP) WHERE K IS NULL'
        )
        run_command('v.db.join',
                    map=hpj_kpp_land,
                    column='b_LandUse',
                    other_table=self._table['lu_c'],
                    other_column='LU'
        )
        # add column KC
        run_command('v.db.addcolumn',
                    map=hpj_kpp_land,
                    columns='KC double'
        )
        # compute KC value
        run_command('v.db.update',
                    map=hpj_kpp_land,
                    column='KC',
                    query_column='K * C')
        # compute final G Factor (Erosion factor)
        print("Computing Erosion factor")
        hpj_kpp_land_raster=self._temp_map('raster')
        run_command('v.to.rast',
                    input=hpj_kpp_land,
                    output=hpj_kpp_land_raster,
                    use='attr',
                    attribute_column='KC'
        )
        formula1=self._output['erosion'] + ' = 40 * ls*' + hpj_kpp_land_raster + ' * 1'
        run_command('r.mapcalc',
                    expr=formula1
        )
        
    def test(self):
        """
        Run test.

        - prints output erosion map metadata
        """
        run_command('r.info', map=self._output['erosion'])
