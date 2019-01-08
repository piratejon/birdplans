#!/usr/bin/env python3

'''
uwsgi.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

uwsgi application wrapper/api endpoint
'''

import json
import html
import sys

from datetime import datetime, timedelta, timezone
from collections import namedtuple
from timeit import default_timer
from urllib import parse
from enum import Enum

import pytz

import maidenhead as mh
import numpy as np

from birdplans.satellitepasspredictor import pass_estimation_wrapper
from birdplans.tlemanager import TleManager
from birdplans import tzhelper

class Severity(Enum):
    '''Severity for returned API messages.
    '''
    VERBOSE = 0 # log everything
    INFO = 1 # normal operation
    WARNING = 2 # recoverable exception
    ERROR = 3 # unrecoverable exception

class Message:
    '''A message displayed with the results.
    '''

    def __init__(self, message, severity=Severity.ERROR):
        '''Initialize'''
        self.message = message
        self.severity = severity

    def render(self):
        '''Format the message as HTML for the simple client.
        '''
        return '<p class="message sev{}">{}</p>'.format(
            self.severity.name, html.escape(self.message)
        )

    def __str__(self):
        return self.render()

class ApiResponse:
    '''Encapsulate the results of a query for client consumption. Used by the simple_client
    method to generate HTML, or as JSON by the modern_client method to render on the client.
    '''

    def __init__(self, minimum_severity=None):
        self.messages = []
        self.passes = []
        self.minimum_severity = Severity.ERROR if minimum_severity is None else minimum_severity

    def message(self, severity, format_string, *args):
        '''Append a formatted message to the response.
        '''
        self.messages.append(Message(format_string.format(args), severity))

    def filtered_messages(self, severity=None):
        '''Return a filtered list of messages meeting the configured severity criteria.
        '''
        severity = self.minimum_severity if severity is None else severity
        return [_ for _ in self.messages if _.severity >= severity]

Parameters = namedtuple(
    'Parameters'
    , ['valid', 'grid', 'where', 'tz', 'start_time', 'end_time', 'birds', 'response']
)
def params_from_query(query, default):
    '''Turn a query string dict into parameters suitable for calling the prediction function.

    :param query: dict representing parsed query string with list values
    :param default: dict of parameter default values
    '''

    try:
        response = ApiResponse(Severity[query['loglevel'][0]])
    except KeyError: # query[x] or Severity[x] could trigger KeyError
        response = ApiResponse(default['loglevel'])

    try:
        grid = query['grid'][0]
    except KeyError:
        response.message(Severity.ERROR, 'mandatory parameter grid not found')
        return Parameters(valid=False, response=response)

    try:
        where = Topos(*mh.toLoc(grid))
    except (ValueError, AssertionError):
        response.message(Severity.ERROR, 'unable to decode grid {}', grid)
        return Parameters(valid=False, response=response)

    minimum_altitude = int(query.get('minimum_altitude', [default['minimum_altitude']])[0])

    tzname = query.get('tzname', [default['tzname']])[0]
    try:
        tz = pytz.timezone(tzname)
    except pytz.UnknownTimeZoneError:
        tz = default['tz']
        response.message(Severity.WARN, 'invalid tz {}, using default {}', tzname, tz)

    try:
        start_time = tz.localize(datetime.strptime(query['start_time'], '%Y-%m-%d %H:%M'))
    except (KeyError, ValueError):
        start_time = default['start_time']
        response.message(Severity.INFO, 'using default start_time {}', start_time)

    try:
        end_time = tz.localize(datetime.strptime(query['end_time'], '%Y-%m-%d %H:%M'))
    except (KeyError, ValueError):
        end_time = default['end_time']
        response.message(Severity.INFO, 'using default end_time {}', end_time)

    if start_time > end_time:
        response.message(Severity.INFO, 'swapping start_time and end_time')
        start_time, end_time = end_time, start_time

    try:
        birds = query['birds']
    except KeyError:
        response.message(Severity.ERROR, 'must select one or more birds to plan for')
        return Parameters(valid=False, response=response)

    return Parameters(
        True, grid, where, minimum_altitude, tz, start_time, end_time, birds, response
    )

