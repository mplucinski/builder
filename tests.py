#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import unittest

if __name__ == '__main__':
	suite = unittest.defaultTestLoader.discover(start_dir='.', pattern='*.py', top_level_dir='..')
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)