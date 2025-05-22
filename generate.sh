#!/bin/bash
set -euo pipefail

cd "$(git root)"

mapfile -d '' packages < <(find ./packages -maxdepth 1 -mindepth 1 -type d -print0 | sort -z)

all_kustomization_yaml='konflux/kustomization.yaml'
packages_on_push_yaml='.tekton/packages-on-push.yaml'
packages_on_pull_request_yaml='.tekton/packages-on-pull-request.yaml'

cat > "${all_kustomization_yaml}" << EOF
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
EOF

function generate_package_wrapper() {
    local name
    local path

    name=$1
    path=$2

    pyproject_toml="${path}/pyproject.toml"
    requirements_in="${path}/requirements.in"
    requirements_txt="${path}/requirements.txt"
    build_requirements_in="${path}/requirements-build.in"
    build_requirements_txt="${path}/requirements-build.txt"
    argfile_conf="${path}/argfile.conf"

    cat > "${pyproject_toml}" <<- EOF
		[project]
		name = "${name}_placeholder_wrapper"
		version = "0.0.1"
		EOF

    echo "${name}" > "${requirements_in}"

    pip-compile --generate-hashes "${requirements_in}" --output-file "${requirements_txt}"

    pybuild-deps compile --generate-hashes "${requirements_txt}" --output-file "${build_requirements_txt}"

    version="$(grep -ioP '^'${name}'==\K.+\w' "${requirements_txt}")"

    cat > "${argfile_conf}" <<- EOF
		PACKAGE_NAME=${name//-/_}
		PACKAGE_VERSION=${version}
		EOF
}

function generate_konflux_resources() {
    local name
    name=$1

    mkdir -p "konflux/${name}"
    kustomization_yaml="konflux/${name}/kustomization.yaml"
    set_resource_name_yaml="konflux/${name}/set-resource-name.yaml"
    set_package_name_yaml="konflux/${name}/set-package-name.yaml"

    cp 'konflux/base/pkg-kustomization.yaml' "${kustomization_yaml}"

    cat > "${set_resource_name_yaml}" <<- EOF
		- op: replace
		  path: /metadata/name
		  value: ${name}
		EOF

    cat > "${set_package_name_yaml}" <<- EOF
		---
		apiVersion: appstudio.redhat.com/v1alpha1
		kind: ImageRepository
		metadata:
		  labels:
		    appstudio.redhat.com/component: ${name}
		  name: ${name}
		spec:
		  image:
		    name: lucarval-tenant/${name}

		---
		apiVersion: appstudio.redhat.com/v1alpha1
		kind: Component
		metadata:
		  name: ${name}
		spec:
		  componentName: ${name}
		  containerImage: quay.io/redhat-user-workloads/lucarval-tenant/${name}
		EOF

    printf -- "  - %s\n" "${name}" >> "${all_kustomization_yaml}"
}

function generate_pac_resources() {
    local name
    name=$1

    export name

    < '.tekton/on-push.yaml.template' envsubst '$name' >> "${packages_on_push_yaml}"
    < '.tekton/on-pull-request.yaml.template' envsubst '$name' >> "${packages_on_pull_request_yaml}"
}

  if [[ "${SKIP_PAC:-0}" == "1" || "${SKIP_PAC:-0}" == "true" ]]; then
      echo 'WARN: Skipping Pipeline as Code generation.'
  else
      rm -f "${packages_on_push_yaml}"
      rm -f "${packages_on_pull_request_yaml}"
  fi

for path in "${packages[@]}"; do
    name="$(basename ${path})"
    echo "Processing ${name}"

    if [[ "${SKIP_WRAPPER:-0}" == "1" || "${SKIP_WRAPPER:-0}" == "true" ]]; then
        echo 'WARN: Skipping package wrapper generation.'
    else
        generate_package_wrapper "${name}" "${path}"
    fi

    if [[ "${SKIP_KONFLUX:-0}" == "1" || "${SKIP_KONFLUX:-0}" == "true" ]]; then
        echo 'WARN: Skipping Konflux resource generation.'
    else
        generate_konflux_resources "${name}"
    fi

    if [[ "${SKIP_PAC:-0}" == "1" || "${SKIP_PAC:-0}" == "true" ]]; then
        echo 'WARN: Skipping Pipeline as Code generation.'
    else
        generate_pac_resources "${name}"
    fi

done
