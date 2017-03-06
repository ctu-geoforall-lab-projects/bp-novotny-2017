# TODO: header

import os
import sys
import subprocess
import shutil
import tempfile
import binascii

def findGRASS():
    ########### SOFTWARE
    if sys.platform == 'win32':
        grass7bin = r'C:\\OSGeo4W64\\bin\\grass72.bat'
    else:
        grass7bin = '/usr/bin/grass'
    startcmd = [grass7bin, '--config', 'path']

    p = subprocess.Popen(startcmd,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if p.returncode != 0:
        raise ErosionError("ERROR: Cannot find GRASS GIS 7 start script "
                           "({cmd}: {reason})".format(cmd=startcmd, reason=err))

    str_out = out.decode("utf-8")
    gisbase = str_out.rstrip(os.linesep)

    # Set GISBASE environment variable
    os.environ['GISBASE'] = gisbase
    # define GRASS-Python environment
    sys.path.append(os.path.join(gisbase, "etc", "python"))

    return grass7bin

grass7bin = findGRASS()
temp_dir = None
import grass.script as gscript
from grass.script import setup as gsetup
from grass.exceptions import ScriptError, CalledModuleError

from osgeo import ogr, gdal

class ErosionError(StandardError):
    pass

class ErosionBase:
    def __init__(self, epsg='5514'):
        ###########
        self.file_type = None
        self.grass_layer_types = {}

        gisdb = os.path.join(tempfile.gettempdir(), 'grassdata')
        if not os.path.isdir(gisdb):
            os.mkdir(gisdb)

        # location/mapset: use random names for batch jobs
        string_length = 16
        location = binascii.hexlify(os.urandom(string_length))
        mapset   = 'PERMANENT'
        location_path = os.path.join(gisdb, location)
        temp_dir = gisdb

        # Create new location
        # GRASS session must be initialized first
        gsetup.init(os.environ['GISBASE'], gisdb, location, mapset)
        try:
            gscript.create_location(gisdb, location, epsg, overwrite=True)
        except ScriptError as e:
            raise ErosionError('{}'.format(e))

        # Be quiet, print only error messages
        os.environ['GRASS_VERBOSE'] = '0'

    def __del__(self):
         #Remove all temp directory
         #shutil.rmtree(temp_dir)
         pass

    def import_files(self, files):
        for file_name in files:
            file_type = self._file_type_test(file_name)
            self.import_data(file_name, file_type)

    def import_data(self, file_name, file_type):
        map_name = os.path.splitext(os.path.basename(file_name))[0]
        if map_name in self.grass_layer_types:
            return # TODO: how to handler raster and vector map with the same name
        # import
        try:
            if file_type == 'raster':
                gscript.run_command('r.external', input=file_name, output=map_name)
            elif file_type == 'vector':
                gscript.run_command('v.in.ogr', input=file_name, output=map_name)
            elif file_type == 'table':
                gscript.run_command('db.in.ogr', input=file_name, output=map_name)
            else:
                raise ErosionError("Unknown file type")
        except CalledModuleError as e:
            raise ErosionError('{}'.format(e))

        self.grass_layer_types[map_name] = file_type

    def test(self):
        #messages
        print('Current GRASS GIS 7 environment:')
        print(gscript.gisenv())

        print('Available raster maps:')
        for rast in gscript.list_strings(type = 'rast'):
            print('{}{}'.format(' ' * 4, rast))

        print('Available vector maps:')
        for vect in gscript.list_strings(type = 'vect'):
            print('{}{}'.format(' ' * 4, vect))

    def export_data(self, grass_file, o_path, o_name):
        pass

    def _file_type_test(self, filename):
        # vector test
        src_ds = ogr.Open(filename)
        if src_ds is not None:
            if '.csv' in filename:
                return 'table'
            else:
                return 'vector'
        # raster test
        src_ds = gdal.Open(filename)
        if src_ds is not None:
            return 'raster'

        if src_ds is None:
            raise ErosionError("File '{}' not found".format(filename))

        raise ErosionError("Unknown file type")
