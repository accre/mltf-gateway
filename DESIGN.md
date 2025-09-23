MLTF Gateway
============

The MLTF Gateway is a REST-based client task submission API. With an
appropriate OAuth2 token, users can submit MLProject tasks to a REST server
who in turn submits jobs on the users' behalf to the SLURM cluster. A high
level diagram of the architecture is the following

```
[ Gateway Client ] <-- WAN --> [ Gateway Server ] <-- LAN --> [ SSAM ]
                                                                 v
                                                             [ SLURM ]
```

* SSAM is a REST-based API in front of the standard REST SLURM API
  * This provides additional logging and authorization above what is supported
    by the builtin SLURM REST API
* Gateway Server is a persistent REST server which accepts commands from the
  client (e.g. submit job, cancel job, list jobs)
* Gateway Client is a thin python client executed by the user which provides
  both an [MLFlow Project Backend](https://mlflow.org/docs/3.4.0/ml/projects/#custom-backend-development) for job submission and a 
  more fully-featured `mltf` command-line tool, which provides functions not
  directly supported by the MLFlow CLI (e.g. check job status, cancel jobs)

Gateway Client
--------------

The Gateway Client is a pure-python module designed to be loaded into the
users' environment which interacts with the Gateway Server REST interface. The
client needs to contain the minimal amount of logic, preferring to delegate
logic to the server when possible. This is because while the server can be
easily and periodically updated centrally, the client will be baked into a user
python environment meaning any updates will happen slowly (if at all).

The client needs to perform two important actions:
1. Acquiring and renewing OAuth2 tokens for authentication
2. Interacting with the Gateway Server

### Client Authentication
The client is initially a CLI tool, meaning there needs to be a method to
ergonomically get tokens from a OAuth2 provider into the users' enviroment.
This should be done with OAuth2's device flow, which asks the users to log into
a specific URL in their browser, then in the background OAuth2 will return the
token to the user (obviating the need to copy-paste a long string into the
user terminal)

```
Visit this link to authorize access to MLFlow
https://oauth2.example.com/realms/mltf-dual-login/device?user_code=XXVC-RKPX
```

It is sufficient to intially put this access token into an environment
variable, but future revisions should securely store a refresh token in the
local environment using python's `keyring` package or similar, which will
allow to periodically refresh/acquire access tokens without further user
intervention.

Importantly, this is the **only** authentication token the user provides to
the server. Users will not need to provide SSAM tokens to the gateway, since
the gateway is submitting to a common user on the backend.

### Interacting with the Gateway Server
The other component of the client is the interaction with the gateway server
via REST. From the client's perspective, this is the only entrypoint into the
cluster and should not be otherwise aware of how the tasks are executed --
meaning all the details are handled by the server component.

Initially, the client needs to support three operations:
1. Submit a new task
2. List all tasks submitted by the user
3. Get status of a specific task

Of these, only the task submission step is complicated. In keeping in line with
the principle that we want as much of the logic as possible to be stored
server-side, the task submission step should use the mlflow library simply to
get some high-level metadata from the provided project URI, then package that
URI in a tarball which is POST-ed to the server component, who then handles
further validation and eventual submission of the job.

Initially, the returned task IDs can be UUIDs, but it should be explored if it
is possible to re-use the MLFlow-provided run_id (e.g. are they guaranteed to
be unique?)

After implementing the initial operations, a more fully-featured CLI would
include features such as:
1. Querying the Gateway Server for available hardware configurations/limits for
   the current user
2. Downloading output artifacts to the client machine
3. Cancelling tasks
4. Purging tasks -- removing any information in the tracking databse + outputs

Finally, the MLFlow command-line does not allow users to perform many of the
proposed operations, so an `mltf` command line tool will be provided which can
be used in lieu of the builtin `mlflow` tool to support additional options

Gateway Server
--------------
The client speaks via REST to a Flask-based gateway server. This server
provides both an API and a demarcation line between the cluster and outside
workd. Since this is also a component directly under admin control, this is
also what implements the majority of the necessary logic as well as any
necessary keymaterial (such as SSAM tokens).

The server needs to be portable, not just in terms of not hard-coding
cluster-specific configuration like hostnames/endpoints, but also to be
agnostic to the method user tasks are executed. Initially there is a SLURM
execution backend (as well as a local execution backend used for unit-testing),
but future deployments may target other technologies like Kubernetes as the
cluster execution environment, so it's important that there is a clear
abstraction which can be implemented elsewhere.

Conceptually, the server tracks `tasks`, which is distinct from `runs` (an
MLFlow construct) and `jobs` (a SLURM construct). A user submits a "task" to
the server, which the server materializes into a SLURM "job" which then
eecutes an MLFlow "run". Tasks should also store metadata about themselves
including the subject of the user which submitted it. Initially information
about tasks can be persisted via pickle to local disk for persistence, but
latter revisions can consider migrating to an SQL database.

The job execution environment will need to receive additional enviroment
variables from the gateway, including the URI of the tracking server (if none
is provided) and an up-to-date user OAuth2 token. Initially, the server should
fail if the user token does not have enough validity remaining (perhaps a
week). Later revisions should support the server refreshing the user token on
their behalf and possibly having a runtime component which receives a new token
"just in time" as the job begins executing

### Task Submission
The most complicated aspect of the server is submitting a task on the users'
behalf. The server needs to receive a potentially-large tarball from the user,
store it somewhere accessible from SSAM/SLURM, parse the job resource requests,
then hand off the task to the SLURM executor to be placed in the queue.

Initially the server should take the user tarball/environment as-is without
further processing and simply pass it on to the executor. This ensures that the
needed server resources remain managable. Some python enviroments, particularly
with CUDA are quite large and can take a significant amount of time to
extract. Additionally, there are security implications to installing a
user-provided enviroment -- this would involve possibly executing untrusted
user code in a secure context, which could leak system secrets back to the
user.

Future revisions can enable data movement by e.g. pre-placing the users'
specified input files on fast local/networked storage.

Runtime Execution Enviroment
----------------------------
Once a user task is submitted to SSAM/SLURM and the job begins executing on the
compute host, we need to set up a standard execution enviroment to:

* Provide isolation. All MLTF jobs are executing as the same POSIX user, so
  we need to ensure jobs from different users on the same compute node cannot
  interfere with each others' execution
* Provide a "clean" environment. To ensure results are reproducible at
  different times, on different hosts, or even diferent clusters, we need
  to provide a consistent execution enviroment which takes as little as
  possible from the underlying host
* Provide abstractions. Users will tend to hard-code values like paths/hosts
  in their code. This means things break when the cluster is changed, or the
  task cannot be executed at other facilities.

When the job begins executing, it is initially using the host-provided
enviroment, including any installed libraries and filesytem paths. The first
step to setting up the runtime execution enviroment is to invoke a
containerization solution like Apptainer, which uses a "standard" OS image and
bind-mounts in private directories for that specific job. We also pass in any
needed enviroment variables/arguments such as OAuth2 tokens to the container
for the next step.

Once we're in a container, which has a consistent environment and is isolated
from the external host, we then set up any final variables, make working
directories, extract the user tarball then begin executing the user code using
the standard `mlflow run` sub-command. At this point, the code is executing on
the hardware the user has chosen, so we simply use the default "local" MLFlow
backend (e.g. no SLURM-specific backend). MLFlow then re-creates the user
python environment, enters that python virtual enviroment, then executes the
user code.

One caveat is that in the case of distributed training where a user specifies
they want to run multiple processes simultaneously, we need to add one extra
layer of indirection in the SLURM entrypoint script that does something
similar to:

```
if [ MULTIPLE_SLURM_TASKS ]; then
    srun <container_wrappe>
else
    <container_wrapper>
fi
```

Without this layer of indirection only the 0th process will execute anything
and the remaining processes will stay idle.
