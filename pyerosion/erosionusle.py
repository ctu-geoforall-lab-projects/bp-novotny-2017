import os

from erosionbase import ErosionBase
from grass.script.core import run_command, parse_command

class ErosionUSLE(ErosionBase):

    def __init__(self, dmt, bpej, lpis, epsg='5514', location_path=None,
                 computeProgress=None, computeStat=None):
        """USLE constructor.

        Two modes are available
         - creating temporal location, input data are imported

         - use existing location, in this case specified location must
           contain maps defined by self.maps directory

        :param epgs: EPSG code for creating new temporal location
        :param location_path: path to existing location
        """

        ErosionBase.__init__(self, epsg, location_path)

        self._computeProgress = computeProgress
        self._computeStat = computeStat
        
        # overwrite existing maps/files by default
        os.environ['GRASS_OVERWRITE']='1'

        # internal input map names
        self._input = { 'euc' : 'euc',
                        'dmt' : dmt,
                        'bpej' : bpej,
                        'lpis' : lpis
        }
        # output names
        self._output = { 'erosion' : 'usle_g',
        }

    def computeProgress(self, perc, label):
        if self._computeStat is not None:
            self._computeStat.emit(perc, lable)
        
    def run(self, terraflow=False):
        """
        Erosion computing
        :param terraflow: True : computing direction by method terraflow
                                    False : computing direction by method wattershed
        """
        self.computeProgress.emit()
        # set computation region based on input DMT
        print("Setting up computation region")
        self.computeProgress(5, u'Setting up computation region...')
        reg = parse_command('g.region',
                            raster=self._input['dmt'],
                            flags='g'
        )
        # computing slope on input DMT
        print("Computing slope")
        self.computeStat.emit(10, u'Computing slope...')
        slope = self._temp_map('raster')
        run_command('r.slope.aspect',
                    elevation=self._input['dmt'],
                    slope=slope
        )
        # setting up mask
        print("Setting up mask")
        self.computeStat.emit(15, u'Setting up mask...')
        run_command('r.mask',
                    raster=self._input['dmt']
        )
        # computing accumulation
        # TODO: discuss accumulation computation (which module, use
        # filled DMT?)
        print("Computing accumulation")
        self.computeStat.emit(20, u'Computing accumulation...')
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
                        flags='a',
                        elevation=self._input['dmt'],
                        accumulation=accu
            )
        #  computing LS Factor
        print("Computing LS factor")
        self.computeStat.emit(30, u'Computing LS factor...')
        formula='ls = 1.6 * pow(' + accu + '* (' + reg['nsres'] +' / 22.13), 0.6) * pow(sin(' + \
        slope + '* (3.1415926/180)) / 0.09, 1.3)'
        run_command('r.mapcalc',
                    expr=formula
        )
        # computing KC Factor
        print("Computing KC factor")
        self.computeStat.emit(50, u'Computing KC factor...')
        # overlay layers: bpej and lpis
        bpej_lpis = self._temp_map('vector')
        run_command('v.overlay',
                    ainput=self._input['bpej'],
                    binput=self._input['lpis'],
                    operator='or',
                    output=bpej_lpis
        )
        # add column KC
        run_command('v.db.addcolumn',
                    map=bpej_lpis,
                    columns='KC double'
        )
        # compute KC value
        run_command('v.db.update',
                    map=bpej_lpis,
                    column='KC',
                    query_column='a_K * b_C')
        # compute final G Factor (Erosion factor)
        print("Computing Erosion factor")
        self.computeStat.emit(85, u'Computing Erosion factor...')
        bpej_lpis_raster=self._temp_map('raster')
        run_command('v.to.rast',
                    input=bpej_lpis,
                    output=bpej_lpis_raster,
                    use='attr',
                    attribute_column='KC',
                    where='KC IS NOT NULL'
        )
        usle=self._output['erosion'] + ' = 40 * ls *' + bpej_lpis_raster + ' * 1'
        run_command('r.mapcalc',
                    expr=usle
        )
        run_command('r.colors',
                    flags='ne',
                    map=self._output['erosion'],
                    color='corine'
        )
        print ("Computation finished")
        self.computeStat.emit(100, u'Computation finished.')
        
    def test(self):
        """
        Run test.

        - prints output erosion map metadata
        """
        run_command('g.gisenv')
        run_command('r.univar', map=self._output['erosion'])
