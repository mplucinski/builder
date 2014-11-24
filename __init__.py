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

	def __init__(self, args, cwd=None, env=None, capture_stdout=False, capture_stderr=False):
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
			stdout=slave_stdout, stderr=slave_stderr)

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

class ConfigHelper:
	def __init__(self, config):
		self.config = config

	def execute(self, *args, **kwargs):
		inherit_env = kwargs.pop('inherit_env', False)
		env = kwargs.pop('env', None)

		_env = copy.deepcopy(os.environ) if inherit_env else dict()
		_env.update(self.config.get('env', {}))
		if env is not None:
			_env.update(env)

		kwargs['env'] = _env
		return Process(*args, **kwargs).communicate()

	def c_cxx_detect_compiler(self, lang):
		return self.detect_compiler(self.config['{}.compiler'.format(lang)])

	def detect_compiler(self, compiler):
		(out, err) = self.execute([compiler, '-v'], capture_stdout=True, capture_stderr=True)
		out = out.decode('utf-8').splitlines()
		err = err.decode('utf-8').splitlines()
		if len(err) > 0:
			m = re.match(r'clang version ([0-9\.]+) .*', err[0])
			if m:
				return ('clang', m.group(1))
		raise Exception('Unknown compiler: {}'.format(compiler))

	def _unknown_value(self, option):
		raise Exception('Unknown value for configuration option {}: {}'.format(option, self.config.get(option)))

	def c_cxx_warning_flags(self, compiler, lang):
		flags = []
		if compiler[0] == 'clang':
			errors = self.config['{}.warnings.errors'.format(lang)]
			if errors:
				flags.append('-Werror')

			flags.append('-Weverything')

			if not self.config['{}.warnings.enable.normal'.format(lang)]:
				pass

			if self.config['{}.warnings.enable.extensions'.format(lang)]:
				if not errors:
					flags.append('-pedantic')
				else:
					flags.append('-pedantic-errors')

			if not self.config['{}.warnings.enable.compatibility'.format(lang)]:
				if lang == 'c':
					flags += ['-Wno-c99-compat', '-Wno-c99-compat-pedantic']
				elif lang == 'cxx':
					flags += ['-Wno-c++98-compat', '-Wno-c++98-compat-pedantic']
				else:
					raise Exception('Unknown language: {}'.format(lang))

			if not self.config['{}.warnings.enable.performance'.format(lang)]:
				pass

			if not self.config['{}.warnings.enable.performance_platform'.format(lang)]:
				flags += ['-Wno-padded', '-Wno-packed']

			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def c_cxx_compilation_flags(self, lang):
		flags = []
		compiler = self.c_cxx_detect_compiler(lang)
		if compiler[0] == 'clang':
			if self.config.has('{}.standard'.format(lang)):
				flags.append('-std={}'.format(self.config['{}.standard'.format(lang)].lower()))
			flags += self.c_cxx_warning_flags(compiler, lang)
			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def c_compilation_flags(self):
		return self.c_cxx_compilation_flags('c')

	def cxx_compilation_flags(self):
		compiler = self.c_cxx_detect_compiler('cxx')
		flags = self.c_cxx_compilation_flags('cxx')
		if compiler[0] == 'clang':
			if self.config.has('cxx.standard_library'):
				flags.append('-stdlib={}'.format(self.config['cxx.standard_library'].lower()))
			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def resolve_value(self, value):
		if isinstance(value, types.FunctionType):
			value = value(self.config)
		return value

class Config:
	def __init__(self, create_helper=True, config={}, parent=None):
		self.helper = ConfigHelper(self) if create_helper else None
		self.config = copy.deepcopy(config)
		self.parent = parent

	@staticmethod
	def _merged_dicts(d1, d2):
		do = dict()
		for i in d1:
			if not i in d2:
				do[i] = d1[i]
			else:
				o1 = d1[i]
				o2 = d2[i]
				if isinstance(o1, dict) and isinstance(o2, dict):
					do[i] = Config._merged_dicts(o1, o2)
				else:
					do[i] = o2
		for i in d2:
			if not i in d1:
				do[i] = d2[i]
		return do

	def merged(self, other):
		config = Config._merged_dicts(copy.deepcopy(self.config), copy.deepcopy(other))
		return Config(config=config, parent=self)

	def has(self, name):
		try:
			self[name]
			return True
		except KeyError:
			return False

	def __getitem__(self, name):
		return self.get(name, raise_key_error=True)

	def get(self, name, default=None, raise_key_error=False):
		_name = name.split('.')
		current = self.config
		while len(_name) > 0:
			if _name[0] in current:
				current = current[_name[0]]
				_name = _name[1:]
			else:
				if raise_key_error:
					raise KeyError('Option {} not found'.format(name))
				return default
		return self.helper.resolve_value(current)

	def set(self, name, value, parent_scope=False):
		_name = name.split('.')
		current = self.config
		while len(_name) > 0:
			if _name[0] in current:
				pass
			elif len(_name) == 1: #leaf
				current[_name[0]] = value
			else:
				current[_name[0]] = dict()
			current = current[_name[0]]
			_name = _name[1:]

		self.config[name] = value
		if parent_scope:
			self.parent.set(name, value)

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

class Builder:
	def __init__(self, source_dir, target_dir, **kwargs):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('-v', '--verbose', action='store_true',
				help='Verbose output')
		args = parser.parse_args()

		self.source_dir = os.path.normpath(source_dir)
		self.target_dir = os.path.normpath(target_dir)
		self.config = Config(config=_default_config).merged(kwargs)
		self.config.set('verbose', args.verbose)

		self.platforms = []
		self.targets = []
		_init_logger(logging.DEBUG if self.config['verbose'] else logging.INFO)

	def __call__(self, args=sys.argv):
		logging.info('Building...')
		for platform in self.platforms:
			config = copy.deepcopy(self.config)
			config.set('platform', platform)
			for target in self.targets:
				self.build(target, config)

		logging.info('Building done.')

	def build(self, target, config):
		logging.info('Building {} for {}...'.format(target.name, config['platform'].name))

		config = copy.deepcopy(config)
		config.set('directory.root', os.path.join(self.target_dir, target.code, config['platform'].code))
		logging.debug('Root build directory: {}'.format(config['directory.root']))

		target._build(config)

		logging.info('Building {} for {} done.'.format(target.name, config['platform'].name))

import builder.platforms
import builder.targets
