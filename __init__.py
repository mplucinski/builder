#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import fcntl
import logging
import os
import os.path
import pty
import re
import subprocess
import sys
import threading
import time
import types

def directory_of_file(file_name):
	return os.path.split(os.path.realpath(file_name))[0]
import copy

def _init_logger(level):
	class Formatter(logging.Formatter):
		def format(self, record):
			prefix = {
				logging.DEBUG: '--',
				logging.INFO: '-',
				logging.WARNING: '>',
				logging.ERROR: '!',
				logging.CRITICAL: '!!!'
			}[record.levelno]
			return '{} {}'.format(prefix, record.msg)
	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(Formatter())
	logging.getLogger().setLevel(level)
	logging.getLogger().addHandler(handler)

class Compiler:
	pass

class CompilerClang:
	pass

class Process:
	@staticmethod
	def set_nonblocking(fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFL)
		flags = flags | os.O_NONBLOCK
		fcntl.fcntl(fd, fcntl.F_SETFL, flags)

	def __init__(self, args, cwd=None, env=None, stdin=False, capture_stdout=False, capture_stderr=False):
		logging.debug('Running {}...'.format(args[0]))
		logging.debug('Parameters: {}'.format(args))
		logging.debug('Working directory: {}'.format(cwd))
		logging.debug('Environment: {}'.format(env))

		self.args = args

		self.buffer_stdout = bytearray()
		self.buffer_stderr = bytearray()

		master_stdout, slave_stdout = pty.openpty()
		master_stderr, slave_stderr = pty.openpty()

		Process.set_nonblocking(master_stdout)
		Process.set_nonblocking(master_stderr)

		self.process = subprocess.Popen(args, bufsize=0, cwd=cwd, env=env,
			stdin=stdin, stdout=slave_stdout, stderr=slave_stderr)

		self._reader_stdout = self.reader(master_stdout, capture_stdout,
									self.buffer_stdout, sys.stdout.buffer)
		self._reader_stderr = self.reader(master_stderr, capture_stderr,
									self.buffer_stderr, sys.stderr.buffer)

	def reader(self, *args):
		stop = threading.Event()
		done = threading.Event()
		thread = threading.Thread(target=self._reader, args=list(args)+[stop, done])
		thread.start()
		return (stop, done)

	def reader_join(self, stop, done):
		stop.set()
		done.wait()

	def communicate(self):
		result = self.process.wait()

		time.sleep(0.1)

		self.reader_join(*self._reader_stdout)
		self.reader_join(*self._reader_stderr)

		logging.debug('Running {} done.'.format(self.args[0]))

		if result != 0:
			raise subprocess.CalledProcessError(result, self.args)

		return (self.buffer_stdout, self.buffer_stderr)

	def _reader(self, fd, capture, buffer, pass_to, stop, done):
		while not stop.is_set():
			try:
				b = os.read(fd, 4096 if capture else 1)
				if capture:
					buffer.extend(b)
				else:
					pass_to.write(b)
					if b'\n' in b:
						pass_to.flush()
			except BlockingIOError:
				pass

		pass_to.flush()

		done.set()

class Profile:
	def __init__(self, name, config=dict()):
		self.name = name
		self.config = config

	def __str__(self):
		return self.name

_default_c_cxx_warnings=dict(
	errors=False, #treat warnings as errors
	enable=dict(
		normal=True, # "normal" warnings, like 'signedness' incompatibility
		extensions=False, # warn on language extensions
		compatibility=False, # warn on incompatibilities with older standards, like C99 or C++03
		performance=True, # warn on general performance issues
		performance_platform=False # warn on platform-specific performance issues
	)
)
_default_config=dict(
	verbose=False,
	directory=dict(
		archive=lambda config: os.path.join(config['directory.root'], 'archives'),
		binary= lambda config: os.path.join(config['directory.root'], 'bin'     ),
		include=lambda config: os.path.join(config['directory.root'], 'include' ),
		library=lambda config: os.path.join(config['directory.root'], 'lib'     ),
		share=  lambda config: os.path.join(config['directory.root'], 'share'   ),
		source= lambda config: os.path.join(config['directory.root'], 'src'     )
	),
	c=dict(
		warnings=_default_c_cxx_warnings
	),
	cxx=dict(
		warnings=_default_c_cxx_warnings
	)
)

_default_profile=Profile(
	name='default'
)

class Builder:
	def __init__(self, **kwargs):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('-v', '--verbose', action='store_true',
				help='Verbose output')
		parser.add_argument('-c', '--config', action='append',
				help='Override configuration value (in form name=value)')
		parser.add_argument('-p', '--profile', action='store', default='default',
				help='Select build profile')
		args = parser.parse_args()

		self.config = Config(config=_default_config).merged(kwargs)

		if args.config:
			for i in args.config:
				idx = i.find('=')
				self.config[i[:idx]] = i[idx+1:]

		self.config['directory.source']
		self.config['directory.target']
		self.config['verbose'] = args.verbose
		self.config['profile'] = args.profile

		self.platforms = []
		self.profiles = [_default_profile]
		self.targets = []
		_init_logger(logging.DEBUG if self.config['verbose'] else logging.INFO)

	def __call__(self, args=sys.argv):
		self.config['profile'] = next(i for i in self.profiles if i.name == self.config['profile'])

		logging.info('Building (profile {})...'.format(self.config['profile']))
		for platform in self.platforms:
			config = self.config.merged(self.config['profile'].config)
			print(repr(config))
			config['platform'] = platform
			for target in self.targets:
				self.build(target, config)

		logging.info('Building done.')

	def build(self, target, config):
		logging.info('Building {} for {}...'.format(target.name, config['platform'].name))

		config = copy.deepcopy(config)
		config['directory.root'] = os.path.join(config['directory.target'], target.code, config['platform'].code)
		logging.debug('Root build directory: {}'.format(config['directory.root']))

		target._build(config)

		logging.info('Building {} for {} done.'.format(target.name, config['platform'].name))

import builder.platforms
import builder.targets
