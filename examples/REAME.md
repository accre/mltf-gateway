[text](sklearn_elasticnet_wine/mltf_config.json)

1. To run the test, simply cd to sklearn_elasticnet_wine folder and create a mltf_config.json file:
```
{
    "job_name": "mlflow-example-job",
    "nodes": 1,
    "ntasks-per-node": 1,
    "cpus-per-task": 4,
    "partition": "batch",
    "mem": "16g",
    "time": 3600,
    "modules": ["cudnn/v8.2.4", "cuda/11.4.1"],
    "environment": [
        "MY_ENV_VAR=value",
        "TERM=dumb"
    ],
    "debug": true
}
```

2. Create venv, with this repo installed on it.
```
pip install .
```

3. Set the right environment variables:
```
export SSAM_URL="https://ssam.accre.vanderbilt.edu/api"
export AUTH_TOKEN="your-ssam-auth-token"
export SLURM_TOKEN="your-slurm-token"
export PROJECT_ROOT_DIR="/path/to/project/root"
```

4. Finally, run the mlflow command 
```
mlflow run . --backend mltf_backend --backend-config ./mltf_config.json
```