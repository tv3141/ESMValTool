import numpy as np
import iris
import iris.exceptions
import os
import json
import warnings

iris.FUTURE.cell_datetime_objects = True
iris.FUTURE.netcdf_promote = True


class CMORCheck(object):

    def __init__(self, cube, table, fail_on_error=False):
        self.cube = cube
        self._failerr = fail_on_error
        self._errors = list()
        cwd = os.path.dirname(os.path.realpath(__file__))
        self._cmor_tables_folder = os.path.join(cwd, 'cmip6-cmor-tables', 'Tables')
        self._cmor_tables_file = 'CMIP6_{}.json'.format(table)
        self._load_variable_information()
        self._load_coord_information()

    def _load_coord_information(self):
        table_file = os.path.join(self._cmor_tables_folder,
                                  'CMIP6_coordinate.json')
        with open(table_file) as inf:
            json_data = inf.read()
        self.coord_json_data = json.loads(json_data)
        self.coord_json_data = self.coord_json_data['axis_entry']
        # Don't look here!
        # Entry in table is 'days since ?', this matches test CMIP6 data
        self.coord_json_data['time']['units'] = u'days since 1850-1-1 00:00:00'

    def _load_variable_information(self):
        table_file = os.path.join(self._cmor_tables_folder,
                                  self._cmor_tables_file)
        with open(table_file) as inf:
            json_data = inf.read()
        self.var_json_data = json.loads(json_data)
        self.var_json_data = self.var_json_data['variable_entry']
        self.var_json_data = self.var_json_data[self.cube.var_name]

    def check(self):
        self._check_rank()
        self._check_dim_names()
        self._check_coords()
        self._check_time_coord()
        self._check_var_metadata()
        self._check_fill_value()
        self._check_data_range()

        if self.has_errors():
            msg = 'There were errors in variable {0}:\n {1}'
            msg = msg.format(self.cube.standard_name, '\n '.join(self._errors))
            raise CMORCheckError(msg)

    def _check_fill_value(self):
        pass

    def _check_var_metadata(self):
        # Set generic error message
        msg = '{} for {} is {}, not {}'
        # Check standard_name
        if self.var_json_data['standard_name']:
            if self.cube.standard_name != self.var_json_data['standard_name']:
                self.report_error(msg, 'standard_name',
                                  self.cube.var_name,
                                  self.cube.standard_name,
                                  self.var_json_data['standard_name'])

        # Check units
        if self.var_json_data['units']:
            if str(self.cube.units) != self.var_json_data['units']:
                self.report_error(msg, 'units',
                                  self.cube.var_name,
                                  self.cube.units,
                                  self.var_json_data['units'])

        # Check other variable attributes that match entries in cube.attributes
        attrs = ['positive']
        for attr in attrs:
            if self.var_json_data[attr]:
                if self.cube.attributes[attr] != self.var_json_data[attr]:
                    self.report_error(msg, attr,
                                      self.cube.var_name,
                                      self.cube.attributes[attr],
                                      self.var_json_data[attr])

    def _check_data_range(self):
        # Set generic error message
        msg = 'Variable {} has values {} ({})'
        # Check data is not less than valid_min
        if self.var_json_data['valid_min']:
            valid_min = float(self.var_json_data['valid_min'])
            if np.any(self.cube.data < valid_min):
                self.report_error(msg, '< valid_min',
                                  self.cube.name(), valid_min)
        # Check data is not greater than valid_max
        if self.var_json_data['valid_max']:
            valid_max = float(self.var_json_data['valid_max'])
            if np.any(self.cube.data > valid_max):
                self.report_error(msg, '> valid_max',
                                  self.cube.name(), valid_max)

    def _check_rank(self):
        # Need to check here that dimensions required not scalar coordinates
        # i.e. rank = #dims - #scalars
        if self.var_json_data['dimensions']:
            # Check number of dim_coords matches rank required
            var_names = self.var_json_data['dimensions'].split()
            # Check for scalar dimensions
            num_scalar_dims = 0
            for var_name in var_names:
                if self.coord_json_data[var_name]['value']:
                    num_scalar_dims += 1
            # Calculate actual rank of data
            rank = len(var_names) - num_scalar_dims
            # Extract dimension coordinates from cube
            dim_coords = self.cube.coords(dim_coords=True)
            # Check number of dimension coords matches rank
            if len(dim_coords) != rank:
                self.report_error('Coordinate rank does not match')

    def _check_dim_names(self):
        if self.var_json_data['dimensions']:
            # Get names of dimension variables from variable CMOR table
            var_names = self.var_json_data['dimensions'].split()
            for var_name in var_names:
                # Get CMOR metadata for coordinate
                cmor = self.coord_json_data[var_name]
                # Check for variable name in coordinate CMOR table,
                #  get out_name as that is coordinate variable name
                #  in variable file.
                out_var_name = cmor['out_name']
                # Check for out_var_name in variable coordinates
                if self.cube.coords(var_name=out_var_name):
                    coord = self.cube.coord(var_name=out_var_name)
                    if coord.standard_name != cmor['standard_name']:
                        self.report_error('standard_name for {} is {}, not {}',
                                          var_name,
                                          coord.standard_name,
                                          cmor['standard_name'])
                else:
                    self.report_error('Coordinate {} does not exist', var_name)

    def _check_coords(self):
        if self.var_json_data['dimensions']:
            # Get names of dimension variables from variable CMOR table
            var_names = self.var_json_data['dimensions'].split()
            for var_name in var_names:
                # Get CMOR metadata for coordinate
                cmor = self.coord_json_data[var_name]
                # Check for variable name in coordinate CMOR table,
                #  get out_name as that is coordinate variable name
                #  in variable file.
                out_var_name = cmor['out_name']
                # Get coordinate out_var_name as it exists!
                try:
                    coord = self.cube.coord(var_name=out_var_name,
                                            dim_coords=True)
                except iris.exceptions.CoordinateNotFoundError:
                    continue

                self._check_coord(cmor, coord, var_name)

    def _check_coord(self, cmor, coord, var_name):
        # Check units
        if cmor['units']:
            if str(coord.units) != cmor['units']:
                self.report_error('units for {} is {}, not {}',
                                  var_name, coord.units, cmor['units'])
        self._check_coord_monotonicity_and_direction(cmor, coord, var_name)
        self._check_coord_values(cmor, coord, var_name)

    def _check_coord_monotonicity_and_direction(self, cmor, coord, var_name):
        if not coord.is_monotonic():
            self.report_error('Coord {} is not monotonic', var_name)
        if cmor['stored_direction']:
            if cmor['stored_direction'] == 'increasing':
                if coord.points[0] > coord.points[1]:
                    msg = 'Coord {} is not increasing'
                    self.report_error(msg, var_name)
            elif cmor['stored_direction'] == 'decreasing':
                if coord.points[0] < coord.points[1]:
                    msg = 'Coord {} is not decreasing'
                    self.report_error(msg, var_name)

    def _check_coord_values(self, cmor, coord, var_name):
        # Check requested coordinate values exist in coord.points
        if cmor['requested']:
            cmor_points = [float(val) for val in cmor['requested']]
            coord_points = list(coord.points)
            for point in cmor_points:
                if point not in coord_points:
                    msg = 'Coord {} does not contain {} {}'
                    self.report_error(msg, var_name, str(point),
                                      str(coord.units))

        # Check coordinate value ranges
        if cmor['valid_min']:
            valid_min = float(cmor['valid_min'])
            if np.any(coord.points < valid_min):
                msg = 'Coord {} has values < valid_min ({})'
                self.report_error(msg, var_name, valid_min)
        if cmor['valid_max']:
            valid_max = float(cmor['valid_max'])
            if np.any(coord.points > valid_max):
                msg = 'Coord {} has values > valid_max ({})'
                self.report_error(msg, var_name, valid_max)

    def _check_time_coord(self):
        try:
            coord = self.cube.coord('time', dim_coords=True)
        except iris.exceptions.CoordinateNotFoundError:
            return

        if not coord.units.is_time_reference():
            self.report_error('Coord time does not have time reference units')

    def has_errors(self):
        return len(self._errors) > 0

    def report_error(self, message, *args):
        msg = message.format(*args)
        if self._failerr:
            raise CMORCheckError(msg)
        else:
            self._errors.append(msg)


