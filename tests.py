#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import sys
import unittest

class TestCase(unittest.TestCase):
	_config_defaults = {
		'always_outdated': False,
		'process.echo.stdout': False,
		'process.echo.stderr': False
	}

	def mock_target(self, cls, *args, **kwargs):
		for k, v in self._config_defaults.items():
			if not k in kwargs:
				kwargs[k] = v

		target = cls(*args, **kwargs)
		target.defaults = self._config_defaults
		return target

if __name__ == '__main__':
	directory = pathlib.Path(__file__).parent
	suite = unittest.defaultTestLoader.discover(start_dir=str(directory), pattern='*.py', top_level_dir=str(directory/'..'))
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)