#!/bin/bash
#
# Used to find any packages that are used as dependencies in the packages already added to calunga.
# The goal is to create a full self-contained index.
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

comm -13 \
    <(ls -1 packages/) \
    <(cat packages/*/requirements*.txt | grep '==' | cut -d= -f1 | sort -u | tr '[:upper:]' '[:lower:]')