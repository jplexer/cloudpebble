#!/bin/sh
sleep 1

# Use the system Python 3.11 (not uv's isolated pebble-tool env)
PYTHON=/usr/local/bin/python

if [ -n "$MODDABLE_EXAMPLES_ROOT" ] && [ -d "$MODDABLE_EXAMPLES_ROOT/.git" ]; then
	git -C "$MODDABLE_EXAMPLES_ROOT" fetch --depth 1 origin "${MODDABLE_EXAMPLES_BRANCH:-main}" >/dev/null 2>&1 || true
	git -C "$MODDABLE_EXAMPLES_ROOT" reset --hard "origin/${MODDABLE_EXAMPLES_BRANCH:-main}" >/dev/null 2>&1 || true
fi

if [ ! -z "$RUN_WEB" ]; then
	if [ ! -z "$RUN_MIGRATE" ]; then
		echo "Performing database migration."
		$PYTHON manage.py migrate --noinput
	fi
	$PYTHON manage.py collectstatic --noinput 2>/dev/null || true
	if [ ! -z "$DEBUG" ]; then
		$PYTHON manage.py runserver 0.0.0.0:$PORT
	else
		gunicorn -c gunicorn.py cloudpebble.wsgi --bind 0.0.0.0:$PORT
	fi
elif [ ! -z "$RUN_CELERY" ]; then
	sleep 2
	C_FORCE_ROOT=true /usr/local/bin/celery -A cloudpebble worker --loglevel=info
else
	echo "Doing nothing!"
	exit 1
fi
