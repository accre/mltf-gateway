# Client-Facing Python API for the MLTF Gateway

**Status:** DRAFT — core API design agreed; implementation not started. One open item (artifact-download backend) to verify before Phase 5.
**Owner:** PerilousApricot
**Branch:** `feat/client-api`
**Last updated:** 2026-11-19

## 1. Purpose

Add a first-class, **user-facing** Python API to the `mltf_gateway.client`
package that lets Python users drive the gateway programmatically without
going through the `mltf` CLI or the `mlflow run --backend gateway` path.

The initial scope is the four basic operations:

1. **Submit** a task (an MLflow project) to the gateway
2. **Check status** of a task
3. **Cancel** a task
4. **Download artifacts** produced by a task

Everything else (hardware discovery, purging, streaming logs, etc.) is
explicitly out of scope for this first revision.

## 2. Goals / Non-goals

### Goals
- A small, idiomatic, **stable** public surface: one client class, a few
  dataclasses, a small typed exception hierarchy.
- **Lazy, non-blocking construction** — `MLTFClient()` must not trigger the
  interactive OAuth2 device flow at import/instantiation time.
- **Reuse** the existing, already-tested internals (auth, tarball packing,
  config resolution) rather than re-implementing them.
- **Zero regressions** to the existing `mltf` CLI and the
  `mlflow run --backend gateway` entry point. This change is additive.
- Predictable behavior that is easy to **unit-test** against a mock/LOCAL
  gateway.

### Non-goals (this revision)
- No new server-side endpoints. The client only speaks to the REST surface
  that already exists (see §5). If an operation needs a new endpoint, that is
  a separate server change.
- No streaming / live log tailing (only final logs on a finished job).
- No hardware/queue introspection.
- No changes to how the *server* executes jobs.

## 3. Current state (what already exists)

`src/mltf_gateway/client/` today is **not** a user-facing API — it is the
MLflow-backend integration layer:

| File | Role | Reused by new API? |
|---|---|---|
| `__init__.py` | **Empty** — nothing exported today | **Yes** — becomes the public export surface |
| `oauth.py` | OAuth2 device flow + keyring token store (`get_access_token`, `add_auth_header_to_request`, …) | **Yes** — primary auth source |
| `project_packer.py` | `prepare_tarball` / `produce_tarball` / `package_project` (tar a project dir, skipping git/cache/venv) | **Yes** — builds the submit tarball |
| `backend_adapter.py` | `RESTAdapter` / `RequestAdaptor` — the HTTP transport the MLflow backend + CLI use (includes in-process `LOCAL` mode) | **No** (see §6.2) — left untouched for compatibility |
| `mlflow_project_backend.py` | `GatewayProjectBackend(AbstractBackend)` — the `mlflow run` backend | **No** — untouched |
| `gateway_client.py` | `gateway_backend_builder()` — MLflow entrypoint | **No** — untouched |

Relevant helpers outside the package:
- `mltf_gateway.utils.gateway_uri()` → `MLTF_GATEWAY_URI` or `https://gw.mltf.vu`
- `mltf_gateway.utils.get_tracking_uri()` → `MLFLOW_TRACKING_URI` or `https://mlflow.mltf.vu`

### Existing defect worth noting
The `mlflow.project_backend` entry point in `pyproject.toml` points at
`mltf_gateway.gateway_client:gateway_backend_builder`, but the function lives
in **`mltf_gateway.client.gateway_client`** — there is no top-level
`mltf_gateway/gateway_client.py`. This entry point appears **stale**. It is
out of scope to fix here, but the new API's export design (§4) should make
the canonical public location unambiguous, and we should confirm whether the
`mlflow run --backend gateway` path is currently affected before this lands.

## 4. Public API surface

Everything public is exported from `mltf_gateway.client`:

```python
from mltf_gateway.client import (
    MLTFClient,          # the client
    Task,                # handle returned by submit()
    TaskStatus,          # result of status()/wait()
    Artifact,            # one entry from list_artifacts()
    MLTFError,           # base exception
    MLTFAuthError,
    MLTFConnectionError,
    MLTFJobError,
    MLTFNotFoundError,
    MLTFTimeoutError,
)
```

### 4.1 Construction

```python
client = MLTFClient(
    gateway_uri=None,     # default: mltf_gateway.utils.gateway_uri()
    tracking_uri=None,    # default: mltf_gateway.utils.get_tracking_uri()
    token=***           # pre-fetched OAuth2 access token; default: None
)
```

