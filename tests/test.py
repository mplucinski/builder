#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import sys
import unittest

sys.path.append(str((pathlib.Path(__file__).parent / '..' / '..').resolve()))

import builder

if __name__ == '__main__':
	unittest.main()
