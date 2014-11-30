#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

class Download(Target):
	local_config_keys = {'url'}

	def build(self, config):
		logging.info('Downloading {}'.format(config))

		file_path = urllib.parse.urlparse(config['url']).path
		file_name = pathlib.Path(file_path).name

		target_dir = pathlib.Path(config['directory.target'])

		try:
			target_dir.mkdir(parents=True)
		except FileExistsError:
			pass

		target_file = target_dir/file_name

		self.log(logging.INFO, 'downloading {}...'.format(config['url']))
		urllib.request.urlretrieve(config['url'], str(target_file))

		config['file.output', Scope.Global, Target.GlobalTargetLevel] = target_file

class Extract(Target):
	local_config_keys = {'file.input'}

	def build(self, config):
		file_input = config['file.input']
		target_dir = pathlib.Path(config['directory.output'])

		try:
			target_dir.mkdir(parents=True)
		except FileExistsError:
			pass

		self.log(logging.INFO, 'extracting {}...'.format(file_input))
		shutil.unpack_archive(file_input, str(target_dir))

class TestDownload(unittest.TestCase):
	def test_download(self):
		example_file = pathlib.Path(__file__)
		target_dir = tempfile.TemporaryDirectory()

		download = Download('download_plane',
			url=lambda config: example_file.as_uri()
		)
		config = MockConfig(Target.GlobalTargetLevel, {
			'directory.target': target_dir.name
		})
		download._build(config)

		self.assertTrue(str(config['file.output']).endswith(example_file.name))
		target_dir.cleanup()

class TestExtract(unittest.TestCase):
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
		archive_file = shutil.make_archive(str(archive_file), format='gztar',
				root_dir=str(this_directory))

		extract = Extract('extract_files', **{
				'file.input': archive_file,
				'directory.output': temp_dir_out_path
		})
		config = MockConfig(Target.GlobalTargetLevel, {

		})
		extract._build(config)

		self.assertEqualDirectories(this_directory, temp_dir_out_path)

		temp_dir.cleanup()
		temp_dir_out.cleanup()

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestDownload))
	suite.addTests(loader.loadTestsFromTestCase(TestExtract))
	return suite

if __name__ == '__main__':
	unittest.main()