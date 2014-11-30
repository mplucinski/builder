#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import fcntl
import logging
import pty
import os
import subprocess
import sys
import time
import threading
import unittest

class Process:
	@staticmethod
	def set_nonblocking(fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFL)
		flags = flags | os.O_NONBLOCK
		fcntl.fcntl(fd, fcntl.F_SETFL, flags)

	def __init__(self, args, cwd=None, env=None, stdin=False, capture_stdout=False, capture_stderr=False):
		logging.debug('Running {}...'.format(args[0]))
		logging.debug('Parameters: {}'.format(args))
		logging.debug('Working directory: {}'.format(cwd))
		logging.debug('Environment: {}'.format(env))

		self.args = args

		self.buffer_stdout = bytearray()
		self.buffer_stderr = bytearray()

		master_stdout, slave_stdout = pty.openpty()
		master_stderr, slave_stderr = pty.openpty()

		Process.set_nonblocking(master_stdout)
		Process.set_nonblocking(master_stderr)

		self.process = subprocess.Popen(args, bufsize=0, cwd=cwd, env=env,
			stdin=stdin, stdout=slave_stdout, stderr=slave_stderr)

		self._reader_stdout = self.reader(master_stdout, capture_stdout,
									self.buffer_stdout, sys.stdout.buffer)
		self._reader_stderr = self.reader(master_stderr, capture_stderr,
									self.buffer_stderr, sys.stderr.buffer)

	def reader(self, *args):
		stop = threading.Event()
		done = threading.Event()
		thread = threading.Thread(target=self._reader, args=list(args)+[stop, done])
		thread.start()
		return (stop, done)

	def reader_join(self, stop, done):
		stop.set()
		done.wait()

	def communicate(self):
		result = self.process.wait()

		time.sleep(0.1)

		self.reader_join(*self._reader_stdout)
		self.reader_join(*self._reader_stderr)

		logging.debug('Running {} done.'.format(self.args[0]))

		if result != 0:
			raise subprocess.CalledProcessError(result, self.args)

		return (self.buffer_stdout, self.buffer_stderr)

	def _reader(self, fd, capture, buffer, pass_to, stop, done):
		while not stop.is_set():
			try:
				b = os.read(fd, 4096 if capture else 1)
				if capture:
					buffer.extend(b)
				else:
					pass_to.write(b)
					if b'\n' in b:
						pass_to.flush()
			except BlockingIOError:
				pass

		pass_to.flush()

		done.set()

class TestProcess(unittest.TestCase):
	message = 'Well done!'

	def test_process(self):
		executable = sys.executable
		process = Process(
			args=[executable, '-c', 'print("{message}")'.format(message=self.message)],
			capture_stdout=True
		)
		stdout, stderr = process.communicate()
		stdout = stdout.decode('utf-8').strip()
		self.assertEqual(self.message, stdout)

def load_tests(loader, tests, pattern):
	suite = unittest.TestSuite()
	suite.addTests(loader.loadTestsFromTestCase(TestProcess))
	return suite

if __name__ == '__main__':
	unittest.main()