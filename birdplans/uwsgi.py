#!`/usr/bin/env python3`

'''
uwsgi.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

uwsgi application wrapper/api endpoint
'''

import html
import sys

from datetime import datetime, timezone
from collections import namedtuple
from tzwhere import tzwhere
from urllib import parse
from enum import Enum

import pytz

import maidenhead as mh

from birdplans.tlemanager import TleManager

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
        self.messages.append(Message(format_string.format(args)))

    def filtered_messages(self, severity=None):
        '''Return a filtered list of messages meeting the configured severity criteria.
        '''
        severity = self.minimum_severity if severity is None else severity
        return [_ for _ in self.messages if _.severity >= severity]

def birdplan_query_endpoint(query, default):
    '''Given a query string, estimate passes and return JSON results.

    :param query: dict representing parsed query string with list values
    :param default: dict of parameter default values
    :param response: QueryResponse object containing results and status to caller
    '''

    ###
    ### loglevel
    ###
    try:
        response = ApiResponse(Severity[query['loglevel'][0]])
    except KeyError:
        try:
            response = ApiResponse(Severity(int(query['loglevel'][0])))
        except (KeyError, ValueError):
            response = ApiResponse()

    ###
    ### window_days
    ###
    try:
        window_days = int(query['window_days'][0])
        response.message(Severity.VERBOSE, 'read {} window_days', window_days)
    except KeyError:
        window_days = default['window_days']
        response.message(Severity.INFO, 'defaulting to {} window_days', window_days)
    except ValueError as ex:
        window_days = default['window_days']
        response.message(
            Severity.WARNING
            , 'invalid window_days {}, defaulting to {}'
            , (query['window_days'][0], window_days)
        )

    t0 = datetime.now(timezone.utc)
    response.message(Severity.VERBOSE, 'start time', (t0, ))

    ###
    ### grid
    ###
    try:
        grid = query['grid'][0]
    except KeyError:
        response.message(Severity.ERROR, 'no grid specified')
        return response

    ###
    ### latlng
    ###
    try:
        latlng = mh.toLoc(grid)
    except (ValueError, AssertionError):
        response.message(Severity.ERROR, 'unable to decode grid {}', grid)
        return response
    response.message(Severity.VERBOSE, 'decoded grid {} as {}}', grid, latlng)

    ###
    ### tzname
    ###
    try:
        grid = query['tz'][0]
    except KeyError:
        try:
            tzname = tzwhere.tzNameAt(*latlng)
            response.message(Severity.INFO, 'looked up tz {} for {}', tzname, latlng)
        except KeyError:
            tzname = defaults['tzname']
            response.message(
                Severity.WARNING
                , 'unable to find tz for {}, defaulting to {}'
                , latlng, tzname
            )

    ###
    ### tz
    ###
    try:
        tz = pytz.timezone(tzname)
        response.message(Severity.VERBOSE, 'selected timezone {}', tz)
    except UnknownTimeZoneError:
        tz = pytz.timezone(defaults['tz'])
        response.message(Severity.WARNING, 'unknown timezone {}, defaulting to {}', tzname, tz)

    ###
    ### minimum_altitude
    ###
    try:
        minimum_altitude = query['minimum_altitude'][0]
        response.message(Severity.VERBOSE, 'selected minimum_altitude {}', minimum_altitude)
    except KeyError:
        minimum_altitude = defaults['minimum_altitude']
        response.message(Severity.VERBOSE, 'defaulting to minimum_altitude {}', minimum_altitude)

    ###
    ### birds
    ###
    try:
        birds = set(query['bird'])
    except KeyError:
        response.message(Severity.ERROR, 'must specify birds')
        return response

    missing_birds = birds - set(birdplan.tle.keys())
    if missing_birds:
        response.message(Severity.WARNING, 'birds not found: {}', ','.join(missing_birds))

    birds = birds & set(birdplan.tle.keys())
    if not birds:
        response.message(Severity.ERROR, 'no available birds specified')
        return response

    t1 = datetime.now(timezone.utc)
    response.message('start time', Severity.VERBOSE, (t1, ))

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

def application(env, start_response):
    '''uWSGI handler.
    '''
    encoding = 'utf-8'

    if True: # simple page
        yield from simple_page(env, start_response, encoding)
try:
    import uwsgi
    # this is meant to be shared across uWSGI application() invocations
    #tzwhere = tzwhere.tzwhere()
    #global_birdplan = BirdPlan(TleManager())
except ImportError:
    # will any tests require tzwhere?
    pass
