#!/usr/bin/env python3
# -*- config: utf-8 -*-

import unittest

class Config:
	def __init__(self, name, config=dict()):
		self.name = name
		self.config = config

	def __getitem__(self, name):
		return self.config[name]

	def __setitem__(self, name, value):
		self.config[name] = value

	def __len__(self):
		return len(self.config)

	def __iter__(self):
		class Iterator:
			def __init__(self, config):
				self.config = config
				self.iterator = iter(self.config.config)

			def __iter__(self):
				return self

			def __next__(self):
				return next(self.iterator)

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

if __name__ == '__main__':
	unittest.main()