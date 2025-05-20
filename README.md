# Calunga

**Experimental!**

Collection of python package dependencies.

TODO: Add more info.

## Usage

To add a new package, create a directory under the [packages](./packages) directory matching the
package name (case-sensitive) in [pypi.org](https://pypi.org/), then run the
[generate.sh](./generate.sh) script.

This will create the requirements file for that package. (Currently, only the latest version is
supported.)

You'll need `pip-compile` installed which is part of the
[pip-tools](https://pypi.org/project/pip-tools/) package.
