#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import pathlib
import tempfile
import urllib
import urllib.request
import unittest

from .base import Scope
from .base import Target
from .config import MockConfig

class Download(Target):
	local_config_keys = {'url'}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

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

class TestDownload(unittest.TestCase):
	def test_download(self):
		example_file = pathlib.Path(__file__)

		download = Download('download_plane',
			url=lambda config: example_file.as_uri()
		)

		target_dir =  tempfile.TemporaryDirectory()

		config = MockConfig(Target.GlobalTargetLevel, {
			'directory.target': target_dir.name
		})

		download._build(config)

		self.assertTrue(str(config['file.output']).endswith(example_file.name))

		target_dir.cleanup()

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestDownload))
	return suite

if __name__ == '__main__':
	unittest.main()