#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
import filecmp
import logging
import pathlib
import shutil
import tempfile
import urllib
import urllib.request
import unittest

from .base import samefile
from .base import Scope
from .base import Target
from .config import MockConfig
from .tests import TestCase

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
		return not self._target_file().is_file()

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
			self.config['scripts.configure'],
			cwd=directory
		)

class TestDownload(TestCase):
	def test_download(self):
		example_file = pathlib.Path(__file__)
		target_dir = tempfile.TemporaryDirectory()

		download = self.mock_target(Download, 'download_plane',
			url=lambda config: example_file.as_uri()
		)
		config = MockConfig(Target.GlobalTargetLevel, {
			'directory.target': target_dir.name
		})
		config_1 = copy.deepcopy(config)
		download._build(config_1)

		self.assertTrue(str(config_1['target.download_plane.file.output']).endswith(example_file.name))
		self.assertTrue(config_1['target.download_plane.build'])

		config_2 = copy.deepcopy(config)
		download._build(config_2)
		self.assertTrue(str(config_2['target.download_plane.file.output']).endswith(example_file.name))
		self.assertFalse(config_2['target.download_plane.build'])

		target_dir.cleanup()

class TestExtract(TestCase):
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
		temp_dir = tempfile.TemporaryDirectory()
		temp_dir_out = tempfile.TemporaryDirectory()
		temp_dir_out_path = pathlib.Path(temp_dir_out.name)
		archive_file = pathlib.Path(temp_dir.name)/'archive'
		archive_file = pathlib.Path(shutil.make_archive(str(archive_file), format='gztar',
				root_dir=str(this_directory)))
		stamps_path = tempfile.TemporaryDirectory()

		extract = self.mock_target(Extract, 'extract_files', **{
				'file.name': archive_file,
				'directory.output': temp_dir_out_path,
				'directory.stamps': stamps_path.name
		})
		config = MockConfig(Target.GlobalTargetLevel, {})
		config_1 = copy.deepcopy(config)
		extract._build(config_1)
		self.assertTrue(config_1['target.extract_files.build'])
		self.assertEqual(str(temp_dir_out_path), config_1['target.extract_files.directory.output'])

		self.assertEqualDirectories(this_directory, temp_dir_out_path)

		config_2 = copy.deepcopy(config)
		extract._build(config_2)
		self.assertFalse(config_2['target.extract_files.build'])
		self.assertEqual(str(temp_dir_out_path), config_2['target.extract_files.directory.output'])

		self.assertEqualDirectories(this_directory, temp_dir_out_path)

		stamps_path.cleanup()
		temp_dir.cleanup()
		temp_dir_out.cleanup()

class TestPatch(TestCase):
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
		temp_dir = tempfile.TemporaryDirectory()
		temp = pathlib.Path(temp_dir.name)
		input_file = temp/'The Empire Strikes Back.txt'
		input_file.open('w').write(self.input_file)
		patch_file = temp/'The Empire Strikes Back.patch'
		patch_file.open('w').write(self.patch.format(file_name=input_file.name))

		patch = self.mock_target(Patch, 'patch_files', **{
			'directory': temp,
			'file': patch_file
		})
		config = MockConfig(Target.GlobalTargetLevel, {})
		patch._build(config)

		output = input_file.open().read()
		self.assertEqual(self.output_file, output)
		temp_dir.cleanup()

class TestCreate(TestCase):
	content = '''<refrigerator> [to dishwasher] "...so I'm inclined to believe that
capping the capital gains tax at 13% would enable sustainable
growth in the GNP of over 4%."'''
	file_name = 'waiting for God.txt'
	directory_name = 'example'

	def test_create_file(self):
		temp_dir = tempfile.TemporaryDirectory()
		temp = pathlib.Path(temp_dir.name)
		file_name = temp/self.file_name

		create = self.mock_target(Create, 'create_file',
			file={
				'name': file_name,
				'content': self.content
			}
		)
		config = MockConfig(Target.GlobalTargetLevel)
		create._build(config)

		output = file_name.open().read()
		self.assertEqual(self.content, output)
		temp_dir.cleanup()

	def test_create_directory(self):
		temp_dir = tempfile.TemporaryDirectory()
		temp = pathlib.Path(temp_dir.name)
		directory_name = temp/self.directory_name

		create = self.mock_target(Create, 'create_file',
			file={
				'name': directory_name,
				'kind': 'directory'
			}
		)
		config = MockConfig(Target.GlobalTargetLevel)
		create._build(config)

		self.assertTrue(directory_name.is_dir())
		temp_dir.cleanup()

	def test_create_file_in_directory(self):
		temp_dir = tempfile.TemporaryDirectory()
		temp = pathlib.Path(temp_dir.name)

		directory_name = temp/self.directory_name
		file_name = directory_name/self.file_name

		create = self.mock_target(Create, 'create_dir_and_file',
			file={
				'name': str(file_name),
				'content': self.content
			}
		)
		config = MockConfig(Target.GlobalTargetLevel)
		create._build(config)

		self.assertTrue(directory_name.is_dir())
		self.assertEqual(self.content, file_name.open().read())

		temp_dir.cleanup()

class TestAutotools(TestCase):
	def test_autotools(self):
		temp_dir = tempfile.TemporaryDirectory()
		source_dir = pathlib.Path(temp_dir.name)
		output_file = source_dir/'output.log'

		autotools = self.mock_target(Autotools, 'autotools_project', **{
			'directory': {
				'source': source_dir
			},
			'scripts': {
				'autoreconf': [shutil.which('python3'), '-c', 'open("{}", "a").write("Autoreconf\\n")'.format(output_file)],
				'configure': [shutil.which('python3'), '-c', 'open("{}", "a").write("Configure\\n")'.format(output_file)]
			}
		})
		config = MockConfig(Target.GlobalTargetLevel)
		autotools._build(config)

		output = output_file.open().read()
		self.assertEqual('Autoreconf\nConfigure\n', output)

		temp_dir.cleanup()

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestDownload))
	suite.addTests(loader.loadTestsFromTestCase(TestExtract))
	suite.addTests(loader.loadTestsFromTestCase(TestPatch))
	suite.addTests(loader.loadTestsFromTestCase(TestCreate))
	suite.addTests(loader.loadTestsFromTestCase(TestAutotools))
	return suite

if __name__ == '__main__':
	unittest.main()