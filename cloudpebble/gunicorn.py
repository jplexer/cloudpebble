import multiprocessing
import os

worker_class = 'gevent'
workers = int(os.environ.get('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
timeout = 120


def post_fork(server, worker):
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
