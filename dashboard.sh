#!/bin/bash

set -euo pipefail

DEBUG="${DEBUG:-0}"
if [[ "$DEBUG" == "1" ]]; then
    set -x
fi

# Use this if the build is too old and it will no longer pass Conforma validation during release.
PREFER_REBUILD_OVER_RELEASE="${PREFER_REBUILD_OVER_RELEASE:-0}"

PYPI_INDEX_URL='https://console.redhat.com/api/pulp-content/public-calunga/mypypi/simple'

function package_version() {
    local pkg_dir="$1"
    local pkg_name="$(basename "$pkg_dir")"
    local req_file="$pkg_dir/requirements.txt"
    grep -ioP '^'${pkg_name}'==\K.+\w' "${req_file}"
}

function index_version() {
    local pkg_name="$1"

    # Pulp's python endpoint doesn't yet handle the `/json` API, so we workaround this by parsing
    # the HTML output: https://github.com/pulp/pulp_python/issues/897
    html_content=$(curl -sL "https://console.redhat.com/api/pulp-content/public-calunga/mypypi/simple/${pkg_name}/")
    if [[ "$html_content" == *"404: Not Found"* ]]; then
        echo "MISSING"
        return
    fi
    echo "$html_content" | yq --input-format=xml \
        '[.html.body.a[]["+content"] | select(.  == "*.tar.gz") | sub(".tar.gz", "") | split("-") | .[-1]] | sort | .[-1]'
}

function latest_built_commit_id() {
    local pkg_name="$1"
    oc get component "${pkg_name}" -o yaml | yq .status.lastBuiltCommit
}

function latest_commit_id() {
    local pkg_dir="$1"
    git rev-list -1 HEAD -- "${pkg_dir}"
}

function find_snapshot_for_commit_id() {
    local commit_id="$1"
    local snapshot_name="${pkg_name}-${commit_id}"
    oc get snapshot \
        -l pac.test.appstudio.openshift.io/sha="${commit_id}" \
        -o jsonpath='{.items[0].metadata.name}'
}

function release_snapshot() {
    local snapshot_name="$1"
    oc create -f - <<- EOF
		apiVersion: appstudio.redhat.com/v1alpha1
		kind: Release
		metadata:
		  generateName: managed-
		spec:
		  releasePlan: test-calunga
		  snapshot: $snapshot_name
		  data:
		    releaseNotes:
		    references: ""
		    synopsis: ""
		    topic: ""
		    description: ""
		EOF
}

for pkg_dir in $(find packages -mindepth 1 -maxdepth 1 -type d | sort); do
    pkg_name=$(basename "$pkg_dir")

    # Get the version of the package in git.
    git_version="$(package_version "${pkg_dir}")"

    # Now get the version of the package in the index.
    index_version="$(index_version "${pkg_name}")"

    if [[ "$git_version" == "$index_version" ]]; then
        continue
    fi

    built_commit_id="$(latest_built_commit_id "${pkg_name}")"
    commit_id="$(latest_commit_id "${pkg_dir}")"

    # The build pipeline wasn't triggered for this commit.
    if [[ "$built_commit_id" != "$commit_id" ]]; then
        echo "Commit mismatch for $pkg_name: built commit id is $built_commit_id, commit id is $commit_id - needs rebuild"
        ./mark-for-rebuild.sh "${pkg_name}"
        continue
    fi

    if [[ "$PREFER_REBUILD_OVER_RELEASE" == "1" ]]; then
        echo "Rebuild preferred over release for $pkg_name"
        ./mark-for-rebuild.sh "${pkg_name}"
        continue
    fi

    # A build exists, but it has not been released.
    snapshot_name="$(find_snapshot_for_commit_id "${commit_id}")"
    echo "Snapshot for $pkg_name: $snapshot_name - needs release"
    release_snapshot "${snapshot_name}"
done
