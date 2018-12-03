#!`/usr/bin/env python3`

'''
birdplan.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

predict upcoming satellite passes at a given location
'''

import unittest
import math
import json
import html
import sys

from datetime import datetime, timezone
from urllib import parse

import requests
import pytz

import maidenhead as mh
import numpy as np

from skyfield.api import load, Topos
from tzwhere import tzwhere
from scipy import optimize

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

    def test_load_tle_json(self):
        '''make sure we can parse the curated bird list'''
        src = 'data/tle/choice_birds.json'
        tleman = TleManager(src)
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

class TleManager:
    '''keep the TLE files updated'''

    def __init__(self, tlesrcfile=None, tledbcurrent=None, tledbhistory=None):
        '''load up a birdlist

        :param tlesrcfile: JSON file linking the birds to their TLEs
        :param tledb: JSON file containing the downloaded TLE logs and history
        '''

        self.tlesrcfile = 'data/tle/choice_birds.json' if tlesrcfile is None else tlesrcfile
        self.tledbcurrent = 'tledbcurrent.json' if tledbcurrent is None else tledbcurrent
        self.tledbhistory = 'tledbhistory.json' if tledbhistory is None else tledbhistory

        with open(self.tlesrcfile, 'r') as fin:
            self.tlesrcs = json.load(fin)

        self.bird_tles = self.load()
        # this has the tle with our aliases
        self.tlestring = '\n'.join([key + '\n' + value for key, value in self.bird_tles.items()])

    def load(self):
        '''load the current tle data into a dict of {bird_alias: 'tle\nlines'}
        '''

        with open(self.tledbcurrent, 'r') as fin:
            tledbcurrent = json.load(fin)

        bird_tles = {}
        for source in self.tlesrcs['sources']:
            lines = tledbcurrent[source]['body'].splitlines()
            for birdname, bird in self.tlesrcs['birds'].items():
                if 'source' in bird and bird['source'] == source:
                    lineiter = iter(lines)
                    for line in lineiter:
                        if bird['name'] == line.strip():
                            bird_tles[birdname] = next(lineiter) + '\n' + next(lineiter)
                            break

        return bird_tles

    def update(self, keep_history=True):
        '''update the tles if needed
        '''
        try:
            with open(self.tledbcurrent, 'r') as fin:
                tledbcurrent = json.load(fin)
        except FileNotFoundError:
            tledbcurrent = {}

        try:
            with open(self.tledbhistory, 'r') as fin:
                tledbhistory = json.load(fin)
        except FileNotFoundError:
            tledbhistory = {}

        for source in self.tlesrcs['sources']:
            wsrc = tledbcurrent.get(source, {})

            headers = {}
            if 'etag' in wsrc:
                headers['etag'] = wsrc['etag']
            if 'last-modified' in wsrc:
                headers['If-Modified-Since'] = wsrc['last-modified']

            response = requests.get(self.tlesrcs['sources'][source]['url'], headers=headers)

            now = datetime.now().astimezone().isoformat()

            wsrc['checked'] = now
            wsrc['status'] = response.status_code

            if response.status_code == 200:
                wsrc['body'] = response.text
                wsrc['updated'] = now

            if 'etag' in response.headers:
                wsrc['etag'] = response.headers['etag']
            if 'last-modified' in response.headers:
                wsrc['last-modified'] = response.headers['last-modified']

            tledbcurrent[source] = wsrc

            if keep_history:
                tledbhistory[source] = tledbhistory.get(source, [])
                tledbhistory[source].append({
                    'when': now,
                    'status': response.status_code,
                    'text': response.text,
                    'etag': response.headers.get('etag'),
                    'last-modified': response.headers.get('last-modified')
                })

        with open(self.tledbcurrent, 'w') as fout:
            json.dump(tledbcurrent, fout)

        if keep_history:
            with open(self.tledbhistory, 'w') as fout:
                json.dump(tledbhistory, fout)

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
        '''Initialize persistent state.
        '''
        self.tle_file = tle_file
        self.tle = load.tle(tle_file)
        self.timescale = load.timescale()

    def add_satellite_alias(self, satellite, alias):
        '''Set an alias for a satellite in the TLE.
        '''
        self.tle[alias] = self.tle[satellite]

    def query_point_in_time(self, bird, grid, when):
        '''Find the altitude, azimuth, and distance of bird with respect to Maidenhead grid at time.
        '''
        where = mh.toLoc(grid)
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
        :param satellite: a Skyfield Satellite object representing the satellite we want to track
        :param location: a Skyfield Topos object representing our Earth-based reference point
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

        alt_f = lambda t: self.altaz(t)[0].degrees

        self.orbit_period_per_minute = (2.0 * np.pi) / self.satellite.model.no
        self.window_width = window_end - window_start
        self.window_revolutions = self.window_width / (self.orbit_period_per_minute / 24.0 / 60.0)
        self.sample_points = int(math.ceil(self.window_revolutions * 6.0))
        self.sample_step = self.window_width / self.sample_points
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

    def altaz(self, time):
        '''Altitude, azimuth, and distance for satellite-home at time.
        '''
        return self.diff.at(time).altaz()

