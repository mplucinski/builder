#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import copy
import logging
import pathlib
import sys
import unittest

from .base import Profile
from .base import Scope
from .base import Target
from .config import Config
from .tests import Skip
from .tests import TestCase
from . import targets

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
	for i in copy.copy(logging.getLogger().handlers):
		logging.getLogger().removeHandler(i)
	logging.getLogger().addHandler(handler)
	logging.debug('Logger configured')

class Build:
	_default_config = {
		'always_outdated': False,
		'directory': {
			'binaries': lambda config: str(pathlib.Path(config['directory.root'])/'bin'),
			'packages': lambda config: str(pathlib.Path(config['directory.root'])/'packages'),
			'source':   lambda config: str(pathlib.Path(config['directory.root'])/'src'),
			'stamps':   lambda config: str(pathlib.Path(config['directory.root'])/'stamps')
		},
		'process': {
			'echo': {
				'stdout': False,
				'stderr': False
			}
		}
	}

	def _arguments_parser(self):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('-v', '--verbose', action='count', default=0,
				help='Verbose output')
		parser.add_argument('-p', '--profile', action='store', default='default',
				help='Select build profile')
		parser.add_argument('target', nargs='*', type=str, metavar='TARGET',
				help='Target(s) to build (all, if nothing passed)')
		return parser

	def __init__(self, config=None):
		self.config = config if config is not None else dict()
		self.profiles = {Profile('default')}
		self.targets = set()

	def __call__(self, args=None):
		parser = self._arguments_parser()
		args = parser.parse_args(args)

		config = Config('default', self._default_config)
		config = Config('main', self.config, config)

		try:
			profile = next(i for i in self.profiles if i.name == args.profile)
			config = Config('profile.{}'.format(profile.code), profile.config, config)
		except StopIteration as e:
			raise Exception('Profile not found: {}'.format(args.profile)) from e

		if 'directory.root' not in config:
			raise Exception('Option "directory.root" does not exist')

		config['directory.root'] = str(pathlib.Path(config['directory.root'])/profile.code)

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
			config = Config(Target.GlobalTargetLevel, {}, config)
			target._build(config)


class MockTarget(Target):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.build_called = False
		self.config_on_build = None
		self._outdated = True

	@property
	def outdated(self):
		return self._outdated

	def build(self):
		self.build_called = True
		self.config_on_build = copy.deepcopy(self.config)

class MockBuild(Build):
	def __init__(self, config=None):
		config = config if config is not None else dict()

		if not 'directory' in config:
			config['directory'] = dict()

		if not 'root' in config['directory']:
			config['directory']['root'] = 'ROOT_DIRECTORY'

		super().__init__(config)

class MockProfile(Profile):
	pass

class TestBuilder(TestCase):
	def test_single_target(self):
		build = MockBuild()
		foo = MockTarget('foo')
		build.targets |= {foo}
		build()
		self.assertEqual(True, foo.build_called)

	def test_main_config(self):
		build = MockBuild({'travel': 'ship'})
		ben = MockTarget('Ben')
		mary = MockTarget('Mary',
			dependencies={ben},
			travel='plane'
		)
		susan = MockTarget('Susan',
			travel='car'
		)
		joe = MockTarget('Joe',
			dependencies={mary, susan}
		)

		build.targets |= {joe}
		build()
		self.assertEqual('ship', joe.config_on_build['travel', Scope.Global])
		self.assertEqual('car', susan.config_on_build['travel', Scope.Global])
		self.assertEqual('plane', mary.config_on_build['travel', Scope.Global])
		self.assertEqual('plane', ben.config_on_build['travel', Scope.Global])

	def test_profiles(self):
		build = MockBuild({'travel': 'car'})
		by_plane = MockProfile('by_plane', {'travel': 'plane'})
		build.profiles |= {by_plane}
		gary = MockTarget('Gary',
			travel='ship'
		)
		johnny = MockTarget('Johnny')
		build.targets |= {gary, johnny}
		build(args=('-p', 'by_plane'))
		self.assertEqual('plane', johnny.config_on_build['travel', Scope.Global])
		self.assertEqual('ship', gary.config_on_build['travel', Scope.Global])

	def test_defaults(self):
		build = MockBuild({
			'directory': {
				'root': 'ROOT_DIRECTORY'
			}
		})
		target = self.mock_target(MockTarget, 'some_target', **{
			'directory.stamps': Skip
		})
		build.targets |= {target}
		build()

		expected_output = target.defaults.copy()
		expected_output.update({
			'directory.binaries': 'ROOT_DIRECTORY/default/bin',
			'directory.packages': 'ROOT_DIRECTORY/default/packages',
			'directory.root': 'ROOT_DIRECTORY/default',
			'directory.source': 'ROOT_DIRECTORY/default/src',
			'directory.stamps': 'ROOT_DIRECTORY/default/stamps'
		})
		self.assertEqual(expected_output, target.config_on_build.items())

	def test_outdated(self):
		build = MockBuild()
		bar = self.mock_target(MockTarget, 'bar')
		foo = MockTarget('foo',
			dependencies={bar}
		)
		build.targets |= {foo}

		bar.build_called = False
		bar._outdated = False
		build()
		self.assertFalse(bar.build_called)

		bar.build_called = False
		bar._outdated = True
		build()
		self.assertTrue(bar.build_called)

	def test_always_outdated(self):
		build = MockBuild()
		foo = MockTarget('foo',
			always_outdated=True
		)
		build.targets |= {foo}

		foo.build_called = False
		foo._outdated = False
		build()
		self.assertTrue(foo.build_called)