- `gateway_uri` / `tracking_uri` fall back to the env-driven helpers, so a
  bare `MLTFClient()` works on a configured machine.
- `token`, if provided, short-circuits the keyring/device-flow. If `None`,
  the token is resolved **lazily on first network call** (see §7) and cached.
- Construction never touches the network and never blocks on a browser.

### 4.2 Submit

```python
task = client.submit(
    project_dir="./demo/demo-cpu",   # path to an MLflow project (has MLproject)
    entry_point="main",
    params={},                       # entry-point parameters (dict)
    name="my-run",                   # optional display name
    backend_config={},               # optional SLURM/SSAM directives (e.g. {"mem": "8192"})
    experiment=None,                 # experiment name; default "default_<user>"
)
```

Returns a `Task`. The client, in order:
1. Resolves the experiment (get-by-name, create if missing) → `experiment_id`.
2. Creates an MLflow **run** in that experiment (tags `mlflow.user`) → `run_id`.
3. Packs `project_dir` into a tarball (via `project_packer`).
4. `POST /api/job` (multipart: `tarball` + form fields) with the Bearer token.
5. Returns `Task(gateway_id, run_id, name, creation_time)` from the response.

An escape hatch for callers who already have a tarball:

```python
task = client.submit_tarball(tarball_path, entry_point="main", ...)
```

`backend_config` is merged with any `gateway_config.json` found in the project
dir (project file wins), matching the existing CLI behavior.

### 4.3 Status

```python
status = client.status(task.gateway_id, show_logs=False)   # -> TaskStatus
final  = client.wait(task.gateway_id, timeout=1800, poll_interval=10)
```

- `status()` is a single `GET /api/jobs/<gateway_id>` call.
- `wait()` polls until a terminal status (`FINISHED`, `FAILED`, `CANCELLED`)
  or `timeout` (raises `MLTFTimeoutError`). The returned `TaskStatus` for a
  finished job includes `logs` (requested with `show_logs=true`).

### 4.4 Cancel

```python
client.cancel(task.gateway_id)     # -> CancelResult / None
```

Issues `DELETE /api/jobs/<gateway_id>`. A 404 raises `MLTFNotFoundError`.

### 4.5 Artifacts

```python
artifacts = client.list_artifacts(task.run_id)      # -> list[Artifact]
dest = client.download_artifact(
    task.run_id, "model.pkl", dest_dir="./out"      # -> local path written
)
```

- `list_artifacts` uses `MlflowClient.list_artifacts` (standard MLflow REST).
- `download_artifact` uses the deployment's **presigned-URL** endpoint
  (`GET /ajax-api/2.0/mlflow-artifacts/presigned/artifacts/<path>?run_id=…`)
  and fetches the returned URL. See §6.3 for why not the standard
  `MlflowClient.download_artifacts`.

### 4.6 The `Task` handle

The `Task` object returned by `submit()` is the ergonomic primary interface —
it remembers its ids and its client, so the common "I just submitted it" flow
reads naturally:

```python
task = client.submit(project_dir=..., name="train")
task.wait()                 # block until done
task.status()               # non-blocking
task.cancel()               # abort
task.artifacts()            # -> list[Artifact]
task.download("model.pkl")  # -> local path
```

`Task` is a thin convenience wrapper; the underlying calls are the
client-level methods in §4.2–4.5 keyed by `gateway_id` / `run_id`. Both forms
are supported so a user can persist a `gateway_id` and resume in a later
process with fresh `client.status(gateway_id)`.

### 4.7 Dataclasses

```python
@dataclass(frozen=True)
class Task:
    gateway_id: str
    run_id: str
    name: str
    creation_time: int                 # epoch seconds
    # convenience methods delegate to the client that created it

@dataclass(frozen=True)
class TaskStatus:
    status: str                        # SCHEDULED|RUNNING|FINISHED|FAILED|CANCELLED|UNKNOWN
    name: str
    failure_reason: str | None
    logs: str | None
    @property
    def is_terminal(self) -> bool: ... # FINISHED/FAILED/CANCELLED

@dataclass(frozen=True)
class Artifact:
    path: str
    is_dir: bool
```

### 4.8 Exceptions

