#!/usr/bin/env python3
# -*- conding: utf-8 -*-

import re
import unittest

from .base import Compiler
from .config import Config
from .process import Process
from .tests import TestCase

def _get_compiler(language, config, process_class=Process):
	executable = config['language.{}.compiler'.format(language)]
	for i in _supported_compilers:
		compiler = i._detect_compiler(executable, language=language,
			config=config, process_class=process_class)
		if compiler is not None:
			return compiler
	raise Exception(('Could not detect compiler located at {}; to use this '+
		'compiler you need to configure all flags manually').format(executable))

class Clang(Compiler):
	@staticmethod
	def _detect_compiler(executable, language, config, process_class=Process):
		process = process_class([executable, '-v'], capture_stdout=True, capture_stderr=True)
		_, stderr = process.communicate()
		stderr = stderr.decode('utf-8')
		m = re.search(r'clang version (([0-9]+\.?)+)', stderr)
		if m:
			return Clang(m.group(1), language, config)
		return None

	@property
	def flags(self):
		flags = []

		warnings_to_errors = bool(self.config('warnings.errors'))
		warnings_categories = { k for k, v in self.config('warnings.enable').items() if v }

		def add_warning_flag(name, flag):
			enabled = (name in warnings_categories)
			flags.append('-W{}{}'.format('' if enabled else 'no-', flag))

		if warnings_to_errors:
			flags.append('-Werror')

		if len(warnings_categories) == 0:
			flags.append('-w')
		else:
			pedantic = bool('extensions' in warnings_categories)
			if pedantic:
				flags.append('-pedantic-errors' if warnings_to_errors else '-pedantic')
			add_warning_flag('normal', 'everything')
			if self.language == 'c':
				add_warning_flag('compatibility', 'c99-compat')
			elif self.language == 'c++':
				if pedantic:
					add_warning_flag('compatibility', 'c++98-compat-pendantic')
				else:
					add_warning_flag('compatibility', 'c++98-compat')
			add_warning_flag('performance.platform', 'padded')
			add_warning_flag('performance.platform', 'packed')
			add_warning_flag('system_code', 'system-headers')

		return flags

_supported_compilers = {Clang}

class TestClang(TestCase):
	cases_version = [
		(b'''clang version 3.4.2 (tags/RELEASE_34/dot2-final)
Target: x86_64-apple-darwin13.4.0
Thread model: posix
''', '3.4.2'),
		(b'''clang version 3.5.0 (tags/RELEASE_350/final)
Target: x86_64-apple-darwin13.4.0
Thread model: posix
''', '3.5.0'),
		(b'''clang version 3.4 (tags/RELEASE_34/final)
Target: x86_64-redhat-linux-gnu
Thread model: posix
Found candidate GCC installation: /usr/bin/../lib/gcc/x86_64-redhat-linux/4.8.3
Found candidate GCC installation: /usr/lib/gcc/x86_64-redhat-linux/4.8.3
Selected GCC installation: /usr/bin/../lib/gcc/x86_64-redhat-linux/4.8.3
''', '3.4')
	]

	def test_detect_clang(self):
		for i in self.cases_version:
			compiler = _get_compiler(
				'c', {'language.c.compiler': 'clang'},
				self.mock_process(b'', i[0])
			)
			self.assertEqual(Clang, type(compiler))
			self.assertEqual(i[1], compiler.version)

	cases_flags_warnings = [
		('case 1', {
		 	'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-w']),
		('case 2', {
			'errors':                      True,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-Werror', '-w']),
		('case 3', {
			'errors':                      False,
			'enable.normal':               True,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-Weverything', '-Wno-c99-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 4', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           True,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-pedantic', '-Wno-everything', '-Wno-c99-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 5', {
			'errors':                      True,
			'enable.normal':               False,
			'enable.extensions':           True,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-Werror', '-pedantic-errors', '-Wno-everything', '-Wno-c99-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 6', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        True,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-Wno-everything', '-Wc99-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 7', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        True,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c++', ['-Wno-everything', '-Wc++98-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 8', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           True,
			'enable.compatibility':        True,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c++', ['-pedantic', '-Wno-everything', '-Wc++98-compat-pendantic', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 9', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   True,
			'enable.performance.platform': False,
			'enable.system_code':          False
		}, 'c', ['-Wno-everything', '-Wno-c99-compat', '-Wno-padded', '-Wno-packed', '-Wno-system-headers']),
		('case 10', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': True,
			'enable.system_code':          False
		}, 'c', ['-Wno-everything', '-Wno-c99-compat', '-Wpadded', '-Wpacked', '-Wno-system-headers']),
		('case 11', {
			'errors':                      False,
			'enable.normal':               False,
			'enable.extensions':           False,
			'enable.compatibility':        False,
			'enable.performance.normal':   False,
			'enable.performance.platform': False,
			'enable.system_code':          True
		}, 'c', ['-Wno-everything', '-Wno-c99-compat', '-Wno-padded', '-Wno-packed', '-Wsystem-headers']),
		('case 12', {
			'errors':                      True,
			'enable.normal':               True,
			'enable.extensions':           True,
			'enable.compatibility':        True,
			'enable.performance.normal':   True,
			'enable.performance.platform': True,
			'enable.system_code':          True
		}, 'c', ['-Werror', '-pedantic-errors', '-Weverything', '-Wc99-compat', '-Wpadded', '-Wpacked', '-Wsystem-headers']),
	]

	def test_flags_warnings(self):
		for i in self.cases_flags_warnings:
			config = {'language.{}.warnings'.format(i[2]): i[1]}
			config = Config('test_clang_flags', config)
#			config._dump()
			clang = Clang('3.5.0', i[2], config)
			self.assertEqual(i[3], clang.flags, msg=i[0])

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestClang))
	return suite

if __name__ == '__main__':
	unittest.main()