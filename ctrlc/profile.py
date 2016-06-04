from __future__ import absolute_import, print_function

import json
import logging
import os
import os.path
import select
import subprocess
import sys

from .multiplicity import duplicity


class ActionFailed(RuntimeError):
  pass


class Profile(object):
  @classmethod
  def main(cls):
    logging.basicConfig(format="[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.DEBUG)
    if len(sys.argv) < 3:
      print("error: must have 2 at least arguments.", file=sys.stderr)
      cls.usage(sys.stderr)
      sys.exit(1)

    if sys.argv[1] not in {"backup", "restore", "full"}:
      print("error: action must be either backup or restore", file=sys.stderr)
      cls.usage(sys.stderr)
      sys.exit(1)

    if not os.path.isfile(sys.argv[2]):
      print("error: profile path must be a valid file", file=sys.stderr)
      cls.usage(sys.stderr)
      sys.exit(1)

    config = cls.load_config_from_file(sys.argv[2])
    if len(sys.argv) == 4 and sys.argv[3] == "--dry-run":
      config["_dry_run"] = True

    getattr(cls(config, os.path.basename(sys.argv[2])), sys.argv[1])()

  @classmethod
  def usage(cls, f=sys.stdout):
    print("Usage: {} <action> profile-path [--dry-run]".format(sys.argv[0]), file=f)
    print("", file=f)
    print("action:", file=f)
    print("  Either backup, restore, or full as the action you would like to take.", file=f)
    print("", file=f)
    print("profile-path:", file=f)
    print("  The path to the profile that defines this backup/restore job.", file=f)

  @classmethod
  def load_config_from_file(cls, path):
    with open(path) as f:
      config = json.load(f)

    cls.validate_config(config)

    return config

  @classmethod
  def validate_config(cls, config):
    valid = cls.validate_required_fields(config, "src", "dest", "backup_actions", "duplicity_version")
    if not valid:  # exit immediately if required is not in.
      sys.exit(1)

    valid = cls.validate_exists(config["src"])
    if not isinstance(config["backup_actions"], list):  # subsequent checks will error if we don't exit
      print("error: backup_actions must be a list.", file=sys.stderr)
      sys.exit(1)

    for action in config["backup_actions"]:
      valid = cls.validate_action(action)

    for script_path in config.get("cleanup_actions", []):
      valid = cls.validate_exists(script_path)

    installed_versions = duplicity.installed_versions()
    if config["duplicity_version"] not in installed_versions:
      print("error: duplicity version {} is not installed. only {} are installed.".format(config["duplicity_version"], installed_versions))
      valid = False

    if not valid:
      sys.exit(1)

  @classmethod
  def validate_required_fields(cls, config, *fields):
    valid = True
    for field in fields:
      if field not in config:
        print("error: missing field {} in config.".format(field), file=sys.stderr)
        valid = False

    return valid

  @classmethod
  def validate_exists(cls, path):
    if not os.path.exists(path):
      print("error: {} does not exist".format(path), file=sys.stderr)
      return False
    return True

  @classmethod
  def validate_action(cls, action):
    if action.startswith("/"):
      return cls.validate_exists(action)
    elif action.startswith("!"):
      if action not in cls.POSSIBLE_ACTIONS:
        print("error: {} is not a valid action, valid ones are: {}".format(action, cls.POSSIBLE_ACTIONS), file=sys.stderr)
        return False
    else:
      print("error: valid actions must be either an absolute path or an !action, you have: {}".format(action), file=sys.stderr)
      return False
    return True

  POSSIBLE_ACTIONS = {"!backup", "!verify", "!remove_old", "!cleanup"}

  def __init__(self, config, name):
    self.config = config
    self.duplicity = duplicity.Duplicity(config["duplicity_version"])
    self.logger = logging.getLogger(name)

  def backup(self):
    self.execute_actions(self.config["backup_actions"])

  def full(self):
    self.config["_full"] = True
    self.backup()

  def restore(self):
    raise NotImplementedError

  def execute_actions(self, actions):
    try:
      for action in actions:
        self.execute_single_action(action)
    finally:
      # We don't want to recurse because that would be back if cleanup_actions fails
      for action in self.config.get("cleanup_actions", []):
        if action.startswith("!"):  # defensive.
          raise RuntimeError("this should never happen. cleanup_actions should only be scripts")

        self.execute_single_action(action)

  def execute_single_action(self, action):
    if action.startswith("!"):
      getattr(self, "execute_{}".format(action.lstrip("!")))()
    else:
      self.execute_script(action)

  def execute_script(self, script_path):
    self.logger.info("calling script: %s", script_path)
    if self.config.get("_dry_run"):
      return

    p = subprocess.Popen(script_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    self.log_subprocess_stdout_and_stderr_until_done(p)

    if p.returncode != 0:
      self.logger.error("script call failed with exit code %d", p.returncode)
      raise ActionFailed("script call failed with exit code {}".format(p.returncode))

    self.logger.info("script call completed")

  def execute_backup(self):
    arguments = self.options_to_commandline_arguments()
    arguments.append(self.config["src"])
    arguments.append(self.config["dest"])

    if self.config.get("_dry_run"):
      arguments.append("--dry-run")

    if self.config.get("_full"):
      arguments.insert(0, "full")

    self.call_duplicity(arguments)

  def execute_verify(self):
    arguments = ["verify"]
    arguments.extend(self.options_to_commandline_arguments())
    arguments.append(self.config["dest"])
    arguments.append(self.config["src"])
    self.call_duplicity(arguments, self.config.get("_dry_run"))

  def execute_remove_old(self):
    remove_commands = {"remove-older-than", "remove-all-but-n-full", "remove-all-inc-of-but-n-full"}
    for key, value in self.config.items():
      if key in remove_commands:
        arguments = [key, str(value)]

    if not self.config.get("_dry_run"):
      arguments.append("--force")

    arguments.append(self.config["dest"])
    self.call_duplicity(arguments)

  def execute_cleanup(self):
    arguments = ["cleanup", "--force", self.config["dest"]]
    self.call_duplicity(arguments, self.config.get("_dry_run"))

  def call_duplicity(self, arguments, dry_run=False):
    self.logger.debug("calling duplicity with arguments: {}".format(arguments))
    if dry_run:
      self.logger.debug("not actually calling command because dry run")
      return

    os.environ["FTP_PASSWORD"] = self.config.get("ftp_password", "")
    os.environ["PASSPHRASE"] = self.config.get("encrypt_password", "")
    os.environ["SIGN_PASSPHRASE"] = self.config.get("sign_password", "")
    p = self.duplicity.run(*arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    self.log_subprocess_stdout_and_stderr_until_done(p)

    if p.returncode != 0:
      self.logger.error("duplicity failed with exit code %d", p.returncode)
      raise ActionFailed("duplicity failed with exit code {}".format(p.returncode))

    self.logger.debug("duplicity run finished")
    return p.returncode

  def log_subprocess_stdout_and_stderr_until_done(self, p):
    while True:
      reads = [p.stdout.fileno(), p.stderr.fileno()]
      ret = select.select(reads, [], [])

      for fd in ret[0]:
        if fd == p.stdout.fileno():
          line = p.stdout.readline().strip()
          if line:
            self.logger.debug(line)
        elif fd == p.stderr.fileno():
          line = p.stderr.readline().strip()
          if line:
            self.logger.debug(line)

      if p.poll() is not None:
        break

    p.stdout.close()
    p.stderr.close()
    return p

  def options_to_commandline_arguments(self):
    arguments = []
    for key, value in self.config["options"].items():
      arguments.append("--{}".format(key))
      arguments.append(str(value))

    return arguments


def main():
  Profile.main()