```python
class MLTFError(Exception):            # base
class MLTFAuthError(MLTFError)         # bad/expired token, device-flow failure
class MLTFConnectionError(MLTFError)   # gateway/tracking unreachable
class MLTFJobError(MLTFError)          # job ran but failed (carries failure_reason)
class MLTFNotFoundError(MLTFError)     # unknown gateway_id/run_id
class MLTFTimeoutError(MLTFError)      # wait() exceeded timeout
```

`wait()` raises `MLTFJobError` when the job reaches `FAILED` (so callers can
distinguish "timed out" from "the job itself failed") and `MLTFTimeoutError`
when it is still running at the deadline.

## 5. The REST surface the client speaks to

No new server endpoints are required. The client uses exactly these existing
endpoints:

**Gateway** (`gateway_uri`, Bearer auth):
- `GET  /api/config` — OIDC discovery bootstrap (device flow)
- `POST /api/job` — submit (multipart `tarball` + form fields)
- `GET  /api/jobs` — list (used to map `gateway_id` ↔ `run_id` and by the CLI)
- `GET  /api/jobs/<gateway_id>?show_logs=…` — status
- `DELETE /api/jobs/<gateway_id>` — cancel

**Tracking server** (`tracking_uri`, Bearer auth):
- `GET  /api/2.0/mlflow/experiments/get-by-name` / `POST …/experiments/create`
- `POST /api/2.0/mlflow/runs/create`
- `GET  /api/2.0/mlflow-artifacts/artifacts?run_id=…` (via `MlflowClient`)
- `GET  /ajax-api/2.0/mlflow-artifacts/presigned/artifacts/<path>?run_id=…`

The same OAuth2 access token is accepted by **both** the gateway and the
tracking server (the existing CLI sets `MLFLOW_TRACKING_TOKEN` to the same
access token), so one token serves all calls.

## 6. Architecture

### 6.1 Module layout (all new, additive)

```
src/mltf_gateway/client/
  __init__.py            # (existing, empty) -> export the public names
  api.py                 # (NEW) MLTFClient public API
  gateway.py             # (NEW) thin requests-based gateway transport
  models.py              # (NEW) Task, TaskStatus, Artifact
  errors.py              # (NEW) exception hierarchy
  oauth.py               # (existing) auth — reused
  project_packer.py      # (existing) tarball — reused
  backend_adapter.py     # (existing) untouched
  mlflow_project_backend.py  # (existing) untouched
  gateway_client.py      # (existing) untouched
```

`MLTFClient` **composes**: `Gateway` (transport) + `oauth` (token) +
`project_packer` (tarball) + `MlflowClient` (run/experiment/artifact-list).
This keeps each concern independently testable and keeps the public class thin.

### 6.2 Why a new `gateway.py` and not reusing `RESTAdapter`

`RESTAdapter` is coupled to the MLflow-backend world: it imports the **server
app** (`create_app`) for in-process `LOCAL` mode, wraps responses in its own
`Response` shim, and returns `ClientSideSubmittedRun` objects. For a clean,
server-independent public client we want a ~100-line `requests`-based
`Gateway` with no server import and no MLflow-backend entanglement.

`RESTAdapter` / `GatewayProjectBackend` / the `mltf` CLI are **left
untouched** so nothing regresses. A **follow-up** (not this revision) can
refactor `RESTAdapter` to delegate to the new `Gateway` and delete the
duplication — tracked separately.

### 6.3 Artifact download: presigned vs standard

The deployment's CLI downloads artifacts via a **custom presigned-URL
endpoint** (`/ajax-api/2.0/mlflow-artifacts/presigned/artifacts/…`), which
implies the stock MLflow `…/artifacts/download` route is not the intended
path here. We therefore use the presigned endpoint (proven by the CLI) for
`download_artifact`, and `MlflowClient.list_artifacts` for listing.

**Open question (Q2, §10):** confirm whether `MlflowClient.download_artifacts`
works against the live tracking server. If it does, we may offer
`download_artifact(..., backend="auto"|"presigned"|"standard")` defaulting to
presigned. Default behavior for this revision: **presigned**.

### 6.4 Reuse map

| Concern | Source |
|---|---|
| Token acquisition/refresh (device flow, keyring) | `client.oauth.get_access_token` |
| Tarball construction | `client.project_packer.package_project` |
| Gateway/tracking URIs | `mltf_gateway.utils.gateway_uri` / `get_tracking_uri` |
| Run + experiment creation, artifact listing | `mlflow.tracking.MlflowClient` |
| Gateway HTTP (submit/status/list/cancel) | new `client.gateway.Gateway` |
| Presigned artifact download | new (raw `requests`) |

