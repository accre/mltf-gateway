FROM python:3 AS builder

#
# Do some things as root. Presumably npm needs to be installed...
# 
RUN chown nobody /srv

# ...Then switch to the nobody user for the rest
USER nobody
RUN python -m venv /srv/venv && \
    /srv/venv/bin/pip install --no-cache-dir --upgrade wheel && \
    /srv/venv/bin/pip install --no-cache-dir --upgrade --force-reinstall pip

COPY --chown=nobody pyproject.toml /srv/src/pyproject.toml
COPY --chown=nobody src/mltf_gateway/__about__.py /srv/src/src/mltf_gateway/__about__.py
COPY --chown=nobody README.md /srv/src/README.md
RUN /srv/venv/bin/pip install --no-cache-dir --no-compile /srv/src/ && \
    rm -rf /srv/src

COPY --chown=nobody README.md *.py *.toml /srv/src/
COPY --chown=nobody src/ /srv/src/src/

RUN /srv/venv/bin/pip uninstall -y mltf_gateway && \
    /srv/venv/bin/pip install --no-cache-dir /srv/src/

FROM python:3 AS runtime
LABEL org.opencontainers.image.source=https://github.com/accre/mltf-gateway
# Same dance as before, install stuff as root then switch to nobody
RUN chown nobody /srv && \
    apt update && \
    apt install --no-install-recommends -y supervisor && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# This config file references a dummy mltf_startup.sh that actually starts the service
COPY --chown=nobody ci/mltf-container/supervisord.conf /etc/supervisord.conf
USER nobody
COPY --chown=nobody ci/mltf-container/mltf_startup.sh /srv/
COPY --from=builder --chown=nobody /srv/venv /srv/venv

WORKDIR /srv
CMD ["/usr/bin/supervisord"]
