#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import sys
import unittest

sys.path.append(str((pathlib.Path(__file__).parent / '..' / '..').resolve()))

import builder

class MockTarget(builder.Target):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.build_called = False

	def build(self):
		self.build_called = True

class TestBuilder(unittest.TestCase):
	def build(self, targets=set()):
		build = builder.Build()
		targets = { MockTarget(i) for i in targets }
		build.targets |= targets
		build()
		return build, targets

	def test_single_target(self):
		build, targets = self.build(targets={'foo'})
		targets = iter(targets)
		self.assertEqual(next(targets).build_called, True)

if __name__ == '__main__':
	unittest.main()
