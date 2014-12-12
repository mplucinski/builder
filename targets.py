import copy
import filecmp
import logging
import os
import pathlib
import shutil
import sys
import urllib
import urllib.request
import unittest

from .base import Scope, Target, TargetTestCase
from .config import Config, ConfigDict
from .tests import _fn_log

class Download(Target):
	local_config_keys = {'url', 'directory.target'}
	local_config_defaults = {
		'directory.target': lambda config: config['directory.packages']
	}

	def _file_name(self):
		file_path = urllib.parse.urlparse(self.config['url']).path
		return pathlib.Path(file_path).name

	def _target_file(self):
		return pathlib.Path(self.config['directory.target'])/self._file_name()

	@property
	def outdated(self):
		return not self._target_file().exists()

	def build(self):
		try:
			pathlib.Path(self.config['directory.target']).mkdir(parents=True)
		except FileExistsError:
			pass

		self.log(logging.INFO, 'downloading {} to {}...'.format(self.config['url'], str(self.config['directory.target'])))
		urllib.request.urlretrieve(self.config['url'], str(self._target_file()))

	def post_build(self):
		self.config['file.output', Scope.Local, Target.GlobalTargetLevel] = self._target_file()

class Extract(Target):
	local_config_keys = {'file.name', 'directory.output'}
	local_config_defaults = {
		'directory.output': lambda config: str(pathlib.Path(config['directory.source']))
	}

	def _target_dir(self):
		return pathlib.Path(self.config['directory.output'])

	def build(self):
		file_input = self.config['file.name']
		target_dir = self._target_dir()

		try:
			target_dir.mkdir(parents=True)
		except FileExistsError:
			pass

		self.log(logging.INFO, 'extracting {}...'.format(file_input))
		self.log(logging.DEBUG, 'in {}'.format(target_dir))
		shutil.unpack_archive(str(file_input), str(target_dir))

	def post_build(self):
		self.config['directory.output', Scope.Local, Target.GlobalTargetLevel] = str(self._target_dir())

class Patch(Target):
	local_config_keys = {'file', 'directory', 'strip'}
	local_config_defaults = {'strip': 1}

	def build(self):
		self.call(
			['patch', '-p{}'.format(self.config['strip']), '-i', str(self.config['file'])],
			cwd=str(self.config['directory'])
		)

class Create(Target):
	local_config_keys = {'file.name', 'file.kind', 'file.content', 'file.mode'}
	local_config_defaults = {'file.kind': 'file', 'file.content': None, 'file.mode': None}

	def build(self):
		file_name = pathlib.Path(self.config['file.name'])
		kind = self.config['file.kind']
		if kind == 'file':
			if not file_name.parent.exists():
				file_name.parent.mkdir(parents=True)
			file_name.open('w').write(self.config['file.content'])
		elif kind == 'directory':
			file_name.mkdir(parents=True)
		else:
			raise Exception('Unsupported target kind: {}'.format(kind))
		if self.config['file.mode']:
			file_name.chmod(self.config['file.mode'])

class Copy(Target):
	local_config_keys = {'source', 'destination'}

	@_fn_log(logging.DEBUG-2)
	def _copy(self, source, destination):
		self.log(logging.DEBUG-1, 'copying "{}" -> "{}"'.format(source, destination))
		if source.is_file():
			shutil.copy2(str(source), str(destination))
		else:
			shutil.copytree(str(source), str(destination))

	def build(self):
		source = map(pathlib.Path, self.config['source'])
		destination = pathlib.Path(self.config['destination'])

		try:
			destination.mkdir(parents=True)
		except FileExistsError:
			pass

		for i in source:
			self._copy(i, destination/i.name)

class Autotools(Target):
	local_config_keys = {'directory.source', 'scripts.autoreconf', 'scripts.configure'}
	local_config_defaults = {
		'scripts.autoreconf': lambda config: [shutil.which('autoreconf')],
		'scripts.configure': lambda config: [str(pathlib.Path(config['directory.source'])/'configure')]
	}

	def build(self):
		directory = self.config['directory.source']
		self.call(
			self.config['scripts.autoreconf']+['-f'],
			cwd=directory
		)

		self.call(
			self.config['scripts.configure']+
				['--prefix={}'.format(self.config['directory.root'])],
			cwd=directory,
			env={
				'CC':       self.config['language.c.compiler'],
				'CXX':      self.config['language.c++.compiler'],
				'CFLAGS':   ' '.join(self.config['language.c.flags']),
				'CXXFLAGS': ' '.join(self.config['language.c++.flags'])
			}
		)

