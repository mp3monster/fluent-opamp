FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        ruby \
        ruby-dev \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY scripts/bootstrap.py /opt/opamp-test/bootstrap.py
COPY entrypoint.sh /opt/opamp-test/entrypoint.sh
COPY defaults /opt/opamp-test/defaults

RUN chmod +x /opt/opamp-test/bootstrap.py /opt/opamp-test/entrypoint.sh \
    && python -m pip install --no-cache-dir --upgrade pip setuptools wheel

VOLUME ["/config", "/host-assets", "/host-output"]

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/opamp-test/entrypoint.sh"]
