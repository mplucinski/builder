import logging
import unittest

from .tests import _fn_log, TestCase

class ConfigDict(dict):
	def __repr__(self):
		return'<ConfigDict {}>'.format(super().__repr__())

class Config:
	@staticmethod
	def _flatten_dict(dictionary, prefix=''):
		prefixed = lambda key: '{}.{}'.format(prefix, key) if prefix else key
		output = {}
		for key, value in dictionary.items():
			if isinstance(value, ConfigDict):
				output.update(Config._flatten_dict(value, prefixed(key)))
			else:
				output[prefixed(key)] = value
		return output

	@staticmethod
	def _flatten_value(key, value):
		output = {}
		if isinstance(value, dict):
			output.update(Config._flatten_dict(value, key))
		else:
			output[key] = value
		return output

	def __init__(self, name, config=None, parent=None):
		self.name = name
		self.config = self._flatten_dict(config) if config is not None else dict()
		self.parent = parent

	def __repr__(self):
		return '<{} name={}>'.format(self.__class__.__qualname__, self.name)

	def _dump(self):
		print('Config', self.name, self.config)
		if self.parent is not None:
			self.parent._dump()

	def items(self):
		return { k: self[k] for k in self }

	@staticmethod
	def _arg_key(key):
		if isinstance(key, tuple):
			return dict(key=key[0], level=key[1])
		return dict(key=key, level=None)

	def _get_subelements(self, key):
		return { k for k in self.config if k.startswith(key+'.') }

	@_fn_log(logging.DEBUG-2)
	def get_single(self, key, top_config=None, level=None, resolve=False):
		assert top_config is not None
		try:
			if level is not None and self.name != level:
				raise KeyError(key)
			value = self.config[key]
			if callable(value) and resolve:
				logging.log(logging.DEBUG-2, 'Resolving callable value for {}={}'.format(key, value))
				value = value(top_config)
			return value
		except KeyError:
			if self.parent is None:
				raise
			return self.parent.get(key, top_config=top_config, level=level, resolve=resolve)

	@_fn_log(logging.DEBUG-2)
	def get(self, key, *args, **kwargs):
		if 'top_config' not in kwargs:
			kwargs['top_config'] = self
		try:
			return self.get_single(key, *args, **kwargs)
		except KeyError:
			prefix = key+'.'
			output = {}
			for i in kwargs['top_config']:
				if i.startswith(prefix):
					output[i[len(prefix):]] = kwargs['top_config'][i]
			if len(output) == 0:
				raise KeyError(key)
			return output

	@_fn_log(logging.DEBUG-2)
	def set(self, key, value, level=None):
		if level is not None and self.name != level:
			self.parent.set(key, value, level)
		else:
			remove = self._get_subelements(key)
			for i in remove:
				del self.config[i]
			add = self._flatten_value(key, value)
			self.config.update(add)

	def __getitem__(self, key):
		return self.get(resolve=True, top_config=self, **self._arg_key(key))

	def __setitem__(self, key, value):
		self.set(value=value, **self._arg_key(key))

	def __contains__(self, key):
		try:
			self[key]
			return True
		except KeyError:
			return False

	def __len__(self):
		parent_keys = set(self.parent.config.keys()) if self.parent is not None else set()
		return len(set(self.config.keys()) | parent_keys)

	@_fn_log(logging.DEBUG-2)
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

class TestConfig(TestCase):
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

	def test_dict_hierarchy(self):
		config = Config('cfg', config=ConfigDict(
			keyboard=ConfigDict(
				count=104,
				layout=ConfigDict(
					usa='qwerty'
				)
			)
		))
		self.assertEqual(104, config['keyboard.count'])
		self.assertEqual('qwerty', config['keyboard.layout.usa'])
		self.assertRaises(KeyError, lambda: config['keyboard.layout.france'])
		self.assertRaises(KeyError, lambda: config['keyboard.layout.germany'])
		self.assertEqual({'usa': 'qwerty'}, config['keyboard.layout'])

		config['keyboard.layout.france'] = 'azerty'
		self.assertEqual(104, config['keyboard.count'])
		self.assertEqual('qwerty', config['keyboard.layout.usa'])
		self.assertEqual('azerty', config['keyboard.layout.france'])
		self.assertRaises(KeyError, lambda: config['keyboard.layout.germany'])
		self.assertEqual({'usa': 'qwerty', 'france': 'azerty'}, config['keyboard.layout'])

		config['keyboard.layout'] = {
			'germany': 'qwertz'
		}
		self.assertEqual(104, config['keyboard.count'])
		self.assertRaises(KeyError, lambda: config['keyboard.layout.usa'])
		self.assertRaises(KeyError, lambda: config['keyboard.layout.france'])
		self.assertEqual('qwertz', config['keyboard.layout.germany'])
		self.assertEqual({'germany': 'qwertz'}, config['keyboard.layout'])

	def test_items(self):
		cfg = ConfigDict(
			keyboard=ConfigDict(
				count=104,
				layout=ConfigDict(
					usa='qwerty',
					france='azerty'
				)
			)
		)
		config = Config('cfg', config=cfg)
		self.assertEqual(Config._flatten_dict(cfg), config.items())
