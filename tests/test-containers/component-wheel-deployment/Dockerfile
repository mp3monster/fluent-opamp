FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        git \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /runner

COPY entrypoint.sh /runner/entrypoint.sh
COPY scripts/run_component_wheel_deployment.py /runner/run_component_wheel_deployment.py

RUN sed -i 's/\r$//' /runner/entrypoint.sh /runner/run_component_wheel_deployment.py \
    && chmod +x /runner/entrypoint.sh /runner/run_component_wheel_deployment.py \
    && python -m pip install --upgrade pip setuptools wheel build virtualenv

VOLUME ["/workspace/opamp", "/host-output"]

ENTRYPOINT ["/usr/bin/tini", "--", "/runner/entrypoint.sh"]