def pass_query_wrapper(
        satellite_name
        , grid
        , window_start
        , window_days
        , minimum_altitude
        , birdplan=None):
    '''Call PassQuery with skyfield API objects.

    :param satellite: the name of a satellite in the TLE file
    :param grid: Earth reference location (Maidenhead grid)
    :param window_start: starting time window to search for passes (Y, m, d) tuple
    :param window_days: how many days to search for -- more than a week does not usually make sense
    :param minimum_altitude: minimum peak altitude pass filter
    :param birdplan: an BirdPlan object, if None then a new one will be created.
    '''
    if birdplan is None:
        birdplan = BirdPlan()

    topos = Topos(*mh.toLoc(grid))
    window_minutes = 24.0 * 60.0 * window_days
    time_range = birdplan.timescale.utc(*window_start, 0, range(int(window_minutes)))

    return PassQuery(
        birdplan
        , birdplan.tle[satellite_name]
        , topos
        , time_range[0]
        , time_range[-1]
        , minimum_altitude)

def multibird_pass_query_wrapper(
        satellite_names
        , grid
        , window_start
        , window_days
        , minimum_altitude):
    '''Call PassQuery with several birds, sorting the results by rising time.

    :param satellite_names: iterable of satellite names in birdplan.tle
    :param grid: Maidenhead grid locator for earth reference point
    :param window_start: (year, month, day) tuple to start searching from
    :param window_days: number of days to query passes for
    :param minimum_altitude: minimum peak elevation to query
    '''

    birdplan = BirdPlan()

    window_minutes = 24.0 * 60.0 * window_days
    time_range = birdplan.timescale.utc(*window_start, 0, range(int(window_minutes)))

    return [
        (
            satellite_name
            , PassQuery(
                birdplan
                , birdplan.tle[satellite_name]
                , Topos(*mh.toLoc(grid))
                , time_range[0]
                , time_range[-1]
                , minimum_altitude)
        )
        for satellite_name in satellite_names
    ]

class Message:
    '''A message displayed with the results.
    '''

    def __init__(self, message, error=False):
        '''Initialize'''
        self.message = message
        self.error = error

    def render(self):
        return '<p class="message error{}">{}</p>'.format(
            str(self.error), html.escape(self.message)
        )

    def __str__(self):
        return self.render()

