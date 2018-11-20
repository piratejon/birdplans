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

class TestBirdplan(unittest.TestCase):
    '''exercise the various functions in birdplan'''

    def test_allthethings(self):
        '''do what we're supposed to do'''
        plan = Birdplan()

        # check initialization stuff
        self.assertEqual(plan.tle_file, 'data/tle/amateur.txt')
        self.assertTrue('FOX-1B' in plan.tle)

        # find next 24hrs passes
        results = plan.query_pass(
            'SO-50', 'EM15ek', plan.timescale.utc(2018, 11, 19, 2, 11, 0)
        )
        self.assertAlmostEqual(results.latlng[0], 35.41667, places=5)
        self.assertAlmostEqual(results.latlng[1], -97.66667, places=5)
        self.assertAlmostEqual(results.alt.degrees, 26.71944, places=5)
        self.assertAlmostEqual(results.azimuth.degrees, 196.69795, places=5)
        self.assertAlmostEqual(results.distance, 1244.45630, places=5)
        #self.assertEqual(results.point[0].t, (2018, 11, 19, 2, 6, 33))
        #self.assertEqual(results.point[0].az, 200)
        #self.assertEqual(results.point[-1].t, (2018, 11, 19, 2, 21, 12))
        #self.assertEqual(results.point[-1].az, 30)

class BirdplanResults:
    '''results of a birdplan query'''

    def __init__(self, latlng, topocentric):
        '''set us up the fields'''
        self.latlng = latlng
        self.alt, self.azimuth, self.distance = topocentric.altaz()
        self.distance = self.distance.km

class Birdplan:
    '''interface for bird planning'''

    def __init__(self, tle_file='data/tle/amateur.txt'):
        '''initialize persistent state'''
        self.tle_file = tle_file
        self.tle = load.tle(tle_file)
        self.timescale = load.timescale()

    def query_pass(self, bird, maidenhead, when):
        '''find the altitude, azimuth, and distance of bird with respect to maidenhead at time'''
        where = mh.toLoc(maidenhead)
        diff = self.tle[bird] - Topos(*where)
        topocentric = diff.at(when)
        return BirdplanResults(where, topocentric)
