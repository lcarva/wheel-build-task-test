#!/bin/bash
set -euo pipefail

cd "$(git root)"

mapfile -d '' packages < <(find ./packages -maxdepth 1 -mindepth 1 -type d -print0)

for path in "${packages[@]}"; do
    name="$(basename ${path})"
    echo "Processing ${name}"

    requirements_in="${path}/requirements.in"
    requirements_txt="${path}/requirements.txt"
    build_requirements_in="${path}/build-requirements.in"
    build_requirements_txt="${path}/build-requirements.txt"

    echo "${name}" > "${requirements_in}"

    pip-compile "${requirements_in}" --output-file "${requirements_txt}"

    ./bin/pip_find_builddeps.py "${requirements_txt}" --output-file "${build_requirements_in}"

    pip-compile "${build_requirements_in}" --output-file "${build_requirements_txt}"
done
