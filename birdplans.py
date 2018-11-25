#!`/usr/bin/env python3`

'''
birdplan.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

predict upcoming satellite passes at a given location
'''

import unittest

import math

from skyfield.api import load, Topos
import maidenhead as mh
from scipy import optimize
import numpy as np

class TestBirdPlan(unittest.TestCase):
    '''exercise the various functions in birdplan'''

    def test_birdplan_init(self):
        '''exercise birdplan constructor and alias'''
        plan = BirdPlan()

        # check initialization stuff
        self.assertEqual(plan.tle_file, 'data/tle/amateur.txt')
        self.assertTrue('SO-50' in plan.tle)
        self.assertTrue('FOX-1B' in plan.tle)
        self.assertFalse('AO-91' in plan.tle)
        plan.add_satellite_alias('FOX-1B', 'AO-91')
        self.assertTrue('AO-91' in plan.tle)

    def test_query_point_in_time(self):
        '''do what we're supposed to do'''
        plan = BirdPlan()

        results = plan.query_point_in_time(
            'SO-50', 'EM15ek', plan.timescale.utc(2018, 11, 19, 2, 11, 0)
        )
        self.assertAlmostEqual(results.latlng[0], 35.41667, places=5)
        self.assertAlmostEqual(results.latlng[1], -97.66667, places=5)
        self.assertAlmostEqual(results.alt.degrees, 26.71944, places=5)
        self.assertAlmostEqual(results.azimuth.degrees, 196.69795, places=5)
        self.assertAlmostEqual(results.distance, 1244.45630, places=5)

    def test_pass_query(self):
        '''exercise querying a pass'''

        # find 30-degree-plus passes of AO-91 (FOX-1B) over EM15 upto 5 days after 2018-11-24
        result = pass_query_wrapper('FOX-1B', 'EM15', (2018, 11, 24), 5, 30.0)
        self.assertEqual(len(result.passes), 8)
        self.assertEqual(result.passes[0][0].utc_iso(), '2018-11-24T07:53:12Z')
        self.assertEqual(result.passes[7][1].utc_iso(), '2018-11-28T18:43:24Z')
        self.assertEqual(result.passes[7][2].utc_iso(), '2018-11-28T18:49:05Z')

class BirdPlanResults:
    '''results of a birdplan query'''

    def __init__(self, latlng, topocentric):
        '''set us up the fields'''
        self.latlng = latlng
        self.alt, self.azimuth, self.distance = topocentric.altaz()
        self.distance = self.distance.km

class BirdPlan:
    '''interface for bird planning'''

    def __init__(self, tle_file='data/tle/amateur.txt'):
        '''initialize persistent state'''
        self.tle_file = tle_file
        self.tle = load.tle(tle_file)
        self.timescale = load.timescale()

    def add_satellite_alias(self, satellite, alias):
        self.tle[alias] = self.tle[satellite]

    def query_point_in_time(self, bird, maidenhead, when):
        '''find the altitude, azimuth, and distance of bird with respect to maidenhead at time'''
        where = mh.toLoc(maidenhead)
        diff = self.tle[bird] - Topos(*where)
        topocentric = diff.at(when)
        return BirdPlanResults(where, topocentric)

class PassQuery:
    '''
    try this:
    <https://github.com/skyfielders/astronomy-notebooks/blob/master/Solvers/Earth-Satellite-Passes.ipynb>
    as accessed 2018-11-19

    encapsulated to return a number of values to the user
    '''

    def __init__(self, birdplan, satellite, location, window_start, window_end, minimum_altitude):
        '''Predict passings of a satellite over a point on the earth during a given time window.

        :param birdplan: a BirdPlan object containing a SkyField timescale
        :param satellite: a Skyfield Satellite object
        :param location: a Skyfield Topos object 
        :param window_start: Skyfield Time object; search window start
        :param window_end: Skyfield Time object; search window end
        :param minimum_altitude: exclude passes peaking below this altitude
        '''
        self.birdplan = birdplan
        self.satellite = satellite
        self.location = location
        self.window_start = window_start
        self.window_end = window_end
        assert window_start.tai < window_end.tai
        self.minimum_altitude = minimum_altitude

        self.diff = self.satellite - self.location

        alt_f = lambda t: self.diff.at(t).altaz()[0].degrees

        self.orbit_period_per_minute = (2.0 * np.pi) / self.satellite.model.no
        self.window_revolutions = (window_end - window_start) / (self.orbit_period_per_minute / 24.0 / 60.0)
        self.sample_points = int(math.ceil(self.window_revolutions * 6.0))
        self.sample_step = (window_end - window_start) / self.sample_points
        self.sample_time_range = self.birdplan.timescale.tai_jd([
            window_start.tai + (_ * self.sample_step)
            for _ in range(self.sample_points)
        ])
        self.sample_altitudes = alt_f(self.sample_time_range)

        left_diff = np.ediff1d(self.sample_altitudes, to_begin=0.0)
        right_diff = np.ediff1d(self.sample_altitudes, to_end=0.0)
        self.maxima = (left_diff > 0.0) & (right_diff < 0.0)

        minus_alt_f_wrapper = lambda t: -alt_f(self.birdplan.timescale.tai_jd(t))
        find_highest = lambda t: optimize.minimize_scalar(
                minus_alt_f_wrapper
                , bracket=[t.tai + self.sample_step, t.tai - self.sample_step]
                , tol=(1.0 / 24.0 / 60.0 / 60.0) / t.tai
        ).x

        self.t_highest = self.birdplan.timescale.tai_jd([
            find_highest(ti) for ti in self.sample_time_range[self.maxima]
        ])

        rising_setting_wrapper = lambda t: -minus_alt_f_wrapper(t)
        find_rising = lambda t: optimize.brentq(
            rising_setting_wrapper, t.tai - (2.0 * self.sample_step), t.tai
        )
        find_setting = lambda t: optimize.brentq(
            rising_setting_wrapper, t.tai + (2.0 * self.sample_step), t.tai
        )

        filtered_peaks = self.birdplan.timescale.tai_jd([
            _.tai for _ in self.t_highest if alt_f(_) > minimum_altitude
        ])
        rising = self.birdplan.timescale.tai_jd([find_rising(_) for _ in filtered_peaks])
        setting = self.birdplan.timescale.tai_jd([find_setting(_) for _ in filtered_peaks])

        self.passes = list(zip(rising, filtered_peaks, setting))

def pass_query_wrapper(satellite_name, maidenhead, window_start, window_days, minimum_altitude, birdplan=None):
    '''Call PassQuery with skyfield API objects.
    
    :param satellite: the name of a satellite in the TLE file
    :param maidenhead: Earth reference location
    :param window_start: starting time window to search for passes (Y, m, d) tuple
    :param window_days: how many days to search for -- more than a week does not usually make sense
    :param minimum_altitude: minimum peak altitude pass filter
    :param birdplan: an BirdPlan object, if None then a new one will be created.
    '''
    if birdplan is None:
        birdplan = BirdPlan()

    topos = Topos(*mh.toLoc(maidenhead))
    window_minutes = 24.0 * 60.0 * window_days
    time_range = birdplan.timescale.utc(*window_start, 0, range(int(window_minutes)))

    return PassQuery(birdplan, birdplan.tle[satellite_name], topos, time_range[0], time_range[-1], minimum_altitude)
