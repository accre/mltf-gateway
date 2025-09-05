#!/bin/bash

#
# Runs inside.sh within a containerization environment
#


function echo_error() {
  # shellcheck disable=SC2238
  echo "$@"
}

debug=false
inside_file="$(pwd)/inside.sh"
initial_dir="$(pwd)"
run_id="0"

while getopts "di:t:r:" opt; do
  case $opt in
  d) debug=true ;;
  i) inside_file="$OPTARG" ;;
	t) tarball="$OPTARG" ;;
  r) run_id="$OPTARG" ;;
	\?)
      echo_error "Invalid option: -$OPTARG"
      exit 1
    ;;
  esac
done
echo "Debug is $debug"

if [ ! -e "${tarball}" ]; then
  echo_error "Could not find input tarball named ${tarball}"
  exit 1
fi

if [ ! -e "${inside_file}" ]; then
  echo_error "Could not find internal shell script"
  exit 1
fi

# Make a temporary directory for our files
tempdir=$(mktemp -d -t "mltf-outside-XXXXXXXXXXXX")
if [ $? -ne 0 ]; then
  echo_error "Error: Could not make temporary directory"
  exit 1
fi

# (Attempt to) delete the directory when this script ends
if [ "$debug" == "true" ]; then
  #shellcheck disable=SC2064 # expand now rather than when signaled
  trap "echo Not removing temporary path ${tempdir} because of debug flag" 0
else
  #shellcheck disable=SC2064 # expand now rather than when signaled
  trap "rm -rf -- ${tempdir}" 0
fi

if [ "$debug" == "true" ]; then
  set -x
fi

mkdir -p "${tempdir}"/{mltf-input,venvs,mltf-output}
cp ${tarball} "${tempdir}"/mltf-input/mlflow-input.tar.gz
cp ${inside_file} "${tempdir}"/mltf-input/inside.sh
cd "${tempdir}" || exit 1
outdir="$(mktemp -d -p "$initial_dir" mltf-output-XXXXXX)"
console_output="${outdir}/stdout.txt"
echo "Outputs placed in ${outdir}"

# FIXME: Need to generatlize nerdctl/docker/podman and apptainer/singularity
#        paths here
if command -v nerdctl >&/dev/null; then
  nerdctl run -i \
    -v "${tempdir}":/tmp/ --rm=true \
    ghcr.io/perilousapricot/mltf-rocky9 \
    -- \
    /bin/bash /tmp/mltf-input/inside.sh -t /tmp/mltf-input/mlflow-input.tar.gz -r "${run_id}" &>"${console_output}"
elif command -v apptainer >&/dev/null; then
  #
  # I don't think these are the right bind params but let's roll with it
  #
  apptainer run \
    --nv \
    --writable-tmpfs \
    --no-mount tmp,cwd \
    --pid \
    --env MLFLOW_ENV_ROOT=/tmp/venvs \
    -B "${tempdir}":/tmp/:rw \
    docker://ghcr.io/perilousapricot/mltf-rocky9 \
    -- \
    /bin/bash /tmp/mltf-input/inside.sh -t /tmp/mltf-input/mlflow-input.tar.gz -r "${run_id}" &>"${console_output}"
else
  echo_error "Can't find containerization engine. Please add one"
  exit 1
fi

cp -a "${tempdir}"/mltf-output "$outdir"