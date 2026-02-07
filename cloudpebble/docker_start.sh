#!/bin/sh
sleep 1

# Use the system Python 3.11 (not uv's isolated pebble-tool env)
PYTHON=/usr/local/bin/python

if [ ! -z "$RUN_WEB" ]; then
	# Make sure the database is up to date.
	echo "Performing database migration."
	$PYTHON manage.py migrate --noinput
	$PYTHON manage.py migrate

	$PYTHON manage.py runserver 0.0.0.0:$PORT
elif [ ! -z "$RUN_CELERY" ]; then
	sleep 2
	C_FORCE_ROOT=true /usr/local/bin/celery -A cloudpebble worker --loglevel=info
else
	echo "Doing nothing!"
	exit 1
fi
