#!/bin/bash
#SBATCH --job-name={{ config.job_name | default('mlflow-job') }}
#SBATCH --partition={{ config.partition | default('shared') }}
#SBATCH --nodes={{ config.nodes | default(1) }}
#SBATCH --ntasks-per-node={{ config['ntasks-per-node'] | default(1) }}
#SBATCH --cpus-per-task={{ config['cpus-per-task'] | default(1) }}
#SBATCH --mem={{ config.mem | default('1gb') }}
#SBATCH --time={{ config.time | default('00:05:00') }}
{% if config.gpus %}
#SBATCH --gpus={{ config.gpus }}
{% endif %}

{{ command }}
