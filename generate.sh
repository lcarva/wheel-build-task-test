#!/bin/bash
set -euo pipefail

cd "$(git root)"

mapfile -d '' packages < <(find ./packages -maxdepth 1 -mindepth 1 -type d -print0)

for path in "${packages[@]}"; do
    name="$(basename ${path})"
    echo "Processing ${name}"

    pyproject_toml="${path}/pyproject.toml"
    requirements_in="${path}/requirements.in"
    requirements_txt="${path}/requirements.txt"
    build_requirements_in="${path}/requirements-build.in"
    build_requirements_txt="${path}/requirements-build.txt"
    argfile_conf="${path}/argfile.conf"

    printf "[project]\nname = \"${name}_placeholder_wrapper\"\nversion = \"0.0.1\"\n" > "${pyproject_toml}"

    echo "${name}" > "${requirements_in}"

    # TODO: Bring back hashes
    pip-compile "${requirements_in}" --output-file "${requirements_txt}"

    pybuild-deps compile "${requirements_txt}" --output-file "${build_requirements_txt}"

    version="$(grep -ioP '^'${name}'==\K.+' "${requirements_txt}")"

    printf "PACKAGE_NAME=${name}\nPACKAGE_VERSION=${version}\n" > "${argfile_conf}"
done
