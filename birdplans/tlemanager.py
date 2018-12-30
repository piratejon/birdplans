#!/usr/bin/env python3

'''
tlemanager.py
2018-11-19
jonathanwesleystone+KI5BEX@gmail.com

Load and keep updated the local TLE database.
'''

import json

from datetime import datetime, timezone

import requests

from skyfield.functions import BytesIO
from skyfield.iokit import parse_tle

class TleManager:
    '''Keep the TLE files updated.
    '''

    def __init__(self, tlesrcfile=None, tledbcurrent=None, tledbhistory=None):
        '''load up a birdlist annotated with TLE sources

        :param tlesrcfile: JSON file linking the birds to their TLEs
        :param tledb: JSON file containing the downloaded TLE logs and history
        '''

        self.tlesrcfile = 'data/tle/choice_birds.json' if tlesrcfile is None else tlesrcfile
        self.tledbcurrent = 'tledbcurrent.json' if tledbcurrent is None else tledbcurrent
        self.tledbhistory = 'tledbhistory.json' if tledbhistory is None else tledbhistory

        with open(self.tlesrcfile, 'r') as fin:
            self.tlesrcs = json.load(fin)

        self.tle = self.load()
        # this has the tle with our aliases
        self.tlestring = '\n'.join([key + '\n' + value for key, value in self.tle.items()])
        self.bird = self.parse()

    def parse(self):
        '''Parse the loaded tle data using SkyField API.
        '''
        tle = {}
        for names, sat in parse_tle(BytesIO(bytes(self.tlestring, 'ascii'))):
            tle[sat.model.satnum] = sat
            for name in names:
                tle[name] = sat

        return tle

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
                            bird_tles[birdname] = ((birdname + (' ' * 24))[:24]) + \
                                '\n' + next(lineiter) + '\n' + next(lineiter)
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

            now = datetime.now(timezone.utc).astimezone().isoformat()

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

    def __getitem__(self, bird):
        '''Bird fetcher -- return SkyField Satellite object parsed from the TLE identified by bird.
        '''
        return self.bird[bird]

class TestTleManager(TleManager):
    '''Test wrapper for TleManager.
    '''

    def __init__(self):
        '''Call super with test arguments for convenience.
        '''
        super().__init__(None, 'data/test/tledbcurrent.json', 'data/test/tledbhistory.json')
