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

import builder.config
import builder.platforms
import builder.targets

def directory_of_file(file_name):
	return os.path.split(os.path.realpath(file_name))[0]
import copy

def _init_logger(verbosity):
	def verbosity_to_level(verbosity):
		if verbosity == 0: return logging.WARNING
		elif verbosity == 1: return logging.INFO
		elif verbosity == 2: return logging.DEBUG
		elif verbosity >= 3:
			return logging.DEBUG - verbosity + 2

	class Formatter(logging.Formatter):
		def format(self, record):
			def level_fmt(level):
				if   level == logging.CRITICAL: return '!!! {msg}'
				elif level == logging.ERROR:    return '! {msg}'
				elif level == logging.WARNING:  return '> {msg}'
				elif level == logging.INFO:     return '- {msg}'
				elif level <= logging.DEBUG:    return '--' + '-'*(logging.DEBUG - level) + ' {msg}'
			return level_fmt(record.levelno).format(msg=record.msg)
	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(Formatter())
	logging.getLogger().setLevel(verbosity_to_level(verbosity))
	logging.getLogger().addHandler(handler)

	logging.debug('Logger configured')

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
	def __init__(self, name, config={}):
		self.name = name
		self.config = config

	def __str__(self):
		return self.name

_default_c_cxx_warnings={
	'errors': False, #treat warnings as errors
	'enable': {
		'normal': True, # "normal" warnings, like 'signedness' incompatibility
		'extensions': False, # warn on language extensions
		'compatibility': False, # warn on incompatibilities with older standards, like C99 or C++03
		'performance': True, # warn on general performance issues
		'performance_platform': False # warn on platform-specific performance issues
	}
}
_default_config={
	'verbose': False,
	'directory': {
		'archive': lambda config: os.path.join(config['directory.root'](), 'archives'),
		'binary':  lambda config: os.path.join(config['directory.root'](), 'bin'     ),
		'include': lambda config: os.path.join(config['directory.root'](), 'include' ),
		'library': lambda config: os.path.join(config['directory.root'](), 'lib'     ),
		'share':   lambda config: os.path.join(config['directory.root'](), 'share'   ),
		'source':  lambda config: os.path.join(config['directory.root'](), 'src'     )
	},
	'language': {
		'c': {
			'warnings': _default_c_cxx_warnings
		},
		'c++': {
			'warnings': _default_c_cxx_warnings
		}
	},
	'environment': {}
}

class Builder:
	def arguments_parser(self):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('-v', '--verbose', action='count',
				help='Verbose output')
		parser.add_argument('-c', '--config', action='append',
				help='Override configuration value (in form name=value)')
		parser.add_argument('-p', '--profile', action='store', default='default',
				help='Select build profile')
		parser.add_argument('target', nargs='*', type=str, metavar='TARGET',
				help='Target(s) to build (all, if nothing passed)')
		return parser

	def __init__(self, config):
		self.config = config
		self.profiles = [
			Profile(name='default')
		]
		self.platforms = []
		self.targets = []

	def __call__(self, args=None):
		parser = self.arguments_parser()
		args = parser.parse_args(args)

		config = builder.config.Config('default', config=_default_config)
		config = config.merged('main', self.config)

		profile = next(i for i in self.profiles if i.name == args.profile)
		config = config.merged('profile', profile.config)

		config_overrides = {}
		if args.config:
			for i in args.config:
				idx = i.find('=')
				config_overrides[i[:idx]] = i[idx+1:]

		config_overrides['verbose'] = args.verbose

		config = config.merged('override', config_overrides)

		_init_logger(config['verbose']())

		logging.log(logging.DEBUG-2, 'Arguments: {}'.format(args))
		logging.log(logging.DEBUG-3, 'Config: {}'.format(config))

		targets = self.targets
		if args.target:
			targets = []
			for i in args.target:
				try:
					targets.append(next(j for j in self.targets if j.name == i))
				except StopIteration as e:
					raise Exception('Global target "{}" not found'.format(i)) from e

		logging.info('Building (profile {})...'.format(profile))
		for platform in self.platforms:
			platform_config = config.merged('platform', {'platform': platform})
			for target in targets:
				self.build(target, platform_config)

		logging.info('Building done.')

	def build(self, target, config):
		logging.info('Building {} for {}...'.format(target.name, config['platform']().name))

		config = config.merged('target', {
			'directory.root': os.path.join(config['directory.target'](), target.code, config['platform']().code)
		})
		logging.log(logging.DEBUG-2, 'Specific build configuration: {}'.format(config))
		logging.debug('Root build directory: {}'.format(config['directory.root']()))

		target._build(config)

		logging.info('Building {} for {} done.'.format(target.name, config['platform'].name))