class BirdplansUwsgi:
    '''Birdplans uwsgi application
    '''

    def __init__(self):
        '''Set application defaults.
        '''
        self.encoding = 'utf-8'
        self.tle = TleManager()

    def get_uwsgi_application(self):
        '''Return something uwsgi can call.
        '''

        return self.uwsgi_application

    def uwsgi_application(self, env, start_response):
        '''Route requests to the appropriate handler_ method.
        '''

        route_to = env['PATH_INFO'].split('/')[1]
        yield from getattr(self, 'handler_' + route_to, self.default_handler)(env, start_response)

    def handler_env(self, env, start_response):
        '''Diagnostic; return the uwsgi ENV.
        '''

        start_response('200 OK', [('Content-Type', 'text/plain; charset={}'.format(self.encoding))])
        yield bytes('\n'.join(['{}: {}'.format(k, v) for k, v in env.items()]), self.encoding)

    def handler_birds(self, env, start_response):
        '''Return available birds.
        '''
        start_response('200 OK', [('Content-Type', 'text/json; charset={}'.format(self.encoding))])
        yield bytes(json.dumps(list(self.tle.tle.keys())), self.encoding)

    def handler_tz(self, env, start_response):
        '''Return supported timezones
        '''
        start_response('200 OK', [('Content-Type', 'text/json; charset={}'.format(self.encoding))])
        yield bytes(json.dumps(pytz.all_timezones), self.encoding)

    def handler_one(self, env, start_response):
        '''Passes over a single location.
        '''

        t0 = default_timer()

        keys = parse.parse_qs(env['QUERY_STRING'])

        lat = float(keys['lat'][0])
        lng = float(keys['lng'][0])
        tz = pytz.timezone(keys['tz'][0])
        window_start = tz.localize(datetime.strptime(keys['window_start'][0], "%Y-%m-%dT%H:%M"))
        window_stop = window_start + timedelta(days=5)
        alt = int(keys.get('alt', [12])[0])
        birds = keys['bird']

        start_response('200 OK', [('Content-Type', 'text/json; charset={}'.format(self.encoding))])

        results = []

        # TODO separate function for this
        # JSON optimizations:
        # reduce timestamp transmission by offsetting from the smallest-observed value
        # truncate altaz floats to two decimal places
        # send altaz curve parameters instead of points
        for bird in birds:
            window_pass = pass_estimation_wrapper(
                self.tle[bird]
                , (lat, lng)
                , window_start
                , window_stop
                , alt
            )

            results.append({
                'lat': lat,
                'lng': lng,
                'bird': bird,
                'passes': [
                    {
                        **{
                            k: {
                                't': int(getattr(pass_, k).utc_datetime().timestamp() * 1000),
                                'az': window_pass.diff.at(getattr(pass_, k)).altaz()[1].degrees
                            }
                            for k in pass_._fields
                        },
                        **dict(
                            zip(
                                ('t', 'alt', 'az'),
                                list(zip(*list(map(
                                    lambda x: [ # time
                                        int(
                                            window_pass.ts.tai_jd(x)
                                            .utc_datetime()
                                            .timestamp() * 1000
                                        )
                                    ] + [ # alt, alz
                                        _.degrees
                                        for _ in
                                        window_pass.diff.at(
                                            window_pass.ts.tai_jd(x)
                                            ).altaz()[0:2]
                                    ]
                                    , np.linspace(pass_.AOS.tai, pass_.LOS.tai, 13)
                                ))))
                            )
                        )
                    }
                    for pass_ in window_pass.passes
                ]
            })

        yield bytes(
            json.dumps(
                {
                    'tz': {
                        'name': str(tz),
                        'changes': tzhelper.make_tzinfo(tz, window_start, window_stop)
                    },
                    'time': default_timer() - t0,
                    'data': results
                }
            )
            , self.encoding
        )

    def default_handler(self, env, start_response):
        '''Default handler, returns the main application.
        '''

        with open('static/index.html', 'r') as fin:
            start_response('200 OK', [('Content-Type', 'text/html; charset=' + self.encoding)])
            yield bytes(fin.read(), self.encoding) # TODO less sponge plz

    @staticmethod
    def decode_grid(grid):
        '''Decode a Maidenhead grid locator to (latitude, longitude).

        :param grid: Grid to decode
        :type grid: string

        :return: (latitude, longitude) floating point degrees tuple
        :rtype: (float, float)

        :raises ValueError: Grid locator contains a character where a digit is expected.
        :raises AssertionError: Grid locator character length is not 2, 4, 6, or 8
        '''

        return mh.toLoc(grid)

    def endpoint_passes_by_grid(self, **query):
        '''Fetch passes at a grid location. Keyword arguments may come from decoded query string.

        :Keyword Arguments
            * *grid* (``string``)
                Maidenhead grid locator for Earth surface reference point
            * *start_time* (``string``)
                Beginning of time window in which to estimate passes (%Y%m%d%H%M)
            * *end_time* (``string``)
                End of time window in which to estimate passes (%Y%m%d%H%M)
            * *minimum_altitude* (``float``)
                Minimum peak pass altitude
            * *tzname* (``string``)
                name of pytz timezone applying to start_time, end_time, and results
        '''
        try:
            lat, lng = self.decode_grid(query['grid'])
        except KeyError:
            pass

        return self.endpoint_passes_by_latlng(
            *mh.toLoc(query['grid'])
            , query['start_time']
            , query['stop_time']
            , query['minimum_altitude']
            , query['tzname']
        )

    def endpoint_passes_by_latlng(self, **query):
        '''Fetch passes at a latitude/longitude. Keyword arguments may come from decoded query
        string.

        :Keyword Arguments
            * *lat* (``float``)
                latitude of Earth surface reference point
            * *lng* (``float``)
                longitude of Earth surface reference point
            * *start_time* (``string``)
                Beginning of time window in which to estimate passes (%Y%m%d%H%M)
            * *end_time* (``string``)
                End of time window in which to estimate passes (%Y%m%d%H%M)
            * *minimum_altitude* (``float``)
                Minimum peak pass altitude
            * *tzname* (``string``)
                name of pytz timezone applying to start_time, end_time, and results
        '''

        return 0

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
        where = Topos(*mh.toLoc(grid))
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

