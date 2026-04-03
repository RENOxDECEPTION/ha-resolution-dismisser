ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.21
FROM ${BUILD_FROM}

LABEL \
    io.hass.type="addon" \
    io.hass.name="Resolution Dismisser" \
    io.hass.description="Automatically dismisses HA Supervisor resolution warnings" \
    org.opencontainers.image.title="Resolution Dismisser" \
    org.opencontainers.image.description="Automatically dismisses HA Supervisor resolution warnings" \
    org.opencontainers.image.source="https://github.com/RENOxDECEPTION/ha-resolution-dismisser" \
    org.opencontainers.image.licenses="MIT"

RUN apk add --no-cache \
    curl \
    jq \
    bash \
    python3 \
    py3-pip \
  && pip3 install --no-cache-dir --break-system-packages websocket-client

COPY run.sh dismiss_repairs.py /
RUN chmod a+x /run.sh /dismiss_repairs.py

CMD [ "/run.sh" ]
