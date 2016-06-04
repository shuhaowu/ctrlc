from __future__ import absolute_import, print_function

from contextlib import contextmanager
import errno
import os
import os.path


def mkdir_p(path):
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else:
      raise


@contextmanager
def chdir(path):
  old_cwd = os.getcwd()
  try:
    os.chdir(path)
    yield
  finally:
    os.chdir(old_cwd)
