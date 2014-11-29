import copy
import types

import builder

class ConfigHelper:
	def __init__(self, config):
		self.config = config

	def execute(self, *args, **kwargs):
		inherit_env = kwargs.pop('inherit_env', False)
		env = kwargs.pop('env', None)

		_env = copy.deepcopy(os.environ) if inherit_env else dict()
		_env.update(self.config.get('env', {}))
		if env is not None:
			_env.update(env)

		kwargs['env'] = _env
		return builder.Process(*args, **kwargs).communicate()

	def c_cxx_detect_compiler(self, lang):
		return self.detect_compiler(self.config['{}.compiler'.format(lang)])

	def detect_compiler(self, compiler):
		(out, err) = self.execute([compiler, '-v'], capture_stdout=True, capture_stderr=True)
		out = out.decode('utf-8').splitlines()
		err = err.decode('utf-8').splitlines()
		if len(err) > 0:
			m = re.match(r'clang version ([0-9\.]+) .*', err[0])
			if m:
				return ('clang', m.group(1))
		raise Exception('Unknown compiler: {}'.format(compiler))

	def _unknown_value(self, option):
		raise Exception('Unknown value for configuration option {}: {}'.format(option, self.config.get(option)))

	def c_cxx_warning_flags(self, compiler, lang):
		flags = []
		if compiler[0] == 'clang':
			errors = self.config['{}.warnings.errors'.format(lang)]
			if errors:
				flags.append('-Werror')

			flags.append('-Weverything')

			if not self.config['{}.warnings.enable.normal'.format(lang)]:
				flags.append('-Wno-everything')

			if self.config['{}.warnings.enable.extensions'.format(lang)]:
				if not errors:
					flags.append('-pedantic')
				else:
					flags.append('-pedantic-errors')

			if not self.config['{}.warnings.enable.compatibility'.format(lang)]:
				if lang == 'c':
					flags += ['-Wno-c99-compat']
				elif lang == 'cxx':
					flags += ['-Wno-c++98-compat', '-Wno-c++98-compat-pedantic']
				else:
					raise Exception('Unknown language: {}'.format(lang))

			if not self.config['{}.warnings.enable.performance'.format(lang)]:
				pass

			if not self.config['{}.warnings.enable.performance_platform'.format(lang)]:
				flags += ['-Wno-padded', '-Wno-packed']

			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def c_cxx_compilation_flags(self, lang):
		flags = []
		compiler = self.c_cxx_detect_compiler(lang)
		if compiler[0] == 'clang':
			if self.config.has('{}.standard'.format(lang)):
				flags.append('-std={}'.format(self.config['{}.standard'.format(lang)].lower()))
			flags += self.c_cxx_warning_flags(compiler, lang)
			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def c_compilation_flags(self):
		return self.c_cxx_compilation_flags('c')

	def cxx_compilation_flags(self):
		compiler = self.c_cxx_detect_compiler('cxx')
		flags = self.c_cxx_compilation_flags('cxx')
		if compiler[0] == 'clang':
			if self.config.has('cxx.standard_library'):
				flags.append('-stdlib={}'.format(self.config['cxx.standard_library'].lower()))
			return flags
		raise Exception('Unknown compiler: {}'.format(compiler))

	def resolve_value(self, value):
		if isinstance(value, types.FunctionType):
			value = value(self.config)
		return value

class Config:
	def __init__(self, create_helper=True, config={}, parent=None):
		self.helper = ConfigHelper(self) if create_helper else None
		self.config = copy.deepcopy(config)
		self.parent = parent

	def __repr__(self):

	@staticmethod
	def _merged_dicts(d1, d2):
		do = dict()
		for i in d1:
			if not i in d2:
				do[i] = d1[i]
			else:
				o1 = d1[i]
				o2 = d2[i]
				if isinstance(o1, dict) and isinstance(o2, dict):
					do[i] = Config._merged_dicts(o1, o2)
				else:
					do[i] = o2
		for i in d2:
			if not i in d1:
				do[i] = d2[i]
		return do

	def merged(self, other):
		config = Config._merged_dicts(copy.deepcopy(self.config), copy.deepcopy(other))
		return Config(config=config, parent=self)

	def has(self, name):
		try:
			self[name]
			return True
		except KeyError:
			return False

	def __getitem__(self, name):
		return self.get(name, raise_key_error=True)

	def get(self, name, default=None, raise_key_error=False):
		_name = name.split('.')
		current = self.config
		while len(_name) > 0:
			if _name[0] in current:
				current = current[_name[0]]
				_name = _name[1:]
			else:
				if raise_key_error:
					raise KeyError('Option {} not found'.format(name))
				return default
		return self.helper.resolve_value(current)

	def __setitem__(self, name, value):
		self.set(name, value)

	def set(self, name, value, parent_scope=False):
		_name = name.split('.')
		current = self.config
		while len(_name) > 0:
			node = _name[0]
			if len(_name) == 1: #leaf
				current[node] = value
			elif not node in current:
				current[node] = dict()
			current = current[_name[0]]
			_name = _name[1:]

		if parent_scope:
			self.parent.set(name, value)		return '<{} config={}>'.format(self.__class__, self.config)