def web_query_wrapper(query_string, window_start_datetime, window_days=None):
    '''Given a query string, prepare results that can go to JSON or HTML.

    :param query_string: dict representing parsed query string with list values
    :param window_start_datetime: beginning of window to search for passes
    :param window_days: number of days to search (default 3)
    '''
    if not window_days:
        window_days = 3

    messages = []
    t0 = datetime.now(timezone.utc)

    grid = None
    try:
        grid = query_string['grid'][0]
    except KeyError:
        messages.append(Message("Missing key 'grid'", True))

    try:
        latlng = mh.toLoc(grid)
    except Exception as ex:
        messages.append(Message("Exception decoding grid: {}".format(str(ex)), True))

    tzname = 'UTC'
    try:
        tzname = query_string['tz'][0]
    except KeyError:
        try:
            tzname = tzwhere.tzNameAt(*latlng)
            messages.append(
                Message('Inferring local timezone {} from location {}'.format(tzname, latlng))
            )
        except Exception as ex:
            messages.append(
                Message("Exception inferring local timezone': {}".format(str(ex)), True)
            )

    tz = pytz.utc
    try:
        tz = pytz.timezone(tzname)
    except Exception as ex:
        messages.append(
            Message('Exception looking up local timezone, using UTC: {}'.format(str(ex)), True)
        )

    # [now, now + 5 days]
    start_time = global_birdplan.timescale.utc(window_start_datetime)
    end_time = global_birdplan.timescale.tai_jd(start_time.tai + window_days)

    topos = None
    try:
        topos = Topos(*latlng)
    except Exception as ex:
        messages.append(Message('Exception initializing Topos: {}'.format(str(ex)), True))

    minimum_altitude = 30.0
    try:
        minimum_altitude = float(query_string['alt'][0])
    except Exception as ex:
        messages.append(
            Message('Exception decoding minimum altitude; using {:.2f}: {}'.format(
                minimum_altitude, str(ex)
            ), True)
        )

    satellite_names = []
    try:
        satellite_names = query_string['sat']
    except KeyError:
        messages.append(Message('No satellites specified', True))

    results = []
    try:
        results = [
            (
                satellite_name
                , PassQuery(
                    global_birdplan
                    , global_birdplan.tle[satellite_name]
                    , topos
                    , start_time
                    , end_time
                    , minimum_altitude)
            )
            if satellite_name in global_birdplan.tle
            else (satellite_name, None)
            for satellite_name in satellite_names
        ]
    except Exception as ex:
        messages.append(Message('PassQuery exception: {}'.format(str(ex)), True))

    missing_birds = set(satellite_names) - set(global_birdplan.tle.keys())
    if missing_birds:
        messages.append(Message('Birds not found: {}'.format(';'.join(missing_birds)), True))

    t1 = datetime.now(timezone.utc)

    return {
        'grid': grid,
        'tzname': tzname,
        'topos': topos,
        'start_time': start_time,
        'end_time': end_time,
        'tz': tz,
        'minimum_altitude': minimum_altitude,
        'messages': messages,
        'results': results,
        'query_time': t1 - t0
    }

def make_pass_tuples(results):
    '''Get the packed format into a tuple we can easily sort and yield.
    '''
    for bird, passquery in results:
        if passquery:
            for _pass in passquery.passes:
                yield (bird, passquery, *_pass)