class CMake(Target):
	local_config_keys = {'directory.source', 'directory.build', 'directory.target', 'scripts.cmake', 'variables'}
	local_config_defaults = {
		'directory.build': lambda config: str(config['directory.source'])+'-build',
		'directory.target': lambda config: str(config['directory.root']),
		'scripts.cmake': lambda config: [shutil.which('cmake')],
	}

	def build(self):
		source_dir = pathlib.Path(self.config['directory.source'])
		build_dir  = pathlib.Path(self.config['directory.build'])
		target_dir = pathlib.Path(self.config['directory.target'])

		try:
			build_dir.mkdir(parents=True)
		except FileExistsError:
			pass

		self.config['variables.CMAKE_INSTALL_PREFIX'] = target_dir
		self.config['variables.CMAKE_C_COMPILER'] = self.config['language.c.compiler']
		self.config['variables.CMAKE_CXX_COMPILER'] = self.config['language.c++.compiler']
		self.config['variables.CMAKE_C_FLAGS'] = ' '.join(self.config['language.c.flags'])
		self.config['variables.CMAKE_CXX_FLAGS'] = ' '.join(self.config['language.c++.flags'])

		self.call(
			self.config['scripts.cmake']+
				[str(source_dir)]+
				[ '-D{}={}'.format(k, v if v else '""') for k, v in self.config['variables'].items()  ],
			cwd=str(build_dir)
		)

class Make(Target):
	local_config_keys = {'directory.source', 'make.targets', 'scripts.make'}
	local_config_defaults = {
		'make.targets': None,
		'scripts.make': lambda config: [shutil.which('make'), '-j{}'.format(os.cpu_count())]
	}

	def build(self):
		self.call(
			self.config['scripts.make']+([] if self.config['make.targets'] is None else list(self.config['make.targets'])),
			cwd=self.config['directory.source']
		)

class Execute(Target):
	def build(self):
		self.call(
			[self.config['process.name']]+self.config['process.args'],
			cwd=self.config['process.cwd']
		)

class TestDownload(TargetTestCase):
	def test_download(self):
		example_file = pathlib.Path(__file__)

		download, _ = self.mock_target(Download, 'download_plane', config=ConfigDict(
			url=lambda config: example_file.as_uri()
		))
		after_download, after_download_config = self.mock_target(Target, 'after download',
			dependencies={download},
			config=ConfigDict({
				'target.after_download.always_outdated': True
			})
		)

		self.run_target(after_download)
		self.assertTrue(after_download_config.value['target.download_plane.build'])
		downloaded_file = after_download_config.value['target.download_plane.file.output']
		self.assertTrue(str(downloaded_file).endswith(example_file.name))
		self.assertEqual(example_file.open().read(), downloaded_file.open().read())

		self.run_target(after_download)
		self.assertFalse(after_download_config.value['target.download_plane.build'])
		downloaded_file = after_download_config.value['target.download_plane.file.output']
		self.assertTrue(str(downloaded_file).endswith(example_file.name))
		self.assertEqual(example_file.open().read(), downloaded_file.open().read())

class TestExtract(TargetTestCase):
	def assertEqualDirectories(self, left, right):
		diff = filecmp.dircmp(str(left), str(right))
		if len(diff.left_only) != 0:
			raise AssertionError('Only in {}: {}'.format(left, diff.left_only))
		if len(diff.right_only) != 0:
			raise AssertionError('Only in {}: {}'.format(right, diff.right_only))
		if len(diff.diff_files) != 0:
			raise AssertionError('Files {} differ between {} and {}'.format(diff.diff_files, left, right))
		if len(diff.funny_files) != 0:
			raise Exception('Could not compare {} between {} and {}'.format(diff.funny_files, left, right))

	def test_extract(self):
		this_directory = pathlib.Path(__file__).parent
		root_dir = pathlib.Path(self.root_dir.name)

		archive_file = root_dir/'archive'
		archive_file = pathlib.Path(shutil.make_archive(str(archive_file), format='gztar',
				root_dir=str(this_directory)))

		output_dir = root_dir/'extract'

		extract, extract_config = self.mock_target(Extract, 'extract_files', config=ConfigDict({
				'file.name': archive_file,
				'directory.output': output_dir,
		}))
		after_extract, after_extract_config = self.mock_target(Target, 'after extract',
			dependencies={extract}, config=ConfigDict({
				'target.after_extract.always_outdated': True
			})
		)

		self.run_target(after_extract)
		self.assertTrue(after_extract_config.value['target.extract_files.build'])
		self.assertEqual(str(output_dir), after_extract_config.value['target.extract_files.directory.output'])
		self.assertEqualDirectories(output_dir, this_directory)

		self.run_target(after_extract)
		self.assertFalse(after_extract_config.value['target.extract_files.build'])
		self.assertEqual(str(output_dir), after_extract_config.value['target.extract_files.directory.output'])
		self.assertEqualDirectories(output_dir, this_directory)

