#!/bin/bash
#
# Add a package to the calunga catalog.
#
# Usage:
#   add-package.sh <package-name>
#

set -euo pipefail

PKG_NAME=$1

cd "$(dirname "${BASH_SOURCE[0]}")"

git checkout main
git pull

# We want this to fail if the directory already exists which implies the package is either already
# onboarded or something went wrong on a previous run.
mkdir "packages/${PKG_NAME}"

./generate.sh

echo
echo "==================================================="
echo "Package dependencies ${PKG_NAME} has been resolved."
echo "==================================================="

BUILD="${BUILD:-1}"
if [[ "${BUILD}" -eq 1 ]]; then
    echo "Building package locally"
    ./build-locally.sh "${PKG_NAME}"
fi

echo 'Creating Konflux resources for package'
kustomize build "konflux/components/${PKG_NAME}" | oc -n calunga-tenant apply -f -

echo 'Creating a pull request for onboarding the package'

BRANCH_NAME="add-${PKG_NAME}"
git checkout -b "${BRANCH_NAME}"
git add .
git commit -m "Onboard ${PKG_NAME} package" --signoff
git push --set-upstream origin "${BRANCH_NAME}"
gh pr create --base main --head "${BRANCH_NAME}" --fill
