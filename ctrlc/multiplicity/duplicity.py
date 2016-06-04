from __future__ import absolute_import, print_function

import logging
import os
import os.path
import subprocess
import shutil
import sys

from ..utils import chdir, mkdir_p

try:
  from urllib.request import urlopen
except ImportError:
  from urllib2 import urlopen


GPG = "/usr/bin/gpg"
TAR = "/bin/tar"

BASE_INSTALL_PATH = "/opt/duplicities"

BASE_INSTALL_PATH_CONFIGS = [
  "/etc/ctrlc/duplicities-base",
  "{home}/.config/ctrlc/duplicities-base",
]

for path in BASE_INSTALL_PATH_CONFIGS:
  if os.path.isfile(path):
    with open(path) as f:
      base_path = f.read().strip()
      if not os.path.isdir(base_path):
        print("WARNING: {} is not a valid directory, ignoring".format(base_path), file=sys.stderr)
      else:
        BASE_INSTALL_PATH = base_path

BASE_INSTALL_PATH = os.getenv("CTRLC_DUPLICITY_BASE") or BASE_INSTALL_PATH
SRC_DIRECTORY = os.path.join(BASE_INSTALL_PATH, ".src")
GNUPG_TRUST_DIRECTORY = os.path.join(BASE_INSTALL_PATH, ".trustdb")


def installed_versions():
  versions = os.listdir(BASE_INSTALL_PATH)
  return filter(lambda n: not n.startswith("."), versions)


class Duplicity(object):
  DOWNLOAD_URL = "https://launchpad.net/duplicity/{series}/{version}/+download/duplicity-{version}.tar.gz"
  TARBALL_NAME = "duplicity-{version}.tar.gz"
  DOWNLOAD_GPG_KEY_ID = "96A9EA9C"

  def __init__(self, version):
    self.version = version
    self.series = version.split(".")
    self.series = ".".join(self.series[:2]) + "-series"
    self.app_download_url = self.DOWNLOAD_URL.format(series=self.series, version=self.version)
    self.sig_download_url = self.app_download_url + ".sig"
    self.install_path = os.path.join(BASE_INSTALL_PATH, self.version)

    self.logger = logging.getLogger("duplicitymanager")

  def download(self):
    self.logger.info("downloading duplicity {} from {}".format(self.version, self.app_download_url))
    response = urlopen(self.app_download_url)
    tarball_filename = os.path.join(SRC_DIRECTORY, self.TARBALL_NAME.format(version=self.version))
    with open(tarball_filename, "wb") as f:
      while True:
        data = response.read(8192)
        if data:
          f.write(data)
        else:
          break

    response = urlopen(self.sig_download_url)
    sig_filename = os.path.join(SRC_DIRECTORY, self.TARBALL_NAME.format(version=self.version) + ".sig")
    with open(sig_filename, "wb") as f:
      while True:
        data = response.read(8192)
        if data:
          f.write(data)
        else:
          break

    self.logger.info("verifying signature from {}".format(self.sig_download_url))
    try:
      subprocess.check_call([GPG, "--verify", sig_filename], env={"GNUPGHOME": GNUPG_TRUST_DIRECTORY})
    except subprocess.CalledProcessError as e:
      self.logger.critical("cannot verify {}: {}".format(tarball_filename, e))
      raise RuntimeError("cannot verify {}: {}".format(tarball_filename, e))

  def install(self):
    self.download()
    with chdir(SRC_DIRECTORY):
      tarball_filename = self.TARBALL_NAME.format(version=self.version)
      duplicity_directory_name = tarball_filename.replace(".tar.gz", "")
      if os.path.isdir(duplicity_directory_name):
        self.logger.debug("removing previous {}".format(duplicity_directory_name))
        shutil.rmtree(duplicity_directory_name)

      self.logger.info("extracting %s", tarball_filename)
      subprocess.check_call([TAR, "xzf", tarball_filename])

      if not os.path.isdir(duplicity_directory_name):
        raise RuntimeError("this is a bug: directory {} not created as expected".format(duplicity_directory_name))

    mkdir_p(self.install_path)

    with chdir(os.path.join(SRC_DIRECTORY, duplicity_directory_name)):
      self.logger.info("installing duplicity %s", self.version)
      subprocess.check_call([
        "/usr/bin/env", "python2", "setup.py", "install",
        "--prefix={}".format(self.install_path),
        "--install-lib={}".format(os.path.join(self.install_path, "site-packages"))
      ])

      self.logger.info("installation of {} complete!".format(self.version))

  def is_installed(self):
    return os.path.exists(self.install_path)

  def uninstall(self):
    self.logger.info("uninstalling duplicity %s", self.version)
    shutil.rmtree(self.install_path)

  def run(self, *args, **kwargs):
    kwargs.setdefault("env", {})
    kwargs["env"].update(os.environ.copy())
    kwargs["env"].update({
      "PYTHONPATH": "{base}/{version}/site-packages".format(base=BASE_INSTALL_PATH, version=self.version),
      "PATH": "{base}/{version}/bin".format(base=BASE_INSTALL_PATH, version=self.version)
    })

    original_pythonpath = os.getenv("PYTHONPATH")
    if original_pythonpath:
      kwargs["env"]["PYTHONPATH"] += ":" + original_pythonpath

    original_path = os.getenv("PATH")
    if original_path:
      kwargs["env"]["PATH"] += ":" + original_path

    executable = os.path.join(BASE_INSTALL_PATH, self.version, "bin", "duplicity")

    cmd = [executable]
    cmd.extend(args)

    self.logger.debug("executing %s with PYTHONPATH=%s", cmd, kwargs["env"]["PYTHONPATH"])
    return subprocess.Popen(cmd, **kwargs)
