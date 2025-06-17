# Calunga

**Experimental!**

Collection of python package dependencies.

TODO: Add more info.

## Adding a new package

To add a new package to the Calunga python index, simply file a new GitHub issue from the "🌱 Add
Package" template. Once a maintainer reviews the request, they will add the `on-board` label to the
issue. This will trigger the [package-onboarding](./.github/workflows/package-onboarding.yaml)
workflow which in turn generates a new pull request with the required changes. A maintainer will
review and merge the changes as needed.

## Development

Sometimes, it is easier to debug issues locally. To add a package without using the automated
workflow described above, create a directory under the [packages](./packages) directory matching the
package name (always lower case) in [pypi.org](https://pypi.org/), then run the
[generate.sh](./generate.sh) script.

This will create the requirements file for that package.

You'll need `pip-compile` installed which is part of the
[pip-tools](https://pypi.org/project/pip-tools/) package.

[pybuild-deps](https://pypi.org/project/pybuild-deps/) is also required. Until issue
[pybuild-deps#304](https://github.com/hermetoproject/pybuild-deps/issues/304) is resolved, install
it from the fork:

```bash
pip install -e git+https://github.com/lcarva/pybuild-deps.git@handle-no-resolver#egg=pybuild_deps
```
