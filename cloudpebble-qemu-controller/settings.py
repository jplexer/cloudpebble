__author__ = 'katharine'

from os import environ as env
import multiprocessing

LAUNCH_AUTH_HEADER = env.get('LAUNCH_AUTH_HEADER', 'secret')
EMULATOR_LIMIT = int(env.get('EMULATOR_FIXED_LIMIT', multiprocessing.cpu_count() * 12))
QEMU_DIR = env['QEMU_DIR']
QEMU_BIN = env.get('QEMU_BIN', 'qemu-system-arm')

# The expected layout of this directory is
# root/<platform>/qemu/qemu_micro_flash.bin + qemu_spi_flash.bin[.bz2]
# Populated by pebble-tool SDK install.
QEMU_IMAGE_ROOT = env['QEMU_IMAGE_ROOT']

SSL_ROOT = env.get('SSL_ROOT', None)

PORT = int(env.get('QCON_PORT', 5001))
HOST = env.get('QCON_HOST', '0.0.0.0')

RUN_AS_USER = env.get('RUN_AS_USER', None)

DEBUG = 'DEBUG' in env
