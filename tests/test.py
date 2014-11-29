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
	def build(self, targets={'foo', 'bar', 'baz', 'qux'}, dependencies={'foo': ['bar', 'baz'], 'baz': ['qux']}, args=None):
		build = builder.Build()
		targets = { i: MockTarget(i) for i in targets }
		for name, target in targets.items():
			target.dependencies = { targets[dep] for dep in dependencies[name] } if name in dependencies else {}
		targets = set(targets.values())
		build.targets |= targets
		build(args=['-vv'])
		return build, targets

	def test_single_target(self):
		build, targets = self.build(targets={'foo'}, dependencies={})
		targets = iter(targets)
		self.assertEqual(next(targets).build_called, True)

	def test_dependencies(self):
		build, targets = self.build(targets={'foo', 'bar', 'baz', 'qux'},
			dependencies={'foo': ['bar', 'baz'], 'baz': ['qux']}
		)
		i_target = iter(targets)
		self.assertEqual(next(i_target).build_called, True)
		self.assertEqual(next(i_target).build_called, True)
		self.assertEqual(next(i_target).build_called, True)
		self.assertEqual(next(i_target).build_called, True)

if __name__ == '__main__':
	unittest.main()
