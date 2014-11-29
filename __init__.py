#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import copy
import logging
import sys
import unittest

from .base import Profile
from .base import Target
from .config import Config

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

class Build:
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

		config = Config('main', self.config)

		try:
			profile = next(i for i in self.profiles if i.name == args.profile)
			config = Config('profile.{}'.format(profile.code), profile.config, config)
		except StopIteration as e:
			raise Exception('Profile not found: {}'.format(args.profile)) from e

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
			target._build(config)


class MockTarget(Target):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.build_called = False
		self.config_on_build = None

	def build(self, config):
		self.build_called = True
		self.config_on_build = copy.deepcopy(config)

class MockProfile(Profile):
	pass

class TestBuilder(unittest.TestCase):
	def test_single_target(self):
		build = Build()
		foo = MockTarget('foo')
		build.targets |= {foo}
		build()
		self.assertEqual(True, foo.build_called)

	def test_main_config(self):
		build = Build({'travel': 'ship'})
		ben = MockTarget('Ben')
		mary = MockTarget('Mary',
			dependencies={ben},
			config={
				'travel': 'plane'
			}
		)
		susan = MockTarget('Susan',
			config={
				'travel': 'car'
			}
		)
		joe = MockTarget('Joe',
			dependencies={mary, susan}
		)

		build.targets |= {joe}
		build()
		self.assertEqual('ship', joe.config_on_build['travel'])
		self.assertEqual('car', susan.config_on_build['travel'])
		self.assertEqual('plane', mary.config_on_build['travel'])
		self.assertEqual('plane', ben.config_on_build['travel'])

	def test_profiles(self):
		build = Build({'travel': 'car'})
		by_plane = MockProfile('by_plane', {'travel': 'plane'})
		build.profiles |= {by_plane}
		gary = MockTarget('Gary',
			config={
				'travel': 'ship'
			}
		)
		johnny = MockTarget('Johnny')
		build.targets |= {gary, johnny}
		build(args=('-p', 'by_plane'))
		self.assertEqual('plane', johnny.config_on_build['travel'])
		self.assertEqual('ship', gary.config_on_build['travel'])
