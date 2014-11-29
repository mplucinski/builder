#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import sys
import unittest

from . import config

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
				if level == logging.CRITICAL: return '!!! {msg}'
				elif level == logging.ERROR: return '! {msg}'
				elif level == logging.WARNING: return '> {msg}'
				elif level == logging.INFO: return '- {msg}'
				elif level <= logging.DEBUG: return '--' + '-'*(logging.DEBUG - level) + ' {msg}'
			return level_fmt(record.levelno).format(msg=record.msg)

	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(Formatter())
	logging.getLogger().setLevel(verbosity_to_level(verbosity))
	logging.getLogger().addHandler(handler)
	logging.debug('Logger configured')

class Target:
	def __init__(self, name):
		self.name = name
		self.dependencies = set()

	def _build(self):
		self.build()

class Build:
	def _arguments_parser(self):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('-v', '--verbose', action='count', default=0,
				help='Verbose output')
		parser.add_argument('target', nargs='*', type=str, metavar='TARGET',
				help='Target(s) to build (all, if nothing passed)')
		return parser

	def __init__(self):
		self.targets = set()

	def __call__(self, args=None):
		parser = self._arguments_parser()
		args = parser.parse_args(args)

		_init_logger(args.verbose)

		targets = self.targets
		if args.target:
			targets = []
			for i in args.target:
				try:
					targets.append(next(j for j in self.targets if j.name == i))
				except StopIteration as e:
					raise Exception('Global target "{}" not found'.format(i)) from e

		for target in targets:
			target._build()


class MockTarget(Target):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.build_called = False

	def build(self):
		self.build_called = True

class TestBuilder(unittest.TestCase):
	def build(self, targets={'foo', 'bar', 'baz', 'qux'}, dependencies={'foo': ['bar', 'baz'], 'baz': ['qux']}, args=None):
		build = Build()
		targets = { i: MockTarget(i) for i in targets }
		for name, target in targets.items():
			target.dependencies = { targets[dep] for dep in dependencies[name] } if name in dependencies else {}
		targets = set(targets.values())
		build.targets |= targets
		build(args=args)
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
	suite = unittest.defaultTestLoader.discover(start_dir='.', pattern='*.py')
	runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
	runner.run(suite)