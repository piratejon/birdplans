#!/usr/bin/env python3

'''
test_tlemanager.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

TleManager unit tests
'''

import unittest

from birdplans.tlemanager import TleManager

class TestTleManager(unittest.TestCase):
    '''Make sure our tlemanager does good.'''

    def test_load_tle_json(self):
        '''make sure we can parse the curated bird list'''
        tleman = TleManager(None, 'data/test/tledbcurrent.json', 'data/test/tledbhistory.json')
        self.assertTrue({
            'AO-7'
            , 'AO-73'
            , 'CAS-4B'
            , 'EO-88'
            , 'UKUBE-1'
            , 'XW-2A'
            , 'XW-2B'
            , 'XW-2C'
            , 'XW-2D'
            , 'XW-2F'
            , 'FO-29'
            , 'SO-50'
            , 'LilacSat2'
            , 'AO-85'
            , 'AO-91'
            , 'AO-92'
            }.issubset(tleman.bird_tles))

if __name__ == '__main__':
    unittest.main()
