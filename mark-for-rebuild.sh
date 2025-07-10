#!/bin/bash

set -euo pipefail

PACKAGE_NAME="$1"

ARGFILE_CONF="packages/${PACKAGE_NAME}/argfile.conf"

# Remove previous force rebuild comment
sed -i '/^# Add comment to force rebuild/d' "$ARGFILE_CONF"

echo "# Add comment to force rebuild, $(date -u --rfc-3339=seconds)" >> "$ARGFILE_CONF"
