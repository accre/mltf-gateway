# MLflow MLTF Gateway

**PLEASE NOTE** This is a very early alpha. If you hit an error or see missing functionality, please make an issue so
we can track and improve.

This project is a remote [MLFlow Project](https://mlflow.org/docs/latest/ml/projects/) job submission service. Using the 
included CLI or via REST, users can submit their training code to ACCRE (Vanderbilt's reearch computing facility).

## Install
Until releases are pushed to PyPi, one can install the client by executing the following

```bash
# If not already in a virtual environment
python3 -m venv venv
source venv/bin/activate

# Once within the virtual environment, install the client
# This only needs to be done once
git clone https://github.com/accre/mltf-gateway.git
pip install -e mltf-gateway
```

After installing, configure the client with
```bash
export MLTF_GATEWAY_URI=https://gateway-dev.mltf.k8s.accre.vanderbilt.edu
mltf login
```
This will prompt you to visit a webpage, login using either CERN or Vanderbilt credentials, and copy a code from your
terminal into the resulting page. You can verify things worked correctly with `mltf auth-status`

```
$ mltf auth-status
Credentials found, expired? False
Token Subject: e0574079-d98b-4cc3-9246-1aef09bc0107
Token Issuer: https://keycloak.k8s.accre.vanderbilt.edu/realms/mltf-dual-login
Access Token:
    Issued: 2025-10-06 22:23:05+00:00
   Expires: 2025-10-11 22:23:05+00:00
 Remaining: 1 day, 2:43:28.941754
Refresh Token:
    Issued: 2025-10-01 21:15:11+00:00
   Expires: 2025-10-26 20:56:06+00:00
 Remaining: 16 days, 1:16:29.941754
```

## Quickstart
To demonstrate the gateway, we set up an example "Hello World" project in the `demo/with-gpu` subdirectory of this repository. To
submit a job, enter the `demo/with-gpu` subdirectory and execute `mltf submit` which should output something similar to

```
$ mltf submit
Find your MLFlow run at https://mlflow-test.mltf.k8s.accre.vanderbilt.edu/#/experiments/0/runs/1d0c653826144357aa90a7de2c6f6bf8
Submitted project to MLTF: 962e168e-a61c-11f0-b4b0-bc2411853964
```

You can list your tasks with `mltf list`

```
$ mltf list
Tasks:
  2025-10-10@16:03:35 - 962e168e-a61c-11f0-b4b0-bc2411853964
```

And check their status with `mltf show <task_id>`. If wanted, logs can be viewed with `--show-logs`.

``` 
$ mltf show 962e168e-a61c-11f0-b4b0-bc2411853964
Status: RUNNING
```

Finally, any output artifacts, parameters or logs will be uploaded to the tracking server which can be accessed
from the URL provided above (future improvements will add CLI access to artifacts). The tracking API is
described [here](https://mlflow.org/docs/latest/ml/tracking/tracking-api/) and will let you upload arbitrary metrics (e.g. loss) and artifacts (e.g. output files)
