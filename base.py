import logging

from .config import Config
from .process import Process

def _code_from_name(name):
	return name.lower().replace(' ', '_').replace('.', '_')

def samefile(first, second):
	def _stat(f):
		try:
			return f.stat()
		except AttributeError:
			import os
			return os.stat(f)

	import os.path
	first = _stat(first)
	second = _stat(second)
	return os.path.samestat(first, second)

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

	def items(self):
		return self.config.items()

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

		return self.config.get(key=key, level=level, resolve=resolve)

	def set(self, key, value, scope=Scope.Local, level=None):
		if scope == Scope.Local:
			key = self.target._local_config_key(key)
		elif scope == Scope.Global:
			pass
		elif scope == Scope.Auto:
			raise Exception('set() operation does not support Scope.Auto')
		self.config.set(key=key, value=value, level=level)

	def __getitem__(self, key):
		return self.get(resolve=True, **self._arg_key(key))

	def __setitem__(self, key, value):
		self.set(value=value, **self._arg_key(key))

	def __iter__(self):
		return iter(self.config)

class Target:
	GlobalTargetLevel = 'target'

	local_config_keys = set()
	local_config_defaults = dict()

	def _local_config_key(self, key):
		return 'target.{}.{}'.format(self.code, key)

	def __init__(self, name, dependencies=None, **kwargs):
		kwargs = Config._flatten_dict(kwargs)

		self.name = name
		self.code = _code_from_name(name)
		self.dependencies = dependencies if dependencies is not None else set()
		self._config = { k: v for k, v in kwargs.items() if k not in self.local_config_keys }
		self._config.update({ self._local_config_key(k): v for k, v in kwargs.items() if k in self.local_config_keys })
		self._config.update({ self._local_config_key(k): v for k, v in self.local_config_defaults.items() if k not in kwargs  })

	@property
	def outdated(self):
		return True

	def call(self, *args, **kwargs):
		if not 'echo_stdout' in kwargs:
			kwargs['echo_stdout'] = self.config['process.echo.stdout']
		if not 'echo_stderr' in kwargs:
			kwargs['echo_stderr'] = self.config['process.echo.stderr']
		process = Process(*args, **kwargs)
		process.communicate()

	def log(self, level, message):
		logging.log(level, '{}: {}'.format(self.name, message))

	def _build(self, config):
		config = Config('target.{}'.format(self.code), self._config, config)

		self.log(logging.INFO, 'processing dependencies...')
		for dependency in self.dependencies:
			dependency._build(config)
		self.log(logging.INFO, 'dependencies ready.')

		self.log(logging.INFO, 'building...')
		self.config = TargetConfig(self, config)

		rebuild = self.config['always_outdated'] or self.outdated

		if rebuild:
			self.build()

		self.config['build', Scope.Local, Target.GlobalTargetLevel] = rebuild

		self.config = None
		self.log(logging.INFO, 'built.')