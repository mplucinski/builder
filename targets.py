import copy
import logging
import os
import os.path
import re
import shutil
import subprocess
import urllib.parse
import urllib.request

class Target:
	def __init__(self, name, dependencies=[], *args, **kwargs):
		self.name = name
		self.code = name.lower().replace(' ','_')
		self.dependencies = dependencies
		self.local_config = kwargs

	def _build(self, config):
		stamp_file = os.path.join(config['directory.root'], '.done-{}'.format(self.code))
		if os.path.exists(stamp_file):
			logging.info('Skipping build of {} (remove {} to force rebuild)'.format(self.name, stamp_file))
			config.set('skip', True)
		else:
			config.set('skip', False)

		if len(self.dependencies) > 0:
			logging.info('Preparing dependencies for {}...'.format(self.name))
			for i in self.dependencies:
				i._build(config)
			logging.info('Preparing dependencies for {} done.'.format(self.name))

		config = config.merged(self.local_config)

		logging.info('Building {} for {}...'.format(self.name,  config['platform'].name))
		self.build(config)
		logging.info('Building {} for {} done.'.format(self.name, config['platform'].name))

		open(stamp_file, 'w')

	def build(self, config):
		raise Exception('{} has no implementation of "build" method'.format(self))

	def prepare_source(self, config):
		if not 'source_dir' in self.local_config:
			archive_file = self.local_config.get('archive_file',
					self.download(config, self.local_config['url'], config['directory.archive'])
			)
			source_dir = self.extract(config, archive_file, config['directory.source'])
		else:
			source_dir = self.local_config['source_dir']
		source_dir = config.helper.resolve_value(source_dir)
		return source_dir

	def download(self, config, url, target_dir, skip_if_exists=True):
		logging.debug('Downloading {}...'.format(url))
		os.makedirs(target_dir, exist_ok=True)
		file_path = urllib.parse.urlparse(url).path
		file_name = os.path.split(file_path)[1]
		target_file = os.path.join(target_dir, file_name)
		if not (skip_if_exists and os.path.exists(target_file)):
			urllib.request.urlretrieve(self.local_config['url'], target_file)
		else:
			logging.debug('File {} already exists, skipping download.'.format(target_file))
		logging.debug('Downloading {} done.'.format(url))
		return target_file

	def extract(self, config, archive_file, target_dir, skip_if_exists=True):
		logging.debug('Extracting {} to {}...'.format(archive_file, target_dir))
		os.makedirs(target_dir, exist_ok=True)
		files_list = config.helper.execute(
			['tar', 'tf', archive_file],
			capture_stdout=True
		)[0]
		files_list = files_list.decode('utf-8').splitlines()
		files_list = [ i.split(os.path.sep) for i in files_list ]
		files_list = [ ('' if len(i) == 0 else (('' if len(i) ==1 else i[1]) if i[0] == '.' else i[0]))  for i in files_list ]
		files_list = [ i for i in files_list if len(i) > 0 ]
		files_list = set(files_list)
		extracted_dir = next(iter(files_list)) if len(files_list) == 1 else None
		extracted_dir_path = os.path.join(target_dir, extracted_dir if extracted_dir else self.code)
		if not config['skip']:
			if not(skip_if_exists and os.path.exists(extracted_dir_path)):
				if not extracted_dir:
					os.makedirs(extracted_dir_path, exist_ok=True)
					target_dir = extracted_dir_path
				logging.debug('Actual extraction in {}'.format(target_dir))
				config.helper.execute(
					['tar', 'xf', archive_file],
					cwd=target_dir
				)
			else:
				logging.debug('Output {} already exists, skipping extraction.'.format(extracted_dir_path))

			logging.debug('Extracting {} to {} done.'.format(archive_file, target_dir))
		return extracted_dir_path

	def make(self, config, directory, targets=[]):
		logging.debug('Making {}...'.format(self.name))
		config.helper.execute(
			['make', '-j{}'.format(os.cpu_count())]+targets,
			cwd=directory#, stdout=subprocess.PIPE, stderr=subprocess.PIPE
		)
		logging.debug('Making {} done.'.format(self.name))

	def _path_build(self, config):
		return os.path.join(config['directory.source'], '{}-build'.format(self.code))

class Patch(Target):
	def build(self, config):
		if config['skip']:
			return
		patch_file = config['file']
		directory = config['directory']
		logging.debug('Patching {} in {}'.format(patch_file, directory))
		config.helper.execute(
			['patch', '-p0'],
			cwd=directory,
			stdin=open(patch_file, 'rb')
		)

