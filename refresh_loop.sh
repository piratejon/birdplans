#!/bin/bash

while true; do
	date
	echo updating ...
	python update_tles.py
	echo updated, reloading ...
	kill -HUP `cat pidfile.txt`
	echo sleeping until next update ...
	sleep 21600
done
