#
# MLTF CLI - an actual script people can run
#

import logging
import os
import sys
from datetime import datetime, timezone

import click
import jwt
import requests

from mltf_gateway.client.mlflow_project_backend import (
    GatewayProjectBackend,
    gateway_uri,
)
from mltf_gateway.client.oauth import (
    authenticate_with_device_flow,
    get_access_token,
    get_stored_credentials,
    is_authenticated,
    logout as oauth_logout,
    token_expired,
)
from mltf_gateway.utils import get_tracking_uri

log = logging.getLogger("mltf-cli")

# Default number of most recent tasks shown by 'mltf list'
DEFAULT_LIST_PAGE_SIZE = 10


# Decorator for authentication checks
def require_auth(func):
    """Decorator to require authentication before executing a command"""

    def wrapper(*args, **kwargs):
        if not is_authenticated():
            click.echo("Authentication required. Please run 'mltf login' first.")
            sys.exit(1)
        return func(*args, **kwargs)

    return wrapper


def get_latest_submission(backend=None):
    backend = backend or GatewayProjectBackend()
    to_decode = backend.list(True, False)
    if to_decode:
        to_decode.sort(key=lambda x: x["creation_time"], reverse=True)
        return to_decode[0]["gateway_id"]
    return None


@click.group()
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
@click.pass_context
def cli(ctx, debug):
    """CLI tool for managing MLTF jobs"""
    ctx.ensure_object(dict)
    loglevel = 10 if debug else 30
    logging.basicConfig(format="%(levelname)s:%(message)s", level=loglevel)
    log.setLevel(loglevel)
    ctx.obj["debug"] = debug


@require_auth
@cli.command()
@click.option(
    "--all", "show_all", is_flag=True, help="List all jobs, not just active ones"
)
@click.option(
    "--start",
    type=click.IntRange(min=1),
    default=None,
    help="First task to show (1-based, most recent is 1)",
)
@click.option(
    "--end",
    type=click.IntRange(min=1),
    default=None,
    help="Last task to show (1-based, inclusive)",
)
@click.pass_context
def list(ctx, show_all, start, end):
    """List jobs, most recent first (shows the 10 most recent unless a range is given)"""
    backend = GatewayProjectBackend()
    to_decode = backend.list(show_all, False)
    if not to_decode:
        click.echo("No Tasks found.")
        return
    to_decode.sort(key=lambda x: x["creation_time"], reverse=True)
    total = len(to_decode)

    range_given = start is not None or end is not None
    lo = start if start is not None else 1
    hi = end if end is not None else total
    if range_given and start is not None and end is not None and start > end:
        raise click.UsageError(
            f"--start ({start}) must not be greater than --end ({end})"
        )
    hi = min(hi, total)
    if lo > total:
        click.echo(f"No tasks in range {lo}-{hi}; there are {total} task(s).")
        return
    if not range_given:
        hi = min(hi, DEFAULT_LIST_PAGE_SIZE)

    time_format = "%Y-%m-%d@%H:%M:%S"
    click.echo("Tasks:")
    for j in to_decode[lo - 1 : hi]:
        task_name = j.get("name", "")
        name_suffix = f" ({task_name})" if task_name else ""
        click.echo(
            f"  {datetime.fromtimestamp(j['creation_time'], timezone.utc).astimezone().strftime(time_format)} - {j['gateway_id']}{name_suffix}"
        )
    if not range_given and total > DEFAULT_LIST_PAGE_SIZE:
        click.echo(
            f"Showing the {DEFAULT_LIST_PAGE_SIZE} most recent of {total} tasks. Use --start/--end to view a range."
        )
    elif range_given:
        click.echo(f"Showing tasks {lo}-{hi} of {total}.")


@require_auth
@cli.command()
@click.argument("run_id", required=False, default="")
@click.option("--show-logs", is_flag=True, help="Show logs of the run")
@click.pass_context
def show(ctx, run_id, show_logs):
    """Show the status of a job"""
    backend = GatewayProjectBackend()
    if not run_id:
        run_id = get_latest_submission(backend)

    if not run_id:
        click.echo("No tasks found")
        sys.exit(1)

    details = backend.show_details(run_id, show_logs)

    click.echo(f"Status: {details.get('status')}")
    if details.get("name"):
        click.echo(f"Name: {details['name']}")
    if "failure_reason" in details:
        click.echo(f"Failure Reason: {details.get('failure_reason')}")

    if show_logs and "logs" in details and details["logs"] is not None:
        click.echo("--- Logs ---")
        click.echo(details["logs"])
    elif show_logs:
        click.echo("--- Logs ---")
        click.echo("(No logs available)")


@require_auth
@cli.command()
@click.option("--dir", "-d", default=os.path.curdir, help="Path of project to submit")
@click.option("--tracking-uri", default=None, help="MLflow tracking URI")
@click.option("--name", "-n", default=None, help="Name to give the task")
@click.pass_context
def submit(ctx, dir, tracking_uri, name):
    """Submit a new MLTF job"""
    backend = GatewayProjectBackend()
    if tracking_uri:
        tracking_uri_val = tracking_uri
    elif os.environ.get("MLFLOW_TRACKING_URI"):
        tracking_uri_val = os.environ.get("MLFLOW_TRACKING_URI")
    else:
        tracking_uri_val = get_tracking_uri()

    ret = backend.run(
        project_uri=dir,
        entry_point="main",
        params={},
        version=None,
        backend_config={},
        tracking_uri=tracking_uri_val,
        experiment_id="0",
        name=name,
    )

    click.echo(f"Submitted project to MLTF: {ret['gateway_id']}")

    return ret


