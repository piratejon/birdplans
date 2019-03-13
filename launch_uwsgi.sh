#!/bin/bash

tip=`git rev-parse HEAD 2>/dev/null || echo none`
diff=`git diff --quiet && echo 0 || echo 1`
uwsgi --http :9090 --wsgi-file birdplans/uwsgi.py --master --processes 8 --safe-pidfile ./pidfile.txt --check-static static --add-header "Tip: ${tip}.${diff}" --add-header 'Cache-Control: public, max-age=315360000' --load-file-in-cache ./static/index.html

