import iris
import pytest
from datetime import datetime as dt
from iris.tests.stock import realistic_3d, lat_lon_cube

from conf_imports import backend
from backend.time_extraction import extract_time_period


@pytest.fixture
def cube():
    """DimCoord([2014-12-21 00:00:00, 2014-12-21 06:00:00, 2014-12-21 12:00:00,
       2014-12-21 18:00:00, 2014-12-22 00:00:00, 2014-12-22 06:00:00,
       2014-12-22 12:00:00], standard_name='time', calendar='gregorian')
    """
    return realistic_3d()


@pytest.fixture
def cube_bounded():
    """DimCoord([2014-12-21 00:00:00, 2014-12-21 06:00:00, 2014-12-21 12:00:00,
       2014-12-21 18:00:00, 2014-12-22 00:00:00, 2014-12-22 06:00:00,
       2014-12-22 12:00:00], bounds=[[2014-12-20 21:00:00, 2014-12-21 03:00:00],
       [2014-12-21 03:00:00, 2014-12-21 09:00:00],
       [2014-12-21 09:00:00, 2014-12-21 15:00:00],
       [2014-12-21 15:00:00, 2014-12-21 21:00:00],
       [2014-12-21 21:00:00, 2014-12-22 03:00:00],
       [2014-12-22 03:00:00, 2014-12-22 09:00:00],
       [2014-12-22 09:00:00, 2014-12-22 15:00:00]], standard_name='time', calendar='gregorian')
    """
    cube = realistic_3d()
    cube.coord('time').guess_bounds()
    return cube


@pytest.fixture
def cube_wo_time():
    return lat_lon_cube()


class TestTimeExtraction():

    def test_include_start_and_end_time_points(self, cube):
        start = dt(2014, 12, 21, 12, 0, 0)
        end   = dt(2014, 12, 22,  6, 0, 0)
        res = extract_time_period(cube, start, end)
        assert len(res.coord('time').points) == 4


    def test_only_full_bounded_periods(self, cube_bounded):
        start = dt(2014, 12, 21, 12, 0, 0)
        end   = dt(2014, 12, 22,  6, 0, 0)
        res = extract_time_period(cube_bounded, start, end)
        assert len(res.coord('time').points) == 2


    def test_outside_range(self, cube):
        start = dt(1800, 1, 1)
        end   = dt(1900, 1, 1)
        res = extract_time_period(cube, start, end)
        assert res == None


    def test_end_before_start(self, cube):
        end   = dt(2014, 12, 21, 12, 0, 0)
        start = dt(2014, 12, 22,  6, 0, 0)
        res = extract_time_period(cube, start, end)
        assert res == None


    def test_no_time_coord(self, cube_wo_time):
        start = dt(2000, 1, 1, 12, 0, 0)
        end   = dt(2100, 1, 1, 12, 0, 0)
        with pytest.raises(iris.exceptions.CoordinateNotFoundError):
            res = extract_time_period(cube_wo_time, start, end)

