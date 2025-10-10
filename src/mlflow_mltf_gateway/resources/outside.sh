#!/bin/bash

#
# Runs inside.sh within a containerization environment
#

set -ex

function echo_error() {
  # shellcheck disable=SC2238
  echo "$@"
}

debug=false
inside_file="$(pwd)/inside.sh"
initial_dir="$(pwd)"

while getopts "di:t:c:s:" opt; do
  case $opt in
  d) debug=true ;;
  i) inside_file="$OPTARG" ;;
	t) tarball="$OPTARG" ;;
  # MLTF-generated script to be sourced just before execution
  # Since this is used to carry keys, it will be deleted/moved somewhere else
  s) source_path="$OPTARG" ;;
  # File containing arguments to be passed to mltf run
  c) cmdline_path="$OPTARG" ;;
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
cp "${tarball}" "${tempdir}"/mltf-input/mlflow-input.tar.gz
cp "${inside_file}" "${tempdir}"/mltf-input/inside.sh

# FIXME bomb if there is a source_path or cmdline_path argument passed in but doesn't exist
source_arg=""
if [[ -n "${source_path}" && -e "${source_path}" ]]; then
  cp "${source_path}" "${tempdir}"/mltf-input/mltf-source
  source_arg=" -s /tmp/mltf-input/mltf-source"
elif [[ -n "${source_path}" ]]; then
  2>&1 echo "ERROR: Command line args was specified but not found"
  exit 1
fi
cmdline_arg=""
if [[ -n "${cmdline_path}" && -e "${cmdline_path}" ]]; then
  cp "${cmdline_path}" "${tempdir}"/mltf-input/mltf-cmdline
  cmdline_arg=" -c /tmp/mltf-input/mltf-cmdline"
elif [[ -n "${cmdline_path}" ]]; then
  2>&1 echo "ERROR: Environment script was specified but not found"
  exit 1
fi

cd "${tempdir}" || exit 1
outdir="$(mktemp -d -p "$initial_dir" mltf-output-XXXXXX)"
console_output="${outdir}/stdout.txt"
echo "Outputs placed in ${outdir}"

# FIXME: Need to generatlize nerdctl/docker/podman and apptainer/singularity
#        paths here
if command -v nerdctl >&/dev/null; then
  # shellcheck disable=SC2086
  # We want to take the bytes as written for cmdline_arg and source_arg
  nerdctl run -i \
    -v "${tempdir}":/tmp/ -v "${tempdir}":/tmp/mltf-output --rm=true \
    ghcr.io/perilousapricot/mltf-rocky9 \
    -- \
    /bin/bash /tmp/mltf-input/inside.sh -t /tmp/mltf-input/mlflow-input.tar.gz ${cmdline_arg} ${source_arg} 2>&1 | tee "${console_output}"
elif command -v apptainer >&/dev/null; then
  #
  # I don't think these are the right bind params but let's roll with it
  #

  # see above
  # shellcheck disable=SC2086
  apptainer run \
    --nv \
    --writable-tmpfs \
    --no-mount tmp,cwd,home \
    --pid \
    --env MLFLOW_ENV_ROOT=/tmp/venvs \
    -B /cvmfs/:/cvmfs:ro \
    -B /cms:/cms:ro \
    -B /lfs_roots:/lfs_roots:ro \
    -B "${tempdir}":/tmp/:rw \
    -B "${outdir}":/tmp/mltf-output:rw \
    docker://ghcr.io/perilousapricot/mltf-rocky9 \
    -- \
    /bin/bash /tmp/mltf-input/inside.sh -t /tmp/mltf-input/mlflow-input.tar.gz ${cmdline_arg} ${source_arg} 2>&1 | tee "${console_output}"
else
  echo_error "Can't find containerization engine. Please add one"
  exit 1
fi

cp -a "${tempdir}"/mltf-output "$outdir"