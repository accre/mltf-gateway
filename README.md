# MLflow MLTF Backend (SSAM Integration)

This document describes how to use the `mlflow-mltf` backend to submit MLflow projects to a Slurm cluster using an SSAM (Slurm Submission and Management) server.

## Overview

The SSAM backend for MLflow allows you to run your MLflow projects as jobs on a Slurm-managed cluster. It works by packaging your project files, and submitting them to an SSAM server, which in turn is responsible for creating and managing the Slurm job.

This approach simplifies running MLflow projects in a clustered environment by abstracting away the details of Slurm job submission.

## Configuration

To use this backend,

1. Create SSAM environment variables
2. You need to create a configuration file: `mltf_config.json` for job-specific parameters.

### ssam environment

The SSAM environment variables have to be set in order for this to work
**Example :**

```
export SSAM_URL="https://ssam.accre.vanderbilt.edu/api"
export AUTH_TOKEN="your-ssam-auth-token"
export SLURM_TOKEN="your-slurm-token"
export PROJECT_ROOT_DIR="/path/to/project/root"
```

#### Configuration Options:

*   **`SSAM_URL`**: (Required) The base URL of the SSAM server API (e.g., `https://ssam.accre.vanderbilt.edu/api`).
*   **`AUTH_TOKEN`**: (Required) The bearer token for authenticating with the SSAM server.
*   **`SLURM_TOKEN`**: (Required) The Slurm token for the SSAM server.
*   **`PROJECT_ROOT_DIR`**: (Required) The base path for the experiment on the cluster.

### mltf_config.json

This file contains the configuration for the Slurm job itself.

**Example `mltf_config.json`:**

```json
{
    "job-name": "mlflow-example-job",
    "partition": "gpu_partition",
    "nodes": 1,
    "ntasks-per-node": 1,
    "cpus-per-task": 4,
    "mem": "16gb",
    "time": "01:00:00",
    "gpus": "1",
    "modules": ["cudnn/v8.2.4", "cuda/11.4.1"],
    "environment": ["MY_ENV_VAR=value"],
    "debug": true
}
```

#### Configuration Options:

*   **`job-name`**: The name of the Slurm job.
*   **`partition`**: The Slurm partition to submit the job to.
*   **`nodes`**: The number of nodes to request.
*   **`ntasks-per-node`**: The number of tasks per node.
*   **`cpus-per-task`**: The number of CPUs per task.
*   **`mem`**: The amount of memory to request (e.g., "4gb").
*   **`time`**: The maximum wall time for the job (e.g., "00:30:00").
*   **`gpus`**: The number of GPUs to request.
*   **`modules`**: A list of environment modules to load before running the project.
*   **`environment`**: A list of environment variables to set for the job.
*   **`debug`**: If `true`, the temporary working directory on the cluster node will not be deleted, which can be useful for debugging.

## Usage

To run an MLflow project with the SSAM backend, use the `mlflow run` command, passing the `mltf_config.json` to the `--backend-config` argument.

```bash
mlflow run . \
    --backend mltf_backend \
    --backend-config mltf_config.json \
    -P my_param=value
```

## How it Works

1.  When you execute `mlflow run` with the `mlflow_mltf_experimental.mltf_backend` backend, the backend plugin is invoked.
2.  The backend reads the SSAM credentials from `.ssam_config.json` in your project root.
3.  It then communicates with the SSAM server to set up the `SLURM_TOKEN` and `PROJECT_ROOT_DIR`.
4.  The backend packages your MLflow project directory into a compressed tarball (`.tar.gz`).
5.  It then sends a request to the specified `SSAM_URL`. This request includes:
    *   The project tarball.
    *   An entrypoint script that knows how to set up the environment and run the project.
    *   The Slurm job parameters from `mltf_config.json`.
6.  The SSAM server receives this request, creates a new Slurm job, and submits it to the cluster.
7.  On the cluster node, the entrypoint script is executed. It creates a Python virtual environment, installs the necessary dependencies, and then runs your MLflow project's entrypoint.
8.  While the job is running, the backend polls the SSAM server to get the status of the job.
9.  Once the job is complete, the backend can retrieve the logs from the SSAM server and attach them as artifacts to your MLflow run.