class CreateFile(Target):
	def build(self, config):
		file_name = config['file.name']
		logging.debug('Creating file: {}'.format(file_name))
		directory = os.path.split(file_name)[1]
		if directory:
			os.makedirs(directory, exist_ok=True)
		with open(config['file.name'], 'w') as f:
			f.write(config['file.content'])
		os.chmod(file_name, config['file.mode'])

class ExtractOnly(Target):
	def build(self, config):
		source_dir = self.prepare_source(config)
		config.set('target.{}.source_dir'.format(self.code), source_dir, parent_scope=True)

class HeaderOnly(Target):
	def build(self, config):
		source_dir = self.prepare_source(config)
		if config.has('headers_dir'):
			source_dir = os.path.join(source_dir, config['headers_dir'])
			target_dir = config['directory.include']
			for i in os.listdir(source_dir):
				src = os.path.join(source_dir, i)
				dst = os.path.join(target_dir, i)
				logging.debug('Copying {} -> {}'.format(src, dst))
				if os.path.isdir(src):
					if os.path.isdir(dst):
						shutil.rmtree(dst)
					shutil.copytree(src, dst)
				else:
					if os.path.exists(dst):
						os.remove(dst)
					shutil.copy2(src, dst)

class Autotools(Target):
	def build(self, config):
		source_dir = self.prepare_source(config)
		if config['skip']:
			return
		self.configure(config, source_dir)
		self.make(config, source_dir, ['install'])

	def configure(self, config, source_dir):
		logging.info('Configuring {}...'.format(self.name))
		config.helper.execute(
			[
				'./configure', '--prefix={}'.format(config['directory.root'])
			],
			env={
				'CC': config['c.compiler'],
				'CXX': config['cxx.compiler'],
				'CFLAGS': ' '.join(config.helper.c_compilation_flags()),
				'CXXFLAGS': ' '.join(config.helper.cxx_compilation_flags())
			},
			cwd=source_dir
		)
		logging.info('Configuring {} done.'.format(self.name))

class CMake(Target):
	'''Target that wraps CMake-based source tree'''
	def build(self, config):
		source_dir = self.prepare_source(config)
		build_dir = self._path_build(config)
		stamp_file = os.path.join(build_dir, '.build-done')
		if not os.path.exists(stamp_file):
			self.cmake(config, source_dir, build_dir)
			self.make(config, build_dir, ['install'])
			open(stamp_file, 'w')
		else:
			logging.debug('{} is already built, skipping.'.format(self.name))

	def _cmake_defs(self, config, variables=None):
		variables = variables or config['cmake.variables']
		return [ '-D{}={}'.format(name, config.helper.resolve_value(value)) for name, value in variables.items() ]

	def cmake(self, config, source_dir, build_dir):
		os.makedirs(build_dir, exist_ok=True)

		stamp_file = os.path.join(build_dir, '.build-done')
		if not os.path.exists(stamp_file):
			config.helper.execute(
				[
					'cmake', source_dir
				]+self._cmake_defs(config, {
					'CMAKE_C_COMPILER': config['c.compiler'],
					'CMAKE_CXX_COMPILER': config['cxx.compiler'],
					'CMAKE_C_COMPILER_ID': config.helper.detect_compiler(config['c.compiler'])[0],
					'CMAKE_CXX_COMPILER_ID': config.helper.detect_compiler(config['cxx.compiler'])[0],
					'CMAKE_C_COMPILER_VERSION': config.helper.detect_compiler(config['c.compiler'])[1],
					'CMAKE_CXX_COMPILER_VERSION': config.helper.detect_compiler(config['cxx.compiler'])[1],
					'CMAKE_C_FLAGS': ' '.join(config.helper.c_compilation_flags()),
					'CMAKE_CXX_FLAGS': ' '.join(config.helper.cxx_compilation_flags()),
					'CMAKE_INSTALL_PREFIX': config['directory.root']
				})+self._cmake_defs(config),
				cwd=build_dir
			)
			self.make(config, build_dir, config.get('make.goals', []) + \
					(['VERBOSE=1'] if config.get('verbose', False) else [])
			)
			open(stamp_file, 'w')
		else:
			logging.debug('{} is already built, skipping.'.format(self.name))


#	@property
#	def name(self):
#		return 'CMake-based {}'.format(self.cmake_project_name())
#
#	@property
#	def code(self):
#		return self.cmake_project_name('cmake-{}'.format(self.source_dir.replace('/','-'))).lower()
#
#	def cmake_project_name(self, default=None):
#		try:
#			source_file = os.path.join(self.source_dir, 'CMakeLists.txt')
#			lines = open(source_file, encoding='utf-8').readlines()
#			for i in lines:
#				m = re.match(r'project\(([^\)]+)\)', i)
#				if m:
#					return m.group(1)
#		except:
#			pass
#		return default or 'project from {}'.format(self.source_dir)
