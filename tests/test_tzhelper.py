#!/usr/bin/env python3

'''
test_tzhelper.py
2019-01-01
jonathanwesleystone+KI5BEX@gmail.com

exercize tzhelper module
'''

import unittest

import datetime
import pytz

from birdplans import tzhelper

class TestTzHelper(unittest.TestCase):
    '''exercise the various functions in TestTzHelper
    '''

    def test_normal_window(self):
        '''prepare timezone info for a non-time-changing window
        '''

        tz = pytz.timezone('America/Chicago')
        start = tz.localize(datetime.datetime(2018, 12, 12, 12, 12))
        end = tz.localize(datetime.datetime(2018, 12, 20, 20, 20))

        self.assertEqual(-360, tzhelper.make_tzinfo_entry(start)['offset'])

        changes = tzhelper.make_tzinfo(tz, start, end)
        self.assertEqual(1, len(changes))
        self.assertEqual(-360, changes[0]['offset'])
        self.assertEqual(int(start.timestamp() / 60), changes[0]['start'])

    def test_dst_crossing_window(self):
        '''prepare timezone info for a window that crosses one or more time changes
        '''
        tz = pytz.timezone('America/Chicago')
        start = tz.localize(datetime.datetime(2018, 12, 12, 12, 12))
        end = tz.localize(datetime.datetime(2019, 12, 20, 20, 20))

        self.assertEqual(-360, tzhelper.make_tzinfo_entry(start)['offset'])

        changes = tzhelper.make_tzinfo(tz, start, end)
        self.assertEqual(3, len(changes))
        self.assertEqual(-360, changes[0]['offset'])
        self.assertEqual(int(start.timestamp() / 60), changes[0]['start'])
