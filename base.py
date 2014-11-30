import logging

from .config import Config

def _code_from_name(name):
	return name.lower().replace(' ', '_').replace('.', '_')

class Profile:
	def __init__(self, name, config=None):
		self.name = name
		self.code = _code_from_name(name)
		self.config = config if config is not None else dict()

class Scope:
	Local = 1
	Global = 2
	Auto = 3

class TargetConfig:
	def __init__(self, target, config):
		self.target = target
		self.config = config

	@staticmethod
	def _arg_key(key):
		if not isinstance(key, tuple):
			key = (key,)
		d = {}
		if len(key) >= 1: d['key']   = key[0]
		if len(key) >= 2: d['scope'] = key[1]
		if len(key) >= 3: d['level'] = key[2]
		return d

	def get(self, key, scope=Scope.Auto, level=None, resolve=False):
		if scope == Scope.Local:
			key = self.target._local_config_key(key)
		elif scope == Scope.Global:
			pass
		elif scope == Scope.Auto:
			try:
				return self.get(key, scope=Scope.Local, level=level, resolve=resolve)
			except KeyError:
				return self.get(key, scope=Scope.Global, level=level, resolve=resolve)

		return self.config.get(key, level, resolve=resolve)

	def __getitem__(self, key):
		return self.get(resolve=True, **self._arg_key(key))

class Target:
	local_config_keys = set()

	def _local_config_key(self, key):
		return 'target.{}.{}'.format(self.code, key)

	def __init__(self, name, dependencies=None, **kwargs):
		self.name = name
		self.code = _code_from_name(name)
		self.dependencies = dependencies if dependencies is not None else set()
		self.config = { k: v for k, v in kwargs.items() if k not in self.local_config_keys }
		self.config.update({ self._local_config_key(k): v for k, v in kwargs.items() if k in self.local_config_keys })

	def log(self, level, message):
		logging.log(level, '{}: {}'.format(self.name, message))

	def _build(self, config):
		config = Config('target.{}'.format(self.code), self.config, config)

		self.log(logging.INFO, 'processing dependencies...')
		for dependency in self.dependencies:
			dependency._build(config)
		self.log(logging.INFO, 'dependencies ready.')

		self.log(logging.INFO, 'building...')
		self.build(TargetConfig(self, config))
		self.log(logging.INFO, 'built.')