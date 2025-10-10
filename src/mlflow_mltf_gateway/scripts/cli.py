#
# MLTF CLI - an actual script people can run
#


import argparse
import logging

import jwt
import os
import os.path
import sys
from datetime import datetime, timezone

log = logging.getLogger("mltf-cli")

# Import OAuth2 client
from mlflow_mltf_gateway.oauth_client import (
    is_authenticated,
    get_stored_credentials,
    authenticate_with_device_flow,
    logout,
    token_expired,
)
from mlflow_mltf_gateway.backends.GatewayBackend import GatewayProjectBackend


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
    details = backend.show_details(args.run_id, args.show_logs)

    print(f"Status: {details.get('status')}")

    if "failure_reason" in details:
        print(f"Failure Reason: {details.get('failure_reason')}")

    if "logs" in details and details["logs"] is not None:
        print("--- Logs ---")
        print(details["logs"])
    elif args.show_logs:
        print("--- Logs ---")
        print("(No logs available)")


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
    ret = backend.run(
        project_uri=args.dir,
        entry_point="main",
        params={},
        version=None,
        backend_config={},
        tracking_uri="https://mlflow-test.mltf.k8s.accre.vanderbilt.edu",
        experiment_id="0",
    )
    print(f"Submitted project to MLTF: {ret['gateway_id']}")


@require_auth
def handle_delete_subcommand(args):
    """Handle the 'delete' subcommand."""
    backend = GatewayProjectBackend()
    result = backend.delete(args.run_id)
    print(result)


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
    from mlflow_mltf_gateway.flaskapp.app import create_app
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

    # Login command
    login_parser = subparsers.add_parser("login", help="Login to MLTF Gateway")

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Logout from MLTF Gateway")

    # Auth-status command
    logout_parser = subparsers.add_parser("auth-status", help="Print auth status")

    # show command
    show_parser = subparsers.add_parser("show", help="Show the status of a job")
    show_parser.add_argument("run_id", help="The ID of the run to show")
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
    if args.command == "list":
        handle_list_subcommand(args)
    elif args.command == "show":
        handle_show_subcommand(args)
    elif args.command == "submit":
        handle_submit_subcommand(args)
    elif args.command == "delete":
        handle_delete_subcommand(args)
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
