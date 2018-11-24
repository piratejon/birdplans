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
        self.assertTrue('FOX-1B' in plan.tle)
        self.assertFalse('AO-91' in plan.tle)
        plan.add_satellite_alias('FOX-1B', 'AO-91')
        self.assertTrue('AO-91' in plan.tle)

        # find next 24hrs passes
        results = plan.query_point_in_time(
            'SO-50', 'EM15ek', plan.timescale.utc(2018, 11, 19, 2, 11, 0)
        )
        self.assertAlmostEqual(results.latlng[0], 35.41667, places=5)
        self.assertAlmostEqual(results.latlng[1], -97.66667, places=5)
        self.assertAlmostEqual(results.alt.degrees, 26.71944, places=5)
        self.assertAlmostEqual(results.azimuth.degrees, 196.69795, places=5)
        self.assertAlmostEqual(results.distance, 1244.45630, places=5)

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

class PassQuery:
    '''
    try this:
    <https://github.com/skyfielders/astronomy-notebooks/blob/master/Solvers/Earth-Satellite-Passes.ipynb>
    as accessed 2018-11-19

    encapsulated to return a number of values to the user
    '''

    def __init__(self, birdplan, satellite, location, timerange):
        '''Predict passings of a satellite over a point on the earth during a given time window.

        :param birdplan: a Birdplan object containing a timescale and 
        :param satellite: the name of a satellite to lookup in birdplan.tle
        :param location: the Topos object 
        :param timerange: a Time array under which to find passes
        '''
        self.birdplan = birdplan
        self.location = location
        self.timerange = timerange

class Birdplan:
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
        return BirdplanResults(where, topocentric)
