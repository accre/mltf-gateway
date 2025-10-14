#!/bin/bash
set -x
#
# Runs within a container to execute client MLFlow code
#
debug=false
tarball=""
source_path=""
cmdline_path=""

while getopts "dt:s:c:" opt; do
  case $opt in
  d) debug=true ;;
	t) tarball="$OPTARG" ;;
  # MLTF-generated script to be sourced just before execution
  # Since this is used to carry keys/secrets, it will be deleted
  s) source_path="$OPTARG" ;;
  # File containing arguments to be passed to mltf run
  c) cmdline_path="$OPTARG" ;;
	\?)
      >&2 echo "Invalid option: -$OPTARG"
      exit 1
    ;;
  esac
done
echo "Debug is $debug"
if [ ! -e ${tarball} ]; then
  >&2 echo "Could not find input tarball ${tarball}"
  exit 1
fi

# First we want to load an MLTF-provided script which will set environment variables
if [[ -n "${source_path}" && -e "${source_path}" ]]; then
  # shellcheck disable=SC1090
  # This is necessarily an external script, suppress the warning
  set +x
  source "${source_path}"
  set -x
  rm -f "${source_path}"
elif [[ -n "${source_path}" ]]; then
  2>&1 echo "ERROR: Environment script was specified but not found"
  exit 1
fi

# Load command line to execute
if [[ -n "${cmdline_path}" && -e "${cmdline_path}" ]]; then
  CMDLINE_DATA="$(cat ${cmdline_path})"
  rm -f "${cmdline_path}"
elif [[ -n "${cmdline_path}" ]]; then
  2>&1 echo "ERROR: Commanad line path was specified but not found"
  exit 1
fi

# Make a temporary directory for our files
tempdir=$(mktemp -d -t "mltf-payload-XXXXXXXXXXXX")
if [ $? -ne 0 ]; then
  >&2 echo "Error: Could not make temporary directory"
  exit 1
fi
echo "MLTF temporary directory: ${tempdir}"
cd $tempdir || exit
#shellcheck disable=SC2064 # expand now rather than when signaled
if [ "$debug" == "true" ]; then
  trap "echo Not removing temporary path ${tempdir} because of debug flag" 0
else
  trap "rm -rf -- ${tempdir}" 0
fi

payload_root="${tempdir}/payload"
echo "Unpacking ${tarball} into ${payload_root}"
( 
  mkdir -p ${payload_root}
  cd ${payload_root} || exit
  tar xvf "${tarball}"
)

#
# Install pyenv and mlflow
#
# Put this into /tmp for now while I think if apptainer should be rw

export PYENV_ROOT="/tmp/pyenv"

if [ ! -e $PYENV_ROOT ]; then
  git clone https://github.com/pyenv/pyenv.git $PYENV_ROOT
else
 cd $PYENV_ROOT || exit
 git pull
fi

[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install mlflow-skinny uv virtualenv
if [[ -n "${SLURM_CPUS_PER_TASK}" ]]; then
  echo "Limiting MAKE_OPTS to ${SLURM_CPUS_PER_TASK} CPUs"
  export MAKE_OPTS=" -j ${SLURM_CPUS_PER_TASK}"
fi

#
# Execute client payload
#
cd "${tempdir}"/payload || exit
# Allow splitting/globbing of the commandline args
# shellcheck disable=SC2086
mlflow run ${CMDLINE_DATA} .
