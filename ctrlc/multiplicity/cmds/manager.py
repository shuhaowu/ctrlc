from __future__ import absolute_import, print_function

import logging
import sys

from ctrlc import multiplicity

logging.basicConfig(format="[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.DEBUG)


def main():
  if len(sys.argv) == 1:
    command = COMMANDS["help"]
  else:
    command = COMMANDS.get(sys.argv[1], COMMANDS["help"])

  return command()


def install():
  if len(sys.argv) < 3:
    print("ERROR: must provide a version", file=sys.stderr)
    sys.exit(1)

  version = sys.argv[2]
  d = multiplicity.Duplicity(version)
  d.install()
  return 0


def uninstall():
  if len(sys.argv) < 3:
    print("ERROR: must provide a version", file=sys.stderr)
    sys.exit(1)

  version = sys.argv[2]
  d = multiplicity.Duplicity(version)
  d.uninstall()
  return 0


def versions():
  print("Installed versions:")
  print("")
  for version in multiplicity.installed_versions():
    print(" - {}".format(version))
  return 0


def usage(f=sys.stdout):
  print("Commands available:", file=f)
  print("", file=f)
  print(" - install {version}", file=f)
  print(" - uninstall {version}", file=f)
  print(" - versions", file=f)
  return 0


COMMANDS = {
  "install": install,
  "uninstall": uninstall,
  "versions": versions,
  "help": usage
}


if __name__ == "__main__":
  main()
