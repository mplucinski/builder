import argparse
import copy
import logging
import pathlib
import sys

from .base import Profile, Scope, Target, TargetTestCase
from .config import Config, ConfigDict

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
	_default_warnings = ConfigDict(
		errors=False,
		enable=ConfigDict(
			normal=True,
			extensions=False,
			compatibility=False,
			performance=ConfigDict(
				normal=False,
				platform=False,
			),
			system_code=False
		)
	)
	_default_config = ConfigDict(
		always_outdated=False,
		directory=ConfigDict(
			binaries =lambda config: str(pathlib.Path(config['directory.root'])/'bin'),
			include  =lambda config: str(pathlib.Path(config['directory.root'])/'include'),
			packages =lambda config: str(pathlib.Path(config['directory.root'])/'packages'),
			source   =lambda config: str(pathlib.Path(config['directory.root'])/'src'),
			stamps   =lambda config: str(pathlib.Path(config['directory.root'])/'stamps')
		),
		process=ConfigDict(
			echo=ConfigDict(
				stdout=False,
				stderr=False
			),
			environment={}
		),
		language=ConfigDict({
			'c': ConfigDict(
				flags=lambda config: compilers._get_compiler('c', config).flags,
				warnings=_default_warnings
			),
			'c++': ConfigDict(
				flags=lambda config: compilers._get_compiler('c++', config).flags,
				warnings=_default_warnings
			)
		})
	)

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
		self.config = ConfigDict(config if config is not None else dict())
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


class TestBuilder(TargetTestCase):
	def test_single_target(self):
		build = self.mock_build(Build)
		foo, runtime_config = self.mock_target(Target, 'foo')
		build.targets |= {foo}
		build()
		self.assertTrue(runtime_config.value is not None)

	def test_main_config(self):
		build = self.mock_build(Build, config=ConfigDict(travel='ship'))
		ben, ben_config = self.mock_target (Target, 'Ben')
		mary, mary_config = self.mock_target(Target, 'Mary',
			dependencies={ben},
			config=ConfigDict(
				travel='plane'
			)
		)
		susan, susan_config = self.mock_target(Target, 'Susan',
			config=ConfigDict(
				travel='car'
			)
		)
		joe, joe_config = self.mock_target(Target, 'Joe',
			dependencies={mary, susan}
		)

		build.targets |= {joe}
		build()
		self.assertEqual('ship', joe_config.value['travel', Scope.Global])
		self.assertEqual('car', susan_config.value['travel', Scope.Global])
		self.assertEqual('plane', mary_config.value['travel', Scope.Global])
		self.assertEqual('plane', ben_config.value['travel', Scope.Global])

	def test_profiles(self):
		build = self.mock_build(Build, config=ConfigDict(travel='car'))
		by_plane = self.mock_profile(Profile, 'by_plane', config=ConfigDict(
			travel='plane'
		))
		build.profiles |= {by_plane}
		gary, gary_config = self.mock_target(Target, 'Gary', config=ConfigDict(
			travel='ship'
		))
		johnny, johnny_config = self.mock_target(Target, 'Johnny')
		build.targets |= {gary, johnny}
		build(args=('-p', 'by_plane'))
		self.assertEqual('plane', johnny_config.value['travel', Scope.Global])
		self.assertEqual('ship', gary_config.value['travel', Scope.Global])

	def test_defaults(self):
		target, target_config = self.mock_target(Target, 'some_target', config=ConfigDict(
			language=ConfigDict({
				'c': ConfigDict(
					flags=None
				),
				'c++': ConfigDict(
					flags=None
				)
			})
		))
		self.run_target(target)

		self.assertTrue(target_config.value is not None)
		root_dir = pathlib.Path(target_config.value['directory.root'])

		expected_output = Config._flatten_dict(Build._default_config.copy())
		expected_output['language.c.flags'] = None
		expected_output['language.c++.flags'] = None
		expected_output.update({
			'directory.binaries': str(root_dir/'bin'),
			'directory.include': str(root_dir/'include'),
			'directory.packages': str(root_dir/'packages'),
			'directory.root': str(root_dir),
			'directory.source': str(root_dir/'src'),
			'directory.stamps': str(root_dir/'stamps'),
			'target.some_target.build': True,
			'target.some_target.file.stamp': self.comparatorAny()
		})
		self.assertEqual(expected_output, target_config.value.items())

	def test_outdated(self):
		bar, bar_config = self.mock_target(Target, 'bar')
		foo, foo_config = self.mock_target(Target, 'foo',
			dependencies={bar}
		)
		build = self.mock_build(Build)
		build.targets |= {foo}
		build()

		self.assertTrue(bar_config.value is not None)
		bar_config.value = None

		build()
		self.assertTrue(bar_config.value is None)

	def test_always_outdated(self):
		foo, foo_config = self.mock_target(Target, 'foo', config=ConfigDict(
			always_outdated=True,
		))
		build = self.mock_build(Build)
		build.targets |= {foo}
		build()

		self.assertTrue(foo_config.value is not None)
		foo_config.value = None

		build()
		self.assertTrue(foo_config.value is not None)
