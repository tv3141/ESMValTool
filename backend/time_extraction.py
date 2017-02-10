# -*- coding: utf-8 -*-

import iris

def extract_time_period(cube, start_time, end_time):
    """Extract only the data between `start_time` and `end_time` from provided
    cube.

    It uses the time point of the data, or if available the beginning of a time
    period. This time point has to be at or after `start`, and before or at
    `end`.

    Args:
        * cube: Iris Cube.
        * start_time: datetime.datetime
        * end_time: datetime.datetime

    Returns:
        Cube containing only data between `start_time` and `end_time`.
    """
    if cube.coord('time').has_bounds():
        time_range_constraint = iris.Constraint(
            time=lambda cell: start_time <= cell.bound[0] and \
                              cell.bound[1] <= end_time)
    else:
        time_range_constraint = iris.Constraint(
            time=lambda cell: start_time <= cell.point <= end_time)

    with iris.FUTURE.context(cell_datetime_objects=True):
        return cube.extract(time_range_constraint)
