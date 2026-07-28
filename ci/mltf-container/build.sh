#!/bin/bash

# Helper script to build MLTF Gateway container
function get_buildkit_cmd() {
    # Other build-kit compatible CLIs exist, find which
    # one the user has installed
	for X in nerdctl docker; do
        if ${X} ps &>/dev/null; then
            echo "${X}"
            return 0
        fi
    done
    2>&1 echo "ERROR: Buildkit CLI (e.g. docker) not found"
    return 1
}

TAG="mltf-gateway:latest"
MULTIARCH=""
CLEAN=""

PROD_MULTIARCH="--platform amd64,arm64"
PROD_CLEAN="--pull --no-cache"
while getopts 'acpt:h' opt; do
  case "$opt" in
    a)
      MULTIARCH="${PROD_MULTIARCH}"
      ;;
    c)
      CLEAN="${PROD_CLEAN}"
      ;;
    p)
      CLEAN="${PROD_CLEAN}"
      MULTIARCH="${PROD_MULTIARCH}"
      ;;
    t)
      TAG="$OPTARG"
      ;;
    ?|h)
      2>&1 echo "Usage: $(basename $0) [-acp] [-t image_tag]"
      2>&1 echo "       -a : Enables building for multiple archs"
      2>&1 echo "       -c : Performs a clean build (no-cache, pull images"
      2>&1 echo "       -t image_tag : Override default image tag"
      2>&1 echo "       -p : Performs a build with production arguments"
      exit 1
      ;;
  esac
done
shift "$(($OPTIND -1))"

BUILDKIT_CMD=$(get_buildkit_cmd)

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../.. && pwd )

echo "INFO: Will build using ${X}"
echo "INFO: Build root is $ROOT_DIR"

${BUILDKIT_CMD} build ${ROOT_DIR} -f ${SCRIPT_DIR}/Dockerfile ${MULTIARCH} ${CLEAN} -t ${TAG}
