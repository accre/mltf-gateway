#!/bin/bash

#
# Runs within a container to exeute client MLFlow code
#
debug=false
entrypoint=""
tarball=""

while getopts "dt:e:r:" opt; do
  case $opt in
  d) debug=true ;;
	t) tarball="$OPTARG" ;;
	e) entrypoint="$OPTARG" ;;
  r) export MLFLOW_RUN_ID="$OPTARG" ;;
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
# Make a temporary directory for our files
tempdir=$(mktemp -d -t "mltf-payload-XXXXXXXXXXXX")
if [ $? -ne 0 ]; then
  >&2 echo "Error: Could not make temporary directory"
  exit 1
fi
echo "MLTF temporary directory: ${tempdir}"
cd $tempdir
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
  cd ${payload_root}
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
 cd $PYENV_ROOT
 git pull
fi

[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install mlflow-skinny virtualenv

#
# Execute client payload
#

cd ${tempdir}/payload
entrypoint_arg=""
if [ ! -z "${entrypoint}" ]; then
  entrypoint_arg="-e \'${entrypoint}'"
fi
mlflow run ${entrypoint_arg} . 
