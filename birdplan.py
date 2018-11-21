#!`/usr/bin/env python3`

'''
birdplan.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

predict upcoming satellite passes at a given location
'''

import unittest

from skyfield.api import load, Topos
import maidenhead as mh
from scipy import optimize
import numpy as np

class TestBirdplan(unittest.TestCase):
    '''exercise the various functions in birdplan'''

    def test_allthethings(self):
        '''do what we're supposed to do'''
        plan = Birdplan()

        # check initialization stuff
        self.assertEqual(plan.tle_file, 'data/tle/amateur.txt')
        self.assertTrue('SO-50' in plan.tle)

        # find next 24hrs passes
        results = plan.query_point_in_time(
            'SO-50', 'EM15ek', plan.timescale.utc(2018, 11, 19, 2, 11, 0)
        )
        self.assertAlmostEqual(results.latlng[0], 35.41667, places=5)
        self.assertAlmostEqual(results.latlng[1], -97.66667, places=5)
        self.assertAlmostEqual(results.alt.degrees, 26.71944, places=5)
        self.assertAlmostEqual(results.azimuth.degrees, 196.69795, places=5)
        self.assertAlmostEqual(results.distance, 1244.45630, places=5)

        results = plan.query_pass(
            'SO-50', 'EM15ek', plan.timescale.utc(2018, 11, 19, 0, 0, 0), 24, 15
        )

class BirdplanResults:
    '''results of a birdplan query'''

    def __init__(self, latlng, topocentric):
        '''set us up the fields'''
        self.latlng = latlng
        self.alt, self.azimuth, self.distance = topocentric.altaz()
        self.distance = self.distance.km

def f_altitude(bird, topos, time_t):
    '''calculate the altitude of bird with respect to topos at time_t'''
    (bird - topos).at(time_t).topocentric.altaz()[0]

class Birdplan:
    '''interface for bird planning'''

    def __init__(self, tle_file='data/tle/amateur.txt'):
        '''initialize persistent state'''
        self.tle_file = tle_file
        self.tle = load.tle(tle_file)
        self.timescale = load.timescale()

    def query_point_in_time(self, bird, maidenhead, when):
        '''find the altitude, azimuth, and distance of bird with respect to maidenhead at time'''
        where = mh.toLoc(maidenhead)
        diff = self.tle[bird] - Topos(*where)
        topocentric = diff.at(when)
        return BirdplanResults(where, topocentric)

    def query_pass(bird, maidenhead, start, dur_hrs, min_alt):
        '''
        try this:
        <https://github.com/skyfielders/astronomy-notebooks/blob/master/Solvers/Earth-Satellite-Passes.ipynb>
        as access 2018-11-19
        '''
        where = mh.toLoc(maidenhead)
        diff = self.tle[bird] - Topos(*where)

        orbit_period_per_minute = (2.0 * np.pi) / self.tle[bird].model.no
        orbit_period = orbit_period_per_minute / 24.0 / 60.0
        revolutions_per_day = 1.0 / orbit_period
        step = orbit_period / 6
        t0 = start.tai
        t = t0 + np.arange(0, 1.0, step)
        dt = JulianDate(tai=t).utc_datetime()
        altitudes = f_altitude(self.tle[bird], Topos(*where), dt) # diff.at(dt).topocentric.altaz()[0]
        left_diff = np.ediff1d(altitudes, to_begin=0.0)
        right_diff = np.ediff1d(altitudes, to_end=0.0)
        maxima = (left_diff > 0.0) & (right_diff < 0.0)

        result = optimize.minimize_scalar(lambda t: -f_altitude(t), bracket=[t + step, t - step], tol=one_second / t)