class CMORCheckError(Exception):
    pass


def main():
    data_folder = '/Users/nube/esmval_data'
    # data_folder = '/home/paul/ESMValTool/data'
    example_datas = [
        ('ETHZ_CMIP5/historical/Amon/ta/CMCC-CESM/r1i1p1', 'Amon'),
        # ('CMIP6/1pctCO2/Amon/ua/MPI-ESM-LR/r1i1p1f1', 'Amon'),
        # ('CMIP6/1pctCO2/Amon/tas/MPI-ESM-LR/r1i1p1f1', 'Amon'),
        # ('CMIP6/1pctCO2/day/tas/MPI-ESM-LR/r1i1p1f1', 'day'),
        # ('CMIP6/1pctCO2/day/pr/MPI-ESM-LR/r1i1p1f1', 'day'),
        # # ('CMIP6/1pctCO2/cfDay/hur/MPI-ESM-LR/r1i1p1f1', 'CFday'),
        # ('CMIP6/1pctCO2/LImon/snw/MPI-ESM-LR/r1i1p1f1', 'LImon'),
        # ('CMIP6/1pctCO2/Lmon/cropFrac/MPI-ESM-LR/r1i1p1f1', 'Lmon'),
        # # ('CMIP6/1pctCO2/Oyr/co3/MPI-ESM-LR/r1i1p1f1', 'Oyr'),
        ]

    # Use this callback to fix anything Iris tries to break!
    # noinspection PyUnusedLocal
    def merge_protect_callback(raw_cube, field, filename):
        # Remove attributes that cause issues with merging and concatenation
        for attr in ['creation_date', 'tracking_id', 'history']:
            if attr in raw_cube.attributes:
                del raw_cube.attributes[attr]
        # Iris chooses to change longitude and latitude units to degrees
        #  regardless of value in file
        if raw_cube.coords('longitude'):
            raw_cube.coord('longitude').units = 'degrees_east'
        if raw_cube.coords('latitude'):
            raw_cube.coord('latitude').units = 'degrees_north'

    for (example_data, table) in example_datas:
        print('\n' + example_data)

        try:
            # Load cubes
            files = os.path.join(data_folder, example_data, '*.nc')
            # Suppress warnings associated with missing 'areacella' measure
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore',
                                        'Missing CF-netCDF measure variable',
                                        UserWarning)
                cubes = iris.load(files, callback=merge_protect_callback)
            # Concatenate data to single cube
            cube = cubes.concatenate_cube()
            # Create checker for loaded cube
            checker = CMORCheck(cube, table)  # , fail_on_error=True)
            # Run checks
            checker.check()

        except (iris.exceptions.ConstraintMismatchError, iris.exceptions.ConcatenateError, CMORCheckError) as ex:
            print(ex)

if __name__ == '__main__':
    main()
