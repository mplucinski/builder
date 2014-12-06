#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
import logging
import pathlib
import sys
import tempfile
import unittest

def _log(level, msg):
	logging.log(level, msg)

def _fn_log(level):
	def wrapper1(fn):
		def wrapper2(*args, **kwargs):
			_log(level, '{}({}, {})'.format(fn.__qualname__, ', '.join(map(repr, args)),
				', '.join(['{}={}'.format(repr(k), repr(v)) for k, v in kwargs.items()]) ))
			r = fn(*args, **kwargs)
			_log(level, '{}(...) = {}'.format(fn.__qualname__, repr(r)))
			return r
		return wrapper2
	return wrapper1

class SkipType:
	pass

Skip = SkipType

class TestCase(unittest.TestCase):
	_config_defaults = {
		'always_outdated': False,
		'language.c.compiler': 'C_COMPILER',
		'language.c.flags': 'C_FLAGS',
		'language.c++.compiler': 'C++_COMPILER',
		'language.c++.flags': 'C++_FLAGS',
		'process.echo.stdout': False,
		'process.echo.stderr': False
	}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.stamps_dir = tempfile.TemporaryDirectory()
		self._config_defaults = copy.deepcopy(self._config_defaults)
		self._config_defaults['directory.stamps'] = self.stamps_dir.name

	def mock_target(self, cls, *args, **kwargs):
		for k, v in self._config_defaults.items():
			if k in kwargs:
				if kwargs[k] is Skip:
					del kwargs[k]
			else:
				kwargs[k] = v

		target = cls(*args, **kwargs)
		target.defaults = self._config_defaults
		return target

	def mock_process(self, stdout, stderr):
		class MockProcess:
			def __init__(self, args, **kwargs):
				pass

			def communicate(self):
				return stdout, stderr

		return MockProcess

if __name__ == '__main__':
	directory = pathlib.Path(__file__).parent
	suite = unittest.defaultTestLoader.discover(start_dir=str(directory), pattern='*.py', top_level_dir=str(directory/'..'))
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)