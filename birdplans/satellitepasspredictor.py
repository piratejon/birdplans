#!/usr/bin/env python3

'''
satellitepasspredictor.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

predict upcoming satellite passes at a given location
'''

import math

from collections import namedtuple

import maidenhead as mh
import numpy as np

from skyfield.api import Topos
from scipy import optimize

Pass = namedtuple('Pass', ['AOS', 'TCA', 'LOS'])
WindowPasses = namedtuple('WindowPasses', ['diff', 'passes'])

def estimate_window_passes(timescale, satellite, location, window_start, window_end, minimum_altitude):
    '''
    Implement the satellite pass prediction approach from
    <https://github.com/skyfielders/astronomy-notebooks/blob/master/Solvers/Earth-Satellite-Passes.ipynb>
    as accessed 2018-11-19

    :param satellite: a Skyfield Satellite object representing the satellite we want to track
    :param location: a Skyfield Topos object representing our Earth-based reference point
    :param window_start: Skyfield Time object representing search window start
    :param window_end: Skyfield Time object representing search window end
    '''

    # pylint: disable=too-many-locals
    # Complex scientific algorithm more clearly expressed with many locals.

    diff = satellite - location
    window_duration = window_end - window_start

    print('window_start', window_start)
    print('window_end', window_end)
    print('window_duration', window_duration)

    orbit_period_per_day = ((2.0 * np.pi) / satellite.model.no) / 24.0 / 60.0
    window_revolutions = window_duration / orbit_period_per_day
    sample_points = int(math.ceil(window_revolutions * 6.0))
    print('sample_points', sample_points)
    sample_step = window_duration / sample_points
    print('sample_step', sample_step)

    sample_time_range = timescale.tai_jd([
        window_start.tai + (_ * sample_step)
        for _ in range(sample_points)
    ])
    print('sample_time_range', sample_time_range)

    alt_f = lambda t: diff.at(t).altaz()[0].degrees

    sample_altitudes = alt_f(sample_time_range)
    print(sample_altitudes)

    left_diff = np.ediff1d(sample_altitudes, to_begin=0.0)
    right_diff = np.ediff1d(sample_altitudes, to_end=0.0)
    maxima = (left_diff > 0.0) & (right_diff < 0.0)

    print(sample_time_range[maxima])

    minus_alt_f_wrapper = lambda t: -alt_f(timescale.tai_jd(t))
    find_peaks = lambda t: optimize.minimize_scalar(
        minus_alt_f_wrapper
        , bracket=[t.tai + sample_step, t.tai - sample_step]
        , tol=(1.0 / 24.0 / 60.0 / 60.0) / t.tai
    ).x

    np.random.seed(99999)
    t_peaks = timescale.tai_jd([
        find_peaks(ti) for ti in sample_time_range[maxima]
    ])

    print(sample_step)
    print(t_peaks)

    rising_setting_wrapper = lambda t: -minus_alt_f_wrapper(t)
    find_rising = lambda t: optimize.brentq(
        rising_setting_wrapper, t.tai - (2.0 * sample_step), t.tai
    )
    find_setting = lambda t: optimize.brentq(
        rising_setting_wrapper, t.tai + (2.0 * sample_step), t.tai
    )

    pass_times = [timescale.tai_jd([find_rising(_), _.tai, find_setting(_)]) for _ in t_peaks if alt_f(_) > 0]

    return WindowPasses(diff, pass_times)

def pass_estimation_wrapper(
        birdplan
        , satellite_name
        , grid
        , window_start
        , window_days
        , minimum_altitude):
    '''Call PassQuery with skyfield API objects.

    :param birdplan: an BirdPlan object encapsulating global state
    :param satellite_name: the name of a satellite in the TLE file
    :param grid: Earth reference location (Maidenhead grid)
    :param window_start: starting time window to search for passes (Y, m, d) tuple
    :param window_days: how many days to search for -- less accuracy beyond a week
    :param minimum_altitude: minimum peak altitude pass filter
    '''

    # pylint: disable=too-many-arguments
    # Necessary to avoid passing global state along with parameters.

    window_minutes = 24.0 * 60.0 * window_days
    time_range = birdplan.timescale.utc(*window_start, 0, range(int(window_minutes)))

    all_passes = estimate_window_passes(
        birdplan.timescale
        , birdplan.tle[satellite_name]
        , Topos(*mh.toLoc(grid))
        , time_range[0]
        , time_range[-1]
        , minimum_altitude
    )

    return WindowPasses(
        all_passes.diff
        , [
            _pass for _pass in all_passes.passes
            if all_passes.diff.at(_pass[1]).altaz()[0].degrees >= minimum_altitude
        ]
    )
