#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import sys
import unittest

if __name__ == '__main__':
	directory = pathlib.Path(__file__).parent
	suite = unittest.defaultTestLoader.discover(start_dir=str(directory), pattern='*.py', top_level_dir=str(directory/'..'))
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)