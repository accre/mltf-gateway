#
# MLTF CLI - an actual script people can run
#

import argparse
import requests
import logging
import os
import os.path
import sys
from datetime import datetime, timezone

import jwt

from mltf_gateway.client.mlflow_project_backend import GatewayProjectBackend

# Import OAuth2 client
from mltf_gateway.client.oauth import (
    is_authenticated,
    get_stored_credentials,
    authenticate_with_device_flow,
    logout,
    token_expired,
)
from mltf_gateway.utils import get_tracking_uri

log = logging.getLogger("mltf-cli")

# Decorator for authentication checks
def require_auth(func):
    """Decorator to require authentication before executing a command"""

    def wrapper(args):
        if not is_authenticated():
            print("Authentication required. Please run 'mltf login' first.")
            sys.exit(1)
        return func(args)

    return wrapper


# Subcommand function definitions (grouped together)
@require_auth
def handle_show_subcommand(args):
    """Handle the 'show' subcommand."""
    backend = GatewayProjectBackend()
    run_id = args.run_id
    if not run_id:
        run_id = get_latest_submission(backend)

    if not run_id:
        print("No tasks found")
        sys.exit(1)

    details = backend.show_details(run_id, args.show_logs)

    print(f"Status: {details.get('status')}")
    import pprint
    pprint.pprint(details)
    if "failure_reason" in details:
        print(f"Failure Reason: {details.get('failure_reason')}")

    if args.show_logs and "logs" in details and details["logs"] is not None:
        print("--- Logs ---")
        print(details["logs"])
    elif args.show_logs:
        print("--- Logs ---")
        print("(No logs available)")

@require_auth
def get_latest_submission(backend = None) -> str:
    backend = backend or GatewayProjectBackend()
    to_decode = backend.list(True, False)
    if to_decode:
        print("Tasks:")
        to_decode.sort(key=lambda x: x["creation_time"], reverse=True)
        return to_decode[0]['gateway_id']
    else:
        return False

# Subcommand function definitions (grouped together)
@require_auth
def handle_list_subcommand(args):
    """Handle the 'list' subcommand."""
    backend = GatewayProjectBackend()
    to_decode = backend.list(args.all, False)
    if to_decode:
        print("Tasks:")
        to_decode.sort(key=lambda x: x["creation_time"], reverse=True)
        for j in to_decode:
            time_format = "%Y-%m-%d@%H:%M:%S"
            # Jeeze this is long...
            print(
                f"  {datetime.fromtimestamp(j['creation_time'], timezone.utc).astimezone().strftime(time_format)} - {j['gateway_id']}"
            )
    else:
        print("No Tasks found.")


@require_auth
def handle_submit_subcommand(args):
    """Handle the 'submit' subcommand."""

    backend = GatewayProjectBackend()
    tracking_uri = get_tracking_uri()
    if os.environ.get("MLFLOW_TRACKING_URI"):
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if hasattr(args, "tracking_uri"):
        tracking_uri = args.tracking_uri

    ret = backend.run(
        project_uri=args.dir,
        entry_point="main",
        params={},
        version=None,
        backend_config={},
        tracking_uri=tracking_uri,
        # FIXME: Let user set their own experiment ID
        experiment_id="0",
    )

    print(f"Submitted project to MLTF: {ret['gateway_id']}")
    return ret


@require_auth
def handle_delete_subcommand(args):
    """Handle the 'delete' subcommand."""
    backend = GatewayProjectBackend()
    result = backend.delete(args.run_id)
    print(result)


@require_auth
def handle_artifacts_subcommand(args):
    """Handle the 'artifacts' subcommand."""
    from mlflow.tracking import MlflowClient
    from mltf_gateway.oauth import get_access_token

    backend = GatewayProjectBackend()
    # List all runs to find the mapping from gateway_id to run_id
    runs = backend.list()
    target_run_id = None
    for run in runs:
        if run["gateway_id"] == args.run_id:
            target_run_id = run["run_id"]
            break

    if not target_run_id:
        print(f"Job with ID {args.run_id} not found.")
        return

    tracking_uri = get_tracking_uri()
    if os.environ.get("MLFLOW_TRACKING_URI"):
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")

    # Ensure tracking token is set for authentication with the tracking server
    creds = get_access_token()
    os.environ["MLFLOW_TRACKING_TOKEN"] = creds["access_token"]

    client = MlflowClient(tracking_uri=tracking_uri)
    try:
        artifacts = client.list_artifacts(target_run_id)
        if artifacts:
            print(f"Artifacts for run {args.run_id} (MLflow ID: {target_run_id}):")
            for artifact in artifacts:
                # Construct the download URL as requested
                base_url = tracking_uri.rstrip("/")
                import pprint
                pprint.pprint(artifact)
                download_url = f"{base_url}/get-artifact?path={artifact.path}&run_uuid={target_run_id}"
                get_presigned_artifact_url(tracking_uri, target_run_id, artifact.path)
                print(f"  {artifact.path} (Download URL: {download_url})")
        else:
            print(f"No artifacts found for run {args.run_id}.")
    except Exception as e:
        print(f"Error retrieving artifacts: {e}")

