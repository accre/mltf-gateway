#!/bin/bash
set -ex

debug={{ debug | lower }}
tarball="input/project.tar.gz"

if [ ! -e "${tarball}" ]; then
  >&2 echo "Could not find input tarball ${tarball}"
  exit 1
fi

export MLFLOW_RUN_ID={{ run_id }}
workdir=$(mktemp -d -t "mltf-workdir-$MLFLOW_RUN_ID-XXXXX")
echo "MLTF work directory: ${workdir}"

if [ "$debug" == "true" ]; then
  trap "echo Not removing temporary path ${workdir} because of debug flag" 0
else
  trap "rm -rf -- ${workdir}" 0
fi

echo "Unpacking ${tarball} into ${workdir}"
tar xvf "${tarball}" -C "${workdir}"
cd "${workdir}"

(
  setup_accre_software_stack || {
    echo "Could not setup ACCRE software stack"
    exit 1
  }
  # Subshell: traps do not propagate here unless redefined
  set -e  # exit immediately on error inside subshell
  {% if config.modules %}
  module reset
  {% for module in config.modules %}
  module load {{ module }}
  {% endfor %}
  module list
  {% endif %}
) || {
  echo "modules not loaded properly... might cause issue later"
}

{% if config.environment %}
{% for env in config.environment %}
export {{ env }}
{% endfor %}
{% endif %}

echo "job is starting on $(hostname)"

# The command is rendered by the backend and includes environment activation
{{ command }}