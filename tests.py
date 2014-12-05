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
	def wrapper(fn):
		def wrapper(*args, **kwargs):
			_log(level, '{}({}, {})'.format(fn.__qualname__, ', '.join(map(repr, args)),
				', '.join(['{}={}'.format(repr(k), repr(v)) for k, v in kwargs.items()]) ))
			r = fn(*args, **kwargs)
			_log(level, '{} = {}'.format(fn.__qualname__, repr(r)))
			return r
		return wrapper
	return wrapper

class SkipType:
	pass

Skip = SkipType

class TestCase(unittest.TestCase):
	_config_defaults = {
		'always_outdated': False,
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

if __name__ == '__main__':
	directory = pathlib.Path(__file__).parent
	suite = unittest.defaultTestLoader.discover(start_dir=str(directory), pattern='*.py', top_level_dir=str(directory/'..'))
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)