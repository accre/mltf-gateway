#!/bin/bash

function get_buildkit_cmd() {
    # Other build-kit compatible CLIs exist, find which
    # one the user has installed
        for X in nerdctl docker; do
        if ${X} ps &>/dev/null; then
            echo "${X}"
            return 0
        fi
    done
    1>&2 echo "ERROR: Buildkit CLI (e.g. docker) not found"
    return 1
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../.. && pwd )

RUN_LOCAL=""
TAG="mltf-gateway:latest"
SECRET_PATH="$(pwd)/secret"
RUN_PATH="$(pwd)/run"

while getopts 't:lh' opt; do
  case "$opt" in
    --)
      break
      ;;
    l)
      RUN_LOCAL=" -v ${ROOT_DIR}:/srv/src:ro "
      ;;
    t)
      TAG="$OPTARG"
      ;;
    ?|h)
      2>&1 echo "Usage: $(basename $0) [-l] [-t image_tag]"
      2>&1 echo "       -l"
      exit 1
      ;;
  esac
done
shift "$(($OPTIND -1))"

CONTAINER_CMD="$(get_buildkit_cmd)"

mkdir -p "${RUN_PATH}"
chmod 777 "${RUN_PATH}"
set -x
${CONTAINER_CMD} run -it --rm=true \
                 -v ${SECRET_PATH}:/secret:ro \
                 -v ${RUN_PATH}:/srv/run \
                 ${RUN_LOCAL} \
                 -e SSAM_URL=https://ssam.accre.vanderbilt.edu \
                 -e AUTH_TOKEN_PATH=/secret/ssam_token \
                 -e SLURM_TOKEN_PATH=/secret/slurm_token \
                 -e DATABASE_URL=sqlite:////srv/run/mltf_gateway.db \
                 -e MLTF_IP=0.0.0.0 \
                 -p 8080:8080/tcp \
             "${TAG}" "$@"