## 7. Authentication flow

1. `MLTFClient(token=*** uses that token.
2. Otherwise, on **first network call** (not construction), call
   `oauth.get_access_token()`, which: returns valid keyring creds → refresh if
   expired → else runs the device flow (opens browser, prints the
   verification URL). The resolved `access_token` is cached on the client for
   the lifetime of the process.
3. All gateway and tracking calls send `Authorization: Bearer <token>`.
4. A `401` from the gateway triggers one re-fetch of the token and a single
   retry; a second `401` raises `MLTFAuthError`.

Lazy auth means `import mltf_gateway.client` and `MLTFClient()` are side-effect
free, and tests can inject a token without any keyring or browser.

## 8. Error handling & retry policy

- **Connectivity** failures → `MLTFConnectionError` (no auto-retry on submit,
  to avoid double-submitting a job; `wait()` retries status polls).
- **HTTP 4xx** from the gateway → mapped to the typed exceptions in §4.8
  (`404`→`MLTFNotFoundError`, `401`→`MLTFAuthError`, other→`MLTFError` with
  the response body).
- **`wait()`** retries status GETs on transient network errors up to a bounded
  number of attempts before re-raising.
- **No retry on `POST /api/job`** — a retried submit could enqueue a
  duplicate job. Documented explicitly.

## 9. Testing strategy

- **Unit** (no network): `models`, `errors`, `gateway.py` request construction
  and response parsing, `MLTFClient` arg handling — using `requests_mock`
  (already a dev dependency) and the existing in-process `LOCAL` gateway.
- **Auth**: reuse the `TestingKeyring` pattern from `tests/test_client_auth.py`
  (note: that helper has a latent bug — it reads `self.vals.get(username)`
  instead of `self.vals[service][username]`; the new tests must not copy it).
- **Integration**: against the mock gateway/tracking pair that validated
  `examples/raw_api_example.py` (submit → status → artifact download).
- **Compatibility**: the existing `mltf` CLI + `mlflow run --backend gateway`
  tests continue to pass unchanged (nothing in those paths is modified).

## 10. Decisions & open questions

### Decided (2026-11-19)
- **Public class name:** `MLTFClient`.
- **Task referencing:** support **both** the `Task` handle (ergonomics) and
  the id-based client methods (resumption across processes).
- **v1 `submit()` source:** **local project dir only**. Remote URIs
  (git/file, via `fetch_and_validate_project`) are a later revision.
- **Stale `mlflow.project_backend` entry point** (§3): **separate PR** — this
  change stays purely additive.
- **`wait()` default `timeout`:** 30 min, overridable.

### Still open
- **Artifact download backend.** Does `MlflowClient.download_artifacts` work
  on the live server, or is the presigned endpoint mandatory? This revision
  defaults to the **presigned** endpoint (proven by the CLI); an
  `auto`/`standard` option is added only if the standard path is confirmed to
  work. Needs verification against the live tracking server before Phase 5.

## 11. Implementation plan (phases)

1. **Phase 1 — Skeleton + models + errors** (no behavior): add
   `models.py`, `errors.py`, populate `__init__.py`. Trivially testable.
2. **Phase 2 — `gateway.py` transport + auth wiring**: the four gateway calls
   + lazy token; unit-tested with `requests_mock` / LOCAL.
3. **Phase 3 — `submit()`**: experiment/run creation + tarball + `POST
   /api/job`; integration-tested against the mock.
4. **Phase 4 — `status()` / `wait()` / `cancel()`.**
5. **Phase 5 — Artifacts** (list + presigned download).
6. **Phase 6 — `Task` convenience handle + docs + README section + examples.**
7. **Follow-up (separate PR):** refactor `RESTAdapter` to delegate to
   `Gateway`; fix stale entry point (Q4).

Each phase lands independently and keeps the package importable and the
existing CLI green.

## 12. Backwards compatibility

- Additive only: new modules + new `__init__.py` exports. No existing module
  is modified in this revision.
- `mltf` CLI and `mlflow run --backend gateway` are unaffected.
- New public names are introduced under a clear, versioned surface
  (`mltf_gateway.client`); we will avoid re-using the confusing existing
  `gateway_client.py` name for anything new.
