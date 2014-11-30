#!/usr/bin/env python3
# -*- config: utf-8 -*-

import unittest

class Config:
	def __init__(self, name, config=None, parent=None):
		self.name = name
		self.config = config if config is not None else dict()
		self.parent = parent

	@staticmethod
	def _arg_key(key):
		if isinstance(key, tuple):
			return dict(key=key[0], level=key[1])
		return dict(key=key, level=None)

	def get(self, key, level=None, resolve=False):
		try:
			if level is not None and self.name != level:
				raise KeyError(key)
			value = self.config[key]
			if callable(value):
				value = value(self)
			return value
		except KeyError:
			if self.parent is None:
				raise
			return self.parent.get(key)

	def set(self, key, value, level=None):
		if level is not None and self.name != level:
			self.parent.set(key, value, level)
		else:
			self.config[key] = value

	def __getitem__(self, key):
		return self.get(resolve=True, **self._arg_key(key))

	def __setitem__(self, key, value):
		self.set(value=value, **self._arg_key(key))

	def __len__(self):
		parent_keys = set(self.parent.config.keys()) if self.parent is not None else set()
		return len(set(self.config.keys()) | parent_keys)

	def __iter__(self):
		class Iterator:
			def __init__(self, config):
				self.config = config
				self.iterator = iter(self.config.config)
				self.visited = set()

			def __iter__(self):
				return self

			def __next__(self):
				try:
					while True:
						key = next(self.iterator)
						if key not in self.visited:
							self.visited.add(key)
							return key
				except StopIteration:
					if self.config.parent is None:
						raise
					self.config = self.config.parent
					self.iterator = iter(self.config.config)
					return next(self)

		return Iterator(self)

class MockConfig(Config):
	def __init__(self, name=None, config=None):
		name = name if name is not None else 'mocked_config'
		super().__init__(name, config=config)

class TestConfig(unittest.TestCase):
	def test_single_config(self):
		config = Config('single')
		self.assertEqual(0, len(config))
		self.assertEqual(0, len(list(config)))

		config['some.key'] = 'some value'
		self.assertEqual(1, len(config))
		self.assertEqual(1, len(list(config)))
		self.assertEqual('some value', config['some.key'])

	def test_inheit_config(self):
		parent = Config('parent')
		parent.config['travel'] = 'Car'
		self.assertEqual(1, len(parent))
		self.assertEqual(1, len(list(parent)))
		self.assertEqual('Car', parent['travel'])

		child = Config('child', parent=parent)
		self.assertEqual(1, len(child))
		self.assertEqual(1, len(list(child)))
		self.assertEqual('Car', child['travel'])

		child['travel'] = 'Plane'
		self.assertEqual(1, len(child))
		self.assertEqual(1, len(list(child)))
		self.assertEqual('Plane', child['travel'])
		self.assertEqual('Car', child['travel', 'parent'])

		child['ticket'] = 100
		self.assertEqual(2, len(child))
		self.assertEqual(2, len(list(child)))
		self.assertEqual('Plane', child['travel'])
		self.assertEqual(100, child['ticket'])

		self.assertEqual(1, len(parent))
		self.assertEqual(1, len(list(parent)))
		self.assertEqual('Car', parent['travel'])

		child['travel', 'parent'] = 'Ship'
		self.assertEqual(1, len(parent))
		self.assertEqual(1, len(list(parent)))
		self.assertEqual('Ship', parent['travel'])

	def test_callable(self):
		config = Config('cfg')
		config['foo'] = 'bar'
		config['baz'] = lambda config: config['foo']+' yea'
		self.assertEqual('bar', config['foo'])
		self.assertEqual('bar yea', config['baz'])

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestConfig))
	return suite

if __name__ == '__main__':
	unittest.main()