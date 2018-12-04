#!/bin/bash

while true; do
	python update_tles.py
	echo updated, reloading ...
	kill -HUP `cat pidfile.txt`
	echo sleeping until next update ...
	sleep 43200
done
