import copy
import functools
import logging
import pathlib
import sys
import tempfile
import unittest

def _log(level, msg):
	logging.log(level, msg)

def _fn_log(level):
	def wrapper1(fn):
		@functools.wraps(fn)
		def wrapper2(*args, **kwargs):
			_log(level, '{}({}, {})'.format(fn.__qualname__, ', '.join(map(repr, args)),
				', '.join(['{}={}'.format(repr(k), repr(v)) for k, v in kwargs.items()]) ))
			r = fn(*args, **kwargs)
			_log(level, '{}(...) = {}'.format(fn.__qualname__, repr(r)))
			return r
		return wrapper2
	return wrapper1

class SkipType:
	pass

Skip = SkipType

class Result:
	def __init__(self):
		self.value = None

class TestCase(unittest.TestCase):
	def setUp(self):
		self.maxDiff = None
		self.root_dir = tempfile.TemporaryDirectory()

	def tearDown(self):
		self.root_dir.cleanup()

	def comparatorAny(self):
		class Comparator:
			def __eq__(self, other):
				return True
		return Comparator()

	def mock_profile(self, cls, name, config=None):
		return cls(name, config)

	def mock_process(self, stdout, stderr):
		class MockProcess:
			def __init__(self, args, **kwargs):
				pass

			def communicate(self):
				return stdout, stderr

		return MockProcess
