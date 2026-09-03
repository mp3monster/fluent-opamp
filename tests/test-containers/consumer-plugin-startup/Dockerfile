FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/opamp

COPY entrypoint.sh /opt/opamp-regression/entrypoint.sh
COPY scripts/run_consumer_plugin_startup.py /opt/opamp-regression/run_consumer_plugin_startup.py

RUN sed -i 's/\r$//' /opt/opamp-regression/entrypoint.sh /opt/opamp-regression/run_consumer_plugin_startup.py \
    && chmod +x /opt/opamp-regression/entrypoint.sh \
    && python -m pip install --no-cache-dir --upgrade pip setuptools wheel

VOLUME ["/workspace/opamp"]

ENTRYPOINT ["/opt/opamp-regression/entrypoint.sh"]
