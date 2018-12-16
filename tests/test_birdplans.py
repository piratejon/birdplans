#!/usr/bin/env python3

'''
test_birdplans.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

birdplans package unit tests
'''

import unittest

class TestBirdPlans(unittest.TestCase):
    '''exercise the various functions in birdplan'''

    def test_pass_query(self):
        '''exercise querying a pass'''

        # find 30-degree-plus passes of AO-91 (FOX-1B) over EM15 upto 5 days after 2018-11-24
        result = pass_query_wrapper('AO-91', 'EM15', (2018, 11, 24), 5, 30.0)
        self.assertEqual(len(result.passes), 8)
        self.assertEqual(result.passes[0][0].utc_iso(), '2018-11-24T07:53:12Z')
        self.assertEqual(result.passes[7][1].utc_iso(), '2018-11-28T18:43:25Z')
        self.assertEqual(result.passes[7][2].utc_iso(), '2018-11-28T18:49:05Z')

    def test_SatellitePassPredictor(self):
        '''basic sanity checks'''
        result = pass_query_wrapper('AO-91', 'EM15', (2018, 11, 24), 5, 30.0)
        self.assertEqual(len(result.passes), 8)
        self.assertEqual(result.passes[0][0].utc_iso(), '2018-11-24T07:53:12Z')
        self.assertEqual(result.passes[7][1].utc_iso(), '2018-11-28T18:43:25Z')
        self.assertEqual(result.passes[7][2].utc_iso(), '2018-11-28T18:49:05Z')
