#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse

class Target:
	def __init__(self, name):
		self.name = name

	def _build(self):
		self.build()

class Build:
	def _arguments_parser(self):
		parser = argparse.ArgumentParser(description='Builder - Integration-centered build system')
		parser.add_argument('target', nargs='*', type=str, metavar='TARGET',
				help='Target(s) to build (all, if nothing passed)')
		return parser

	def __init__(self):
		self.targets = set()

	def __call__(self, args=None):
		parser = self._arguments_parser()
		args = parser.parse_args(args)

		targets = self.targets
		if args.target:
			targets = []
			for i in args.target:
				try:
					targets.append(next(j for j in self.targets if j.name == i))
				except StopIteration as e:
					raise Exception('Global target "{}" not found'.format(i)) from e

		for target in targets:
			target._build()