def time_delta_minutes_seconds(timedelta):
    '''format a timedelta since python forgot
    '''
    seconds = timedelta.total_seconds()
    return '{}:{:02d}'.format(int(seconds / 60), int(seconds % 60))

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
            <th rowspan=2>Duration (mm:ss)
            <th colspan=3>Azimuth
            <th colspan=3>{}
            <th colspan=3>UTC
            <th colspan=2>TLE Epoch'''.format(results['tzname'])

    yield '<tr><th>AOS<th>TCA<th>LOS<th>AOS<th>TCA<th>LOS<th>AOS<th>TCA<th>LOS<th>Timestamp<th>Age'

    sorted_passes = sorted(make_pass_tuples(results['results']), key=lambda r: r[2].tai)

    formats = {
        'long_strftime': '%Y-%m-%d %H:%M %Z',
        'short_strftime': '%H:%M',
        'degrees': '{:.0f}\u00b0',
    }

    previous_pass_aos = None
    for _pass in sorted_passes:
        bird, pq, aos, tca, los = _pass
        yield '<tr>' + ''.join('<td>{}'.format(html.escape(_)) for _ in [
            bird
            , formats['degrees'].format(pq.altaz(tca)[0].degrees)
            , time_delta_minutes_seconds(los.astimezone(pytz.UTC) - aos.astimezone(pytz.UTC))
            , formats['degrees'].format(pq.altaz(aos)[1].degrees)
            , formats['degrees'].format(pq.altaz(tca)[1].degrees)
            , formats['degrees'].format(pq.altaz(los)[1].degrees)
            , aos.astimezone(results['tz']).strftime(formats['long_strftime'])
            , tca.astimezone(results['tz']).strftime(formats['short_strftime'])
            , los.astimezone(results['tz']).strftime(formats['short_strftime'])
            , aos.astimezone(pytz.UTC).strftime(formats['long_strftime'])
            , tca.astimezone(pytz.UTC).strftime(formats['short_strftime'])
            , los.astimezone(pytz.UTC).strftime(formats['short_strftime'])
            , pq.satellite.epoch.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            , str(
                pq.birdplan.timescale.utc(now).astimezone(pytz.UTC) -
                pq.satellite.epoch.astimezone(pytz.UTC)
            )
        ])
        previous_pass_aos = aos

    yield '</table>'

    yield '<p>Time to find passes: {}'.format(results['query_time'])

def simple_page(env, start_response, encoding):
    '''simple Web 1.0 page that works great in Links (but not Lynx, sorry, tables!)
    or otherwise without javascript/modern Web2.0 stuff
    '''

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
    endpoint_server = BirdplansUwsgi()
    application = endpoint_server.get_uwsgi_application()
except ImportError:
    # must be testing or something
    pass
