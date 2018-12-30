#!/usr/bin/env python3

'''
satellitepasspredictor.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

predict upcoming satellite passes at a given location
'''

import datetime
import math

from collections import namedtuple

import numpy as np

from skyfield.api import Topos, Loader
from scipy import optimize

Pass = namedtuple('Pass', ['AOS', 'TCA', 'LOS'])
WindowPasses = namedtuple('WindowPasses', ['diff', 'passes'])

TIMESCALE = Loader('data/skyfield').timescale()

def estimate_window_passes(satellite, location, window_start, window_end):
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

    orbit_period_per_day = ((2.0 * np.pi) / satellite.model.no) / 24.0 / 60.0
    window_revolutions = window_duration / orbit_period_per_day
    sample_points = int(math.ceil(window_revolutions * 6.0))
    sample_step = window_duration / sample_points

    sample_time_range = TIMESCALE.tai_jd([
        window_start.tai + (_ * sample_step)
        for _ in range(sample_points)
    ])

    alt_f = lambda t: diff.at(t).altaz()[0].degrees

    sample_altitudes = alt_f(sample_time_range)

    left_diff = np.ediff1d(sample_altitudes, to_begin=0.0)
    right_diff = np.ediff1d(sample_altitudes, to_end=0.0)
    maxima = (left_diff > 0.0) & (right_diff < 0.0)

    minus_alt_f_wrapper = lambda t: -alt_f(TIMESCALE.tai_jd(t))
    find_peaks = lambda t: optimize.minimize_scalar(
        minus_alt_f_wrapper
        , bracket=[t.tai + sample_step, t.tai - sample_step]
        , tol=(1.0 / 24.0 / 60.0 / 60.0) / t.tai
    ).x

    t_peaks = TIMESCALE.tai_jd([
        find_peaks(ti) for ti in sample_time_range[maxima]
    ])

    rising_setting_wrapper = lambda t: -minus_alt_f_wrapper(t)
    find_rising = lambda t: optimize.brentq(
        rising_setting_wrapper, t.tai - (2.0 * sample_step), t.tai
    )
    find_setting = lambda t: optimize.brentq(
        rising_setting_wrapper, t.tai + (2.0 * sample_step), t.tai
    )

    pass_times = [
        Pass(*TIMESCALE.tai_jd([find_rising(_), _.tai, find_setting(_)]))
        for _ in t_peaks if alt_f(_) > 0
    ]

    return WindowPasses(diff, pass_times)

def pass_estimation_wrapper(
        satellite
        , latlng
        , window_start
        , window_days
        , minimum_altitude=None):
    '''Call estimate_window_passes with skyfield API objects.

    :param satellite: SkyField satellite object to compute passes for
    :param latlng: Earth reference point expressed as a tuple of floats
    :param window_start: pass estimation window start time as tz-aware Python datetime
    :param window_days: how many days to estimate passes for
    :param minimum_altitude: minimum peak altitude pass filter, default 0
    '''

    # pylint: disable=too-many-arguments
    # Necessary to avoid passing global state along with parameters.

    minimum_altitude = 0 if minimum_altitude is None else minimum_altitude

    time_start = TIMESCALE.utc(window_start)
    time_end = TIMESCALE.utc(window_start + datetime.timedelta(days=window_days))

    all_passes = estimate_window_passes(
        satellite
        , Topos(*latlng)
        , time_start
        , time_end
    )

    return WindowPasses(
        all_passes.diff
        , [
            _pass for _pass in all_passes.passes
            if all_passes.diff.at(_pass.TCA).altaz()[0].degrees >= minimum_altitude
        ]
    )
