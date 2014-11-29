import logging

from .config import Config

def _code_from_name(name):
	return name.replace(' ', '_').replace('.', '_')

class Profile:
	def __init__(self, name, config=None):
		self.name = name
		self.code = _code_from_name(name)
		self.config = config if config is not None else dict()

class Target:
	def __init__(self, name, dependencies=None, config=None):
		self.name = name
		self.code = _code_from_name(name)
		self.dependencies = dependencies if dependencies is not None else set()
		self.config = config if config is not None else dict()

	def log(self, level, message):
		logging.log(level, '{}: {}'.format(self.name, message))

	def _build(self, config):
		config = Config('target.{}'.format(self.code), self.config, config)

		self.log(logging.INFO, 'processing dependencies...')
		for dependency in self.dependencies:
			dependency._build(config)
		self.log(logging.INFO, 'dependencies ready.')

		self.log(logging.INFO, 'building...')
		self.build(config)
		self.log(logging.INFO, 'built.')