class TestPatch(TargetTestCase):
	input_file = '''YODA: Code!  Yes.  A programmer's strength flows from code
      maintainability.  But beware of Perl.  Terse syntax... more
      than one way to do it...  default variables.  The dark side
      of code maintainability are they.  Easily they flow, quick
      to join you when code you write.  If once you start down the
      dark path, forever will it dominate your destiny, consume
      you it will.
LUKE: Is Perl better than Python?
YODA: Yes... yes... yes.  Quicker, easier, more maintainable.
LUKE: But how will I know why Python is better than Perl?
YODA: You will know.  When your code you try to read six months
      from now.'''

	patch = '''--- a/{file_name}\t
+++ b/{file_name}\t
@@ -7,5 +7,5 @@
       you it will.
 LUKE: Is Perl better than Python?
-YODA: Yes... yes... yes.  Quicker, easier, more maintainable.
+YODA: No... no... no.  Quicker, easier, more seductive.
 LUKE: But how will I know why Python is better than Perl?
 YODA: You will know.  When your code you try to read six months
'''

	output_file = '''YODA: Code!  Yes.  A programmer's strength flows from code
      maintainability.  But beware of Perl.  Terse syntax... more
      than one way to do it...  default variables.  The dark side
      of code maintainability are they.  Easily they flow, quick
      to join you when code you write.  If once you start down the
      dark path, forever will it dominate your destiny, consume
      you it will.
LUKE: Is Perl better than Python?
YODA: No... no... no.  Quicker, easier, more seductive.
LUKE: But how will I know why Python is better than Perl?
YODA: You will know.  When your code you try to read six months
      from now.'''

	def test_patch(self):
		temp = pathlib.Path(self.root_dir.name)
		input_file = temp/'The Empire Strikes Back.txt'
		input_file.open('w').write(self.input_file)
		patch_file = temp/'The Empire Strikes Back.patch'
		patch_file.open('w').write(self.patch.format(file_name=input_file.name))

		patch, _ = self.mock_target(Patch, 'patch_files', config=ConfigDict(
			directory=temp,
			file=patch_file
		))
		self.run_target(patch)

		output = input_file.open().read()
		self.assertEqual(self.output_file, output)

class TestCreate(TargetTestCase):
	content = '''<refrigerator> [to dishwasher] "...so I'm inclined to believe that
capping the capital gains tax at 13% would enable sustainable
growth in the GNP of over 4%."'''
	file_name = 'waiting for God.txt'
	directory_name = 'example'

	def test_create_file(self):
		root = pathlib.Path(self.root_dir.name)
		file_name = root/self.file_name

		create, _ = self.mock_target(Create, 'create_file', config=ConfigDict(
			file=ConfigDict(
				name=file_name,
				content=self.content
			)
		))
		self.run_target(create)

		output = file_name.open().read()
		self.assertEqual(self.content, output)

	def test_create_directory(self):
		root = pathlib.Path(self.root_dir.name)
		directory_name = root/self.directory_name

		create, _ = self.mock_target(Create, 'create_file', config=ConfigDict(
			file=ConfigDict(
				name=directory_name,
				kind='directory'
			)
		))
		self.run_target(create)

		self.assertTrue(directory_name.is_dir())

	def test_create_file_in_directory(self):
		root = pathlib.Path(self.root_dir.name)
		directory_name = root/self.directory_name
		file_name = directory_name/self.file_name

		create, _ = self.mock_target(Create, 'create_dir_and_file', config=ConfigDict(
			file=ConfigDict(
				name=str(file_name),
				content=self.content
			)
		))
		self.run_target(create)

		self.assertTrue(directory_name.is_dir())
		self.assertEqual(self.content, file_name.open().read())

