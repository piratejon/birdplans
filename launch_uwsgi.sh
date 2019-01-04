#!/bin/bash

tip=`git rev-parse HEAD 2>/dev/null || echo none`
uwsgi --http :9090 --wsgi-file birdplans/uwsgi.py --master --processes 8 --pyargv $tip --safe-pidfile ./pidfile.txt --check-static static
