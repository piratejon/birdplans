#!/usr/bin/env python3

'''
test_satellitepasspredictor.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

estimate_window_passes unit tests
'''

import unittest

import datetime
import pytz

from birdplans.satellitepasspredictor import pass_estimation_wrapper

from birdplans.tlemanager import TestTleManager

class TestSatellitePassPredictor(unittest.TestCase):
    '''exercise the various functions in SatellitePassPredictor
    '''

    def test_estimate_window_passes(self):
        '''make sure we can guess where it's gonna be
        '''
        tle = TestTleManager()
        window_start = datetime.datetime(2018, 11, 24, tzinfo=pytz.utc)
        window_stop = window_start + datetime.timedelta(days=5)
        result = pass_estimation_wrapper(
            tle['AO-91']
            , (35.0, -98.0)
            , window_start
            , window_stop
            , 30.0
        )
        self.assertEqual(len(result.passes), 8)
        self.assertEqual(result.passes[0][0].utc_iso(), '2018-11-24T07:53:12Z')
        self.assertEqual(result.passes[7][1].utc_iso(), '2018-11-28T18:43:25Z')
        self.assertEqual(result.passes[7][2].utc_iso(), '2018-11-28T18:49:05Z')
