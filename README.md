# Calunga

**Experimental!**

Collection of python package dependencies.

TODO: Add more info.

## Usage

To add a new package, create a directory under the [packages](./packages) directory matching the
package name (always lower case) in [pypi.org](https://pypi.org/), then run the
[generate.sh](./generate.sh) script.

This will create the requirements file for that package. (Currently, only the latest version is
supported.)

You'll need `pip-compile` installed which is part of the
[pip-tools](https://pypi.org/project/pip-tools/) package.

[pybuild-deps](https://pypi.org/project/pybuild-deps/) is also required. Until issue
[pybuild-deps#304](https://github.com/hermetoproject/pybuild-deps/issues/304) is resolved, install
it from the fork:

```bash
pip install -e git+https://github.com/lcarva/pybuild-deps.git@handle-no-resolver#egg=pybuild_deps
```
