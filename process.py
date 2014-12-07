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

	def __init__(self, args, cwd=None, env=None, stdin=False,
			echo_stdout=True, echo_stderr=True,
			capture_stdout=False, capture_stderr=False):
		if cwd is not None:
			cwd = str(cwd)

		logging.debug('Running {}...'.format(args[0]))
		logging.debug('Parameters: {}'.format(args))
		logging.debug('Working directory: {}'.format(cwd))
		logging.debug('Environment: {}'.format(env))
		logging.debug('Echo: stdout: {}, stderr: {}'.format(echo_stdout, echo_stderr))

		self.args = args

		self.buffer_stdout = bytearray()
		self.buffer_stderr = bytearray()

		master_stdout, slave_stdout = pty.openpty()
		master_stderr, slave_stderr = pty.openpty()

		Process.set_nonblocking(master_stdout)
		Process.set_nonblocking(master_stderr)

		self.process = subprocess.Popen(args, bufsize=0, cwd=cwd, env=env,
			stdin=stdin, stdout=slave_stdout, stderr=slave_stderr)

		pass_to_stdout = sys.stdout.buffer if echo_stdout else None
		pass_to_stderr = sys.stderr.buffer if echo_stderr else None

		self._reader_stdout = self.reader(master_stdout, capture_stdout,
									self.buffer_stdout, pass_to_stdout)
		self._reader_stderr = self.reader(master_stderr, capture_stderr,
									self.buffer_stderr, pass_to_stderr)

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
				if pass_to is not None:
					pass_to.write(b)
					if b'\n' in b:
						pass_to.flush()
			except BlockingIOError:
				pass

		if pass_to is not None:
			pass_to.flush()

		done.set()

class TestProcess(unittest.TestCase):
	message_out = 'Well done!'
	message_err = 'Really nice!'

	def test_process(self):
		executable = sys.executable
		process = Process(
			args=[executable, '-c', 'import sys;print("{stdout}");sys.stderr.write("{stderr}")'.format(
				stdout=self.message_out, stderr=self.message_err
			)],
			capture_stdout=True,
			capture_stderr=True,
			echo_stdout=False,
			echo_stderr=False
		)
		stdout, stderr = process.communicate()
		stdout = stdout.decode('utf-8').strip()
		stderr = stderr.decode('utf-8').strip()
		self.assertEqual(self.message_out, stdout)
		self.assertEqual(self.message_err, stderr)