def get_presigned_artifact_url(tracking_uri, run_id, artifact_path):
    request = {"run_id": run_id,
               "path": artifact_path}
    headers = {"Authorization": f"Bearer {get_stored_credentials()['access_token']}",
               "Content-Type": "application/json"}
    import pprint
    pprint.pprint(headers)
    uri = f"https://mlflow.mltf.vu/ajax-api/2.0/mlflow-artifacts/presigned/35/9475ca9ca1ad4227be17f97d9b805316/artifacts/myTrainingScript.py"

    log.debug(f"Getting artifacts from {uri}")
    resp = requests.get(uri, headers=headers)
    print(resp.text)
    resp.raise_for_status()
    import pprint
    pprint.pprint(resp.json())

def handle_login_subcommand(args):
    """Handle the 'login' subcommand."""
    print("Initiating OAuth2 authentication...")
    credentials = authenticate_with_device_flow()
    if credentials:
        print("Login successful!")
    else:
        print("Login failed.")
        sys.exit(1)


def handle_logout_subcommand(args):
    """Handle the 'logout' subcommand."""
    logout()
    print("Logged out successfully.")


def handle_auth_status_subcommand(args):
    """Handle the 'auth_status' subcommand."""
    creds = get_stored_credentials()
    if not creds:
        print("No credentials found")
        return

    print(f"Credentials found, expired? {token_expired(creds)}")
    access_decoded = jwt.decode(
        creds["access_token"], options={"verify_signature": False}
    )
    print(f"Token Subject: {access_decoded['sub']}")
    print(f"Token Issuer: {access_decoded['iss']}")
    print("Access Token:")
    curr_time = datetime.now(timezone.utc)
    access_iss = datetime.fromtimestamp(access_decoded["iat"], timezone.utc)
    access_exp = datetime.fromtimestamp(access_decoded["exp"], timezone.utc)
    # TODO: I believe there is some sort of print indent helper? Look into that
    # TODO: Convert timestamps into human readable objects

    print(f"    Issued: {access_iss}")
    print(f"   Expires: {access_exp}")
    print(f" Remaining: {access_exp - curr_time}")
    print("Refresh Token:")
    refresh_decoded = jwt.decode(
        creds["refresh_token"], options={"verify_signature": False}
    )
    refresh_iss = datetime.fromtimestamp(refresh_decoded["iat"], timezone.utc)
    refresh_exp = datetime.fromtimestamp(refresh_decoded["exp"], timezone.utc)
    print(f"    Issued: {refresh_iss}")
    print(f"   Expires: {refresh_exp}")
    print(f" Remaining: {refresh_exp - curr_time}")


def handle_server_subcommand(args):
    """Handle the 'server' subcommand - start HTTP server"""
    from mltf_gateway.server.app import create_app
    import os

    app = create_app()
    # Get host and port from arguments or use defaults
    host = args.host or os.environ.get("MLTF_HOST", "localhost")
    port = args.port or int(os.environ.get("MLTF_PORT", 5001))

    print(f"Starting MLTF Gateway server on {host}:{port}")
    print("Press Ctrl+C to stop the server")

    # Start the Flask development server
    app.run(host=host, port=port, debug=args.debug)


def create_parser():
    parser = argparse.ArgumentParser(description="CLI tool for managing MLTF jobs")
    parser.add_argument("--debug", dest="debug", default=False, action='store_true')
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument(
        "--all", action="store_true", help="List all jobs, not just active ones"
    )

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a new MLTF job")
    submit_parser.add_argument(
        "--dir",
        "-d",
        default=os.path.curdir,
        help="Path of project to submit",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an MLTF job")
    delete_parser.add_argument("run_id", help="ID of the job to delete")

    # Artifacts command
    artifacts_parser = subparsers.add_parser(
        "artifacts", help="Show artifacts for a given run"
    )
    artifacts_parser.add_argument("run_id", help="ID of the run to show artifacts for")

    # Login command
    login_parser = subparsers.add_parser("login", help="Login to MLTF Gateway")

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Logout from MLTF Gateway")

    # Auth-status command
    logout_parser = subparsers.add_parser("auth-status", help="Print auth status")

    # show command
    show_parser = subparsers.add_parser("show", help="Show the status of a job")
    show_parser.add_argument("run_id", help="The ID of the run to show", default="", nargs="?")
    show_parser.add_argument(
        "--show-logs", action="store_true", help="Show logs of the run"
    )

    # Server command
    server_parser = subparsers.add_parser(
        "server", help="Start MLTF Gateway HTTP server"
    )
    server_parser.add_argument("--host", help="Host to bind the server to")
    server_parser.add_argument("--port", type=int, help="Port to bind the server to")
    server_parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    loglevel = logging.DEBUG if args.debug else logging.CRITICAL
    logging.basicConfig(format="%(levelname)s:%(message)s", level=loglevel)
    if args.command == "list":
        handle_list_subcommand(args)
    elif args.command == "show":
        handle_show_subcommand(args)
    elif args.command == "submit":
        handle_submit_subcommand(args)
    elif args.command == "delete":
        handle_delete_subcommand(args)
    elif args.command == "artifacts":
        handle_artifacts_subcommand(args)
    elif args.command == "login":
        handle_login_subcommand(args)
    elif args.command == "logout":
        handle_logout_subcommand(args)
    elif args.command == "auth-status":
        handle_auth_status_subcommand(args)
    elif args.command == "server":
        handle_server_subcommand(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
