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

	def get(self, key, level=None):
		try:
			if level is not None and self.name != level:
				raise KeyError(key)
			return self.config[key]
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
		return self.get(**self._arg_key(key))

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

class TestConfig(unittest.TestCase):
	def test_single_config(self):
		config = Config('single')
		self.assertEqual(len(config), 0)
		self.assertEqual(len(list(config)), 0)

		config['some.key'] = 'some value'
		self.assertEqual(len(config), 1)
		self.assertEqual(len(list(config)), 1)
		self.assertEqual(config['some.key'], 'some value')

	def test_inheit_config(self):
		parent = Config('parent')
		parent.config['travel'] = 'Car'
		self.assertEqual(len(parent), 1)
		self.assertEqual(len(list(parent)), 1)
		self.assertEqual(parent['travel'], 'Car')

		child = Config('child', parent=parent)
		self.assertEqual(len(child), 1)
		self.assertEqual(len(list(child)), 1)
		self.assertEqual(child['travel'], 'Car')

		child['travel'] = 'Plane'
		self.assertEqual(len(child), 1)
		self.assertEqual(len(list(child)), 1)
		self.assertEqual(child['travel'], 'Plane')
		self.assertEqual(child['travel', 'parent'], 'Car')

		child['ticket'] = 100
		self.assertEqual(len(child), 2)
		self.assertEqual(len(list(child)), 2)
		self.assertEqual(child['travel'], 'Plane')
		self.assertEqual(child['ticket'], 100)

		self.assertEqual(len(parent), 1)
		self.assertEqual(len(list(parent)), 1)
		self.assertEqual(parent['travel'], 'Car')

		child['travel', 'parent'] = 'Ship'
		self.assertEqual(len(parent), 1)
		self.assertEqual(len(list(parent)), 1)
		self.assertEqual(parent['travel'], 'Ship')


if __name__ == '__main__':
	unittest.main()