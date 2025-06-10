FROM quay.io/lucarval/calunga-builder:latest AS builder

ARG PACKAGE_NAME

RUN \
    mkdir -p /opt/app-root/dist && \
    ls -la "${PIP_FIND_LINKS}" && \
    PACKAGE_TARBALL=$(find "${PIP_FIND_LINKS}" -name "${PACKAGE_NAME}-*.tar.gz" -printf "%f\n") && \
    [ $(echo "${PACKAGE_TARBALL}" | wc -l) -eq 1 ] && \
    cp "${PIP_FIND_LINKS}/${PACKAGE_TARBALL}" /opt/app-root/dist/ && \
    tar -xvf "/opt/app-root/dist/${PACKAGE_TARBALL}" && \
    PACKAGE_DIR=$(basename "${PACKAGE_TARBALL}" .tar.gz) && \
    python -m build --wheel --outdir /opt/app-root/dist "${PACKAGE_DIR}"

FROM scratch

COPY --from=builder /opt/app-root/dist /releases
