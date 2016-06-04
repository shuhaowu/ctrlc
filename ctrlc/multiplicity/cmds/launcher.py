from __future__ import absolute_import, print_function

import os
import sys

from ..duplicity import Duplicity

POSSIBLE_FILES = [
  "/etc/ctrlc/active-duplicity-version",
  "{home}/.config/ctrlc/active-duplicity-version".format(home=os.getenv("HOME")),
]


def main():
  version = None
  for fn in POSSIBLE_FILES:
    if os.path.isfile(fn):
      with open(fn) as f:
        version = f.read().strip()
        if version:
          break

  version = version or os.getenv("CTRLC_DUPLICITY_VERSION")
  if not version:
    print("ERROR: $CTRLC_DUPLICITY_VERSION is not set, cannot continue", file=sys.stderr)
    sys.exit(1)

  d = Duplicity(version)

  if not d.is_installed():
    print("ERROR: version {0} is not installed, try: `ctrlc-duplicity-manager install {0}`".format(version), file=sys.stderr)
    sys.exit(1)

  return d.run(*sys.argv[1:]).wait()


if __name__ == "__main__":
  main()
