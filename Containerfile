FROM registry.redhat.io/ubi10/python-312-minimal:latest

COPY packages/urllib3 /opt/app-root/src

RUN pip install urllib3
