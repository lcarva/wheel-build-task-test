FROM quay.io/lucarval/calunga-builder:latest AS builder

RUN \
    tar -xvf "${PIP_FIND_LINKS}/urllib3-2.4.0.tar.gz" && \
    python -m build --wheel urllib3-2.4.0 && \
    mkdir -p /opt/app-root/dist && \
    cp urllib3-2.4.0/dist/*.whl /opt/app-root/dist/ && \
    cp "${PIP_FIND_LINKS}/urllib3-2.4.0.tar.gz" /opt/app-root/dist/

FROM scratch

COPY --from=builder /opt/app-root/dist /releases