@require_auth
@cli.command()
@click.argument("run_id")
@click.pass_context
def delete(ctx, run_id):
    """Delete an MLTF job"""
    backend = GatewayProjectBackend()
    result = backend.delete(run_id)
    click.echo(result)


@require_auth
@cli.command()
@click.argument("run_id")
@click.pass_context
def artifacts(ctx, run_id):
    """Show artifacts for a given run"""
    from mlflow.tracking import MlflowClient

    backend = GatewayProjectBackend()
    runs = backend.list()
    target_run_id = None
    for run in runs:
        if run["gateway_id"] == run_id:
            target_run_id = run["run_id"]
            break

    if not target_run_id:
        click.echo(f"Job with ID {run_id} not found.")
        return

    if os.environ.get("MLFLOW_TRACKING_URI"):
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    else:
        tracking_uri = get_tracking_uri()

    creds = get_access_token()
    os.environ["MLFLOW_TRACKING_TOKEN"] = creds["access_token"]

    client = MlflowClient(tracking_uri=tracking_uri)
    try:
        art_list = client.list_artifacts(target_run_id)
        if art_list:
            click.echo(f"Artifacts for run {run_id} (MLflow ID: {target_run_id}):")
            for artifact in art_list:
                presigned_url = get_presigned_artifact_url(
                    tracking_uri, target_run_id, artifact.path
                )
                click.echo(f"  {artifact.path} (Download URL: {presigned_url})")
        else:
            click.echo(f"No artifacts found for run {run_id}.")
    except Exception as e:
        click.echo(f"Error retrieving artifacts: {e}")


def get_presigned_artifact_url(tracking_uri, run_id, artifact_path):
    headers = {
        "Authorization": f"Bearer {get_stored_credentials()['access_token']}",
        "Content-Type": "application/json",
    }
    base_url = tracking_uri.rstrip("/")
    uri = f"{base_url}/ajax-api/2.0/mlflow-artifacts/presigned/artifacts/{artifact_path}?run_id={run_id}"

    log.debug(f"Getting presigned artifact URL from {uri}")
    resp = requests.get(uri, headers=headers)
    resp.raise_for_status()
    return resp.json().get("url")


@cli.command()
@click.pass_context
def login(ctx):
    """Login to MLTF Gateway"""
    click.echo("Initiating OAuth2 authentication...")
    credentials = authenticate_with_device_flow()
    if credentials:
        click.echo("Login successful!")
    else:
        click.echo("Login failed.")
        sys.exit(1)


@cli.command()
@click.pass_context
def logout(ctx):
    """Logout from MLTF Gateway"""
    oauth_logout()
    click.echo("Logged out successfully.")


@cli.command(name="auth-status")
@click.pass_context
def auth_status(ctx):
    """Print auth status"""
    creds = get_stored_credentials()
    if not creds:
        click.echo("No credentials found")
        return

    click.echo(f"Credentials found, expired? {token_expired(creds)}")
    access_decoded = jwt.decode(
        creds["access_token"], options={"verify_signature": False}
    )
    click.echo(f"  Gateway URI: {gateway_uri()}")
    click.echo(f"Token Subject: {access_decoded['sub']}")
    click.echo(f" Token Issuer: {access_decoded['iss']}")
    click.echo("Access Token:")
    curr_time = datetime.now(timezone.utc)
    access_iss = datetime.fromtimestamp(access_decoded["iat"], timezone.utc)
    access_exp = datetime.fromtimestamp(access_decoded["exp"], timezone.utc)

    click.echo(f"       Issued: {access_iss}")
    click.echo(f"      Expires: {access_exp}")
    click.echo(f"    Remaining: {access_exp - curr_time}")
    click.echo("Refresh Token:")
    refresh_decoded = jwt.decode(
        creds["refresh_token"], options={"verify_signature": False}
    )
    refresh_iss = datetime.fromtimestamp(refresh_decoded["iat"], timezone.utc)
    refresh_exp = datetime.fromtimestamp(refresh_decoded["exp"], timezone.utc)
    click.echo(f"       Issued: {refresh_iss}")
    click.echo(f"      Expires: {refresh_exp}")
    click.echo(f"    Remaining: {refresh_exp - curr_time}")


@cli.command()
@click.option("--host", default=None, help="Host to bind the server to")
@click.option("--port", default=None, type=int, help="Port to bind the server to")
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
@click.pass_context
def server(ctx, host, port, debug):
    """Start MLTF Gateway HTTP server"""
    from mltf_gateway.server.app import create_app

    app = create_app()
    host = host or os.environ.get("MLTF_HOST", "localhost")
    port = port or int(os.environ.get("MLTF_PORT", 5001))

    click.echo(f"Starting MLTF Gateway server on {host}:{port}")
    click.echo("Press Ctrl+C to stop the server")

    app.run(host=host, port=port, debug=debug)


@cli.command()
@click.pass_context
def token(ctx):
    """Print the current authentication token"""
    creds = get_access_token()
    click.echo("# This token is intended to be loaded via:")
    click.echo("#     eval `mltf token`")
    click.echo("# This will put the token in your shell environment")
    click.echo(f'export MLFLOW_TRACKING_TOKEN={creds["access_token"]}')


def main():
    cli()


if __name__ == "__main__":
    cli()
