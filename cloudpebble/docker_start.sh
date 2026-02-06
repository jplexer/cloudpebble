#!/bin/sh
sleep 1
if [ ! -z "$RUN_WEB" ]; then
	# Make sure the database is up to date.
	echo "Performing database migration."
	python manage.py migrate --noinput
	python manage.py migrate

	python manage.py runserver 0.0.0.0:$PORT
elif [ ! -z "$RUN_CELERY" ]; then
	sleep 2
	C_FORCE_ROOT=true celery -A cloudpebble worker --loglevel=info
else
	echo "Doing nothing!"
	exit 1
fi
