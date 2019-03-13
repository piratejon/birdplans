#!/usr/bin/env python3

'''
tzhelper.py
2019-01-01
jonathanwesleystone+KI5BEX@gmail.com

timezone helpers, for supplying offset data to clients, such as Elm's customTimeZone
'''

import pytz

def make_tzinfo_entry(change):
    '''Make a single tz entry.
    '''

    return {
        'start': int(change.timestamp() / 60),
        'offset': int(change.utcoffset().total_seconds() / 60)
    }

def make_tzinfo(tz, window_start, window_stop):
    '''Subset and format the tz stuff for the client.
    '''

    changes = [
        make_tzinfo_entry(tz.localize(_))
        for _ in sorted(tz._utc_transition_times) # pylint: disable=protected-access
        if window_start <= pytz.utc.localize(_) <= window_stop
    ]

    start_entry = make_tzinfo_entry(window_start)
    end_entry = make_tzinfo_entry(window_stop)

    if not changes:
        changes = [start_entry]

    if start_entry['offset'] != changes[0]['offset']:
        changes = [start_entry] + changes

    if end_entry['offset'] != changes[-1]['offset']:
        changes = changes + [end_entry]

    changes = sorted(changes, key=lambda x: x['start'], reverse=True)

    return changes
