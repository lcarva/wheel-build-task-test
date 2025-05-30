FROM quay.io/lucarval/calunga-builder:latest AS builder

ARG PACKAGE_NAME
ARG PACKAGE_VERSION

# TODO: Handle the case where '-' in the package name may get converted to '_' in the sdist file
# name, e.g. python-dateutil
RUN \
    mkdir -p /opt/app-root/dist && \
    ls -la "${PIP_FIND_LINKS}" && \
    cp "${PIP_FIND_LINKS}/${PACKAGE_NAME}-${PACKAGE_VERSION}.tar.gz" /opt/app-root/dist/ && \
    tar -xvf "/opt/app-root/dist/${PACKAGE_NAME}-${PACKAGE_VERSION}.tar.gz" && \
    python -m build --wheel --outdir /opt/app-root/dist "${PACKAGE_NAME}-${PACKAGE_VERSION}"

FROM scratch

COPY --from=builder /opt/app-root/dist /releases