class TestCopy(TargetTestCase):
	def test_copy(self):
		this_directory = pathlib.Path(__file__).parent
		temp = pathlib.Path(self.root_dir.name)

		copy, _ = self.mock_target(Copy, 'copy_files', config=ConfigDict(
			source=lambda config: this_directory.glob('*.py'),
			destination=temp
		))
		self.run_target(copy)

		for i in temp.iterdir():
			if i.is_file():
				j = this_directory/i.name
				self.assertEqual(j.open().read(), i.open().read())

class TestAutotools(TargetTestCase):
	def test_autotools(self):
		root_dir = pathlib.Path(self.root_dir.name)
		(root_dir/'default'/'src').mkdir(parents=True)
		output_file = root_dir/'output.log'

		autotools, _ = self.mock_target(Autotools, 'autotools_project', config=ConfigDict(
			scripts=ConfigDict(
				autoreconf=[shutil.which('python3'), '-c', 'open("{}", "a").write("Autoreconf\\n")'.format(output_file)],
				configure=[shutil.which('python3'), '-c', 'open("{}", "a").write("Configure\\n")'.format(output_file)]
			)
		))
		self.run_target(autotools, build_config=ConfigDict(
			language=ConfigDict({
				'c': ConfigDict(
					compiler='',
					flags=[]
				),
				'c++': ConfigDict(
					compiler='',
					flags=[]
				)
			})
		))

		output = output_file.open().read()
		self.assertEqual('Autoreconf\nConfigure\n', output)

class TestCMake(TargetTestCase):
	def test_cmake(self):
		root_dir = pathlib.Path(self.root_dir.name)
		output_file = root_dir/'output.log'

		cmake_mock = '''import sys
open("{}", "a").write("CMake\\n"+repr(sys.argv[2:]))
'''.format(output_file)

		cmake, _ = self.mock_target(CMake, 'cmake_project', config=ConfigDict(
			scripts=ConfigDict(
				cmake=[shutil.which('python3'), '-c', cmake_mock]
			)
		))
		self.run_target(cmake, build_config=ConfigDict(
			language=ConfigDict({
				'c': ConfigDict(
					compiler='',
					flags=[]
				),
				'c++': ConfigDict(
					compiler='',
					flags=[]
				)
			})
		))

		output = output_file.open().read()
		self.assertTrue(output.startswith('CMake'))
		output = output[6:].strip()
		output = eval(output)

		defines = { i for i in output if i.startswith('-D') }

		self.assertEqual({
			'-DCMAKE_INSTALL_PREFIX={}'.format(root_dir/'default'),
			'-DCMAKE_C_FLAGS=""',
			'-DCMAKE_CXX_FLAGS=""',
			'-DCMAKE_C_COMPILER=""',
			'-DCMAKE_CXX_COMPILER=""'
		}, defines)

class TestMake(TargetTestCase):
	def test_make(self):
		temp = pathlib.Path(self.root_dir.name)
		output_file = temp/'output.log'

		targets = ['a', 'b', 'c']
		make, _ = self.mock_target(Make, 'make_target', config=ConfigDict({
			'directory.source': temp,
			'make.targets': targets,
			'scripts.make': lambda config: [
				shutil.which('python3'), '-c',
				'open("{}", "w") .write("Make\\n{}\\n")'.format(
					output_file, config['make.targets']
				)
			]
		}))
		self.run_target(make)

		self.assertEqual('Make\n{}\n'.format(repr(targets)), output_file.open().read())

class TestExecute(TargetTestCase):
	def test_execute(self):
		temp = pathlib.Path(self.root_dir.name)
		output_file = temp/'output.log'

		execute, _ = self.mock_target(Execute, 'exec_target', config=ConfigDict({
			'process.name': sys.executable,
			'process.args': [
				'-c',
				'open("{}", "w").write("Execute in {}\\n")'.format(output_file, temp)
			],
			'process.cwd': temp
		}))
		self.run_target(execute)

		self.assertEqual('Execute in {}\n'.format(temp), output_file.open().read())
