#!/usr/bin/env python3
# -*- config: utf-8 -*-

import unittest

class Config:
	def __init__(self, name, config=None, parent=None):
		self.name = name
		self.config = config if config is not None else dict()
		self.parent = parent

	def __getitem__(self, name):
		try:
			return self.config[name]
		except KeyError:
			if self.parent is None:
				raise
			return self.parent[name]

	def __setitem__(self, name, value):
		self.config[name] = value

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

		child['ticket'] = 100
		self.assertEqual(len(child), 2)
		self.assertEqual(len(list(child)), 2)
		self.assertEqual(child['travel'], 'Plane')
		self.assertEqual(child['ticket'], 100)

		self.assertEqual(len(parent), 1)
		self.assertEqual(len(list(parent)), 1)
		self.assertEqual(parent['travel'], 'Car')

if __name__ == '__main__':
	unittest.main()