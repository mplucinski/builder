import argparse
import copy
import logging
import pathlib
import shutil
import sys
import tarfile
import unittest

from .base import Profile
from .build import Build
from .config import ConfigDict
from . import targets
from .tests import Skip, TestCase

if not any([ '.xz' in i[1] for i in shutil.get_unpack_formats() ]):
	def _extract_xz(filename, extract_dir):
		try:
			tarobj = tarfile.open(filename)
		except tarfile.TarError as e:
			raise ReadError('{} is not a tar file'.format(filename)) from e

		try:
			tarobj.extractall(extract_dir)
		finally:
			tarobj.close()

	shutil.register_unpack_format('XZ file', ['.xz'], _extract_xz, [], 'Tar file compressed with XZ (LZMA) algorithm')
