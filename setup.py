from setuptools import setup, find_packages


setup(
  name="ctrlc",
  version="0.0.1",
  packages=find_packages(exclude=["tests*"]),
  author="Shuhao Wu",
  author_email="shuhao@shuhaowu.com",
  entry_points={
    "console_scripts": [
      "multiplicity = ctrlc.multiplicity.cmds.manager:main",
      "ctrlc-duplicity = ctrlc.multiplicity.cmds.launcher:main",
      "ctrlc = ctrlc.profile:main"
    ]
  },
  data_files=[
    (
      "/opt/duplicities/.trustdb",
      [
        "data/duplicity-trustdb/pubring.gpg",
        "data/duplicity-trustdb/secring.gpg",
        "data/duplicity-trustdb/trustdb.gpg"
      ]
    ),
    (
      "/opt/duplicities/.src",
      [
        "data/src_directory/readme"
      ]
    )
  ],
  test_suite="tests"
)