def html_web_wrapper(query_string, now):
    '''Do a query and return the results in an HTML table.
    '''

    results = web_query_wrapper(query_string, now)

    yield '<ul>'
    for message in results['messages']:
        yield '<li>' + str(message)
    yield '</ul>'

    yield '<table border="1">'
    yield '''
        <tr>
            <th rowspan=2>Bird
            <th rowspan=2>Max El
            <th rowspan=2>Duration (Minutes)
            <th colspan=3>Azimuth
            <th colspan=3>{}
            <th colspan=3>UTC
            <th colspan=2>TLE Epoch'''.format(results['tzname'])

    yield '<tr><th>AOS<th>TCA<th>LOS<th>AOS<th>TCA<th>LOS<th>AOS<th>TCA<th>LOS<th>Timestamp<th>Age'

    sorted_passes = sorted(make_pass_tuples(results['results']), key=lambda r: r[2].tai)

    long_strftime = '%Y-%m-%d %H:%M:%S %Z'
    short_strftime = '%H:%M:%S'

    for _pass in sorted_passes:
        bird, pq, aos, tca, los = _pass
        yield '<tr>' + ''.join('<td>{}'.format(html.escape(_)) for _ in [
            bird
            , '{:.2f}'.format(pq.altaz(tca)[0].degrees)
            #, '{:.2f}'.format((los - aos) * 24.0 * 60.0)
            , str(los.astimezone(pytz.UTC) - aos.astimezone(pytz.UTC))
            , '{:.2f}'.format(pq.altaz(aos)[1].degrees)
            , '{:.2f}'.format(pq.altaz(tca)[1].degrees)
            , '{:.2f}'.format(pq.altaz(los)[1].degrees)
            , aos.astimezone(results['tz']).strftime(long_strftime)
            , tca.astimezone(results['tz']).strftime(short_strftime)
            , los.astimezone(results['tz']).strftime(short_strftime)
            , aos.astimezone(pytz.UTC).strftime(long_strftime)
            , tca.astimezone(pytz.UTC).strftime(short_strftime)
            , los.astimezone(pytz.UTC).strftime(short_strftime)
            , pq.satellite.epoch.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            , str(
                pq.birdplan.timescale.utc(now).astimezone(pytz.UTC) -
                pq.satellite.epoch.astimezone(pytz.UTC)
            )
        ])

    yield '</table>'

    yield '<p>Time to find passes: {}'.format(results['query_time'])

def application(env, start_response):
    '''uWSGI handler.
    '''
    encoding = 'utf-8'
    keys = parse.parse_qs(env['QUERY_STRING'])
    start_response('200 OK', [('Content-Type', 'text/html; charset={}'.format(encoding))])
    yield bytes('''
    <!DOCTYPE html>
    <html>
        <head>
            <title>birdplan</title>
            <meta charset="utf-8" />
        </head>
        <body>
            <h1>birdplan</h1>
            <form method="get">
                <h2>Query bird passes</h2>
                <ul class="birdqueryform">
                    <li>Grid earth reference/QTH: <input name="grid" type="text" maxlength="8" placeholder="FN03hp" value="{}" /> (<a href='http://www.levinecentral.com/ham/grid_square.php' target="_blank">find yourself</a>)
                    <li>Bird minimum peak altitude: <input name="alt" type="number" min="1" max="90" value="{}" placeholder="30" /> degrees above the horizon
                    <li>Birds:<p><select name="sat" multiple size=8>
    '''.format(
        keys['grid'][0] if 'grid' in keys else ''
        , keys['alt'][0] if 'alt' in keys else ''
    ), encoding)

    sats = set(keys.get('sat', []))

    for sat in sorted(set(global_birdplan.tle.values()), key=lambda s: s.name):
        yield bytes(
            '<option value="{0}" {1}>{0}</option>'.format(
                sat.name, 'selected' if sat.name in sats else ''
            ), encoding
        )

    yield bytes('''
                        </select>
                    <li><input type="submit" value="Search" />
                </ul>
            </form>
    ''', encoding)

    if keys:
        yield from [bytes(_, encoding) for _ in html_web_wrapper(keys, datetime.now(timezone.utc))]

    yield bytes('''
    <!--
    <p>tip: {}
    <p>Worker ID: {}
    -->
    '''.format(sys.argv[1] if 1 < len(sys.argv) else 'no tip', uwsgi.worker_id()), encoding)

    yield bytes('''
        </body>
    </html>
    ''', encoding)

try:
    import uwsgi
    # this is meant to be shared across uWSGI application() invocations
    tzwhere = tzwhere.tzwhere()
    global_birdplan = BirdPlan()
    global_birdplan.add_satellite_alias('FOX-1B', 'AO-91')
    uwsgi.log('{}'.format(tzwhere))
    uwsgi.log('{}'.format(global_birdplan))
except ImportError:
    pass
