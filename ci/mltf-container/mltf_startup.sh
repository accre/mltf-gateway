#!/bin/bash
ls -lahd /srv/{src,run}
if [ -e /srv/src/pyproject.toml ]; then
    #
    # The user passed in a source dir, install as editable package
    #
    echo "Detected local install."
    /srv/venv/bin/pip install --upgrade -e /srv/src/
fi
source /srv/venv/bin/activate
mkdir -p /srv/run
cd /srv/run
MLTF_PORT=${MLTF_PORT:-${PORT:-8080}}
MLTF_IP=${MLTF_IP:-localhost}
for ((;;)); do
    mltf server --port ${MLTF_PORT} --host ${MLTF_IP} "$@"
    echo "Server died, restarting"
    sleep 5
done
