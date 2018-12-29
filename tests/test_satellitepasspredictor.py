#!/usr/bin/env python3

'''
test_satellitepasspredictor.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

estimate_window_passes unit tests
'''

import unittest

from birdplans.satellitepasspredictor import pass_estimation_wrapper

from birdplans.tlemanager import TestTleManager
from birdplans.birdplans import BirdPlan

class TestSatellitePassPredictor(unittest.TestCase):
    '''exercise the various functions in SatellitePassPredictor'''

    def test_estimate_window_passes(self):
        '''make sure we can guess where it's gonna be'''
        birdplan = BirdPlan(TestTleManager())
        result = pass_estimation_wrapper(birdplan, 'AO-91', (35.0, -98.0), (2018, 11, 24), 5, 30.0)
        self.assertEqual(len(result.passes), 8)
        self.assertEqual(result.passes[0][0].utc_iso(), '2018-11-24T07:53:12Z')
        self.assertEqual(result.passes[7][1].utc_iso(), '2018-11-28T18:43:25Z')
        self.assertEqual(result.passes[7][2].utc_iso(), '2018-11-28T18:49:05Z')
