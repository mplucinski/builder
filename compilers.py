#!/usr/bin/env python3
# -*- conding: utf-8 -*-

import re
import unittest

from .process import Process
from .tests import TestCase

def _get_compiler(language, config, process_class=Process):
	executable = config['language.{}.compiler'.format(language)]
	for i in _supported_compilers:
		compiler = i._detect_compiler(executable, process_class=process_class)
		if compiler is not None:
			return compiler
	raise Exception(('Could not detect compiler located at {}; to use this '+
		'compiler you need to configure all flags manually').format(executable))

class Clang:
	@staticmethod
	def _detect_compiler(executable, process_class=Process):
		process = process_class([executable, '-v'], capture_stdout=True, capture_stderr=True)
		_, stderr = process.communicate()
		stderr = stderr.decode('utf-8')
		m = re.search(r'clang version (([0-9]+\.?)+)', stderr)
		if m:
			return Clang(m.group(1))
		return None

	def __init__(self, version):
		self.version = version

_supported_compilers = {Clang}

class TestClang(TestCase):
	cases = [
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
		for i in self.cases:
			compiler = _get_compiler(
				'c', {'language.c.compiler': 'clang'},
				self.mock_process(b'', i[0])
			)
			self.assertEqual(Clang, type(compiler))
			self.assertEqual(i[1], compiler.version)

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestClang))
	return suite

if __name__ == '__main__':
	unittest.main()