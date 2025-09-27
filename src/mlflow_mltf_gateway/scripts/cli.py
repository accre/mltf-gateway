#
# MLTF CLI - an actual script people can run
#


import argparse
import jwt
import os.path
import sys
import datetime

# Import OAuth2 client
from mlflow_mltf_gateway.oauth_client import (
    is_authenticated,
    get_stored_credentials,
    authenticate_with_device_flow,
    logout,
    token_expired,
)


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
def handle_list_subcommand(args):
    """Handle the 'list' subcommand."""
    if args.all:
        print("Listing all items...")
    else:
        print("Listing active items...")


@require_auth
def handle_submit_subcommand(args):
    """Handle the 'submit' subcommand."""
    if args.name:
        print(f"Submitting item: {args.name}")
    else:
        print("Please provide a name for the new item.")


@require_auth
def handle_delete_subcommand(args):
    """Handle the 'delete' subcommand."""
    if args.id:
        print(f"Deleting item with ID: {args.id}")
    else:
        print("Please provide an ID to delete.")


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
    print("Access Token:")
    access_decoded = jwt.decode(creds['access_token'], options={"verify_signature": False})
    # TODO: I believe there is some sort of print indent helper? Look into that
    # TODO: Convert timestamps into human readable objects
    print(f"  Subject: {access_decoded['sub']}")
    print(f"   Issuer: {access_decoded['iss']}")
    print(f"   Issued: {access_decoded['iat']}")
    print(f"  Expires: {access_decoded['exp']}")
    print("Refresh Token:")
    refresh_decoded = jwt.decode(creds['refresh_token'], options={"verify_signature": False})
    print(f"  Subject: {refresh_decoded['sub']}")
    print(f"   Issuer: {refresh_decoded['iss']}")
    print(f"   Issued: {refresh_decoded['iat']}")
    print(f"  Expires: {refresh_decoded['exp']}")

def handle_server_subcommand(args):
    """Handle the 'server' subcommand - start HTTP server"""
    from src.mlflow_mltf_gateway.flaskapp.app import create_app
    import os

    app = create_app()
    # Get host and port from arguments or use defaults
    host = args.host or os.environ.get("MLTF_HOST", "localhost")
    port = args.port or int(os.environ.get("MLTF_PORT", 5000))

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
        "--name",
        required=True,
        help="Name of the item to submit",
    )
    submit_parser.add_argument(
        "--dir",
        "-d",
        required=True,
        default=os.path.curdir,
        help="Path of inputs to submit",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an MLTF job")
    delete_parser.add_argument("--id", required=True, help="ID of the job to delete")

    # Login command
    login_parser = subparsers.add_parser("login", help="Login to MLTF Gateway")

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Logout from MLTF Gateway")

    # Auth-status command
    logout_parser = subparsers.add_parser("auth-status", help="Print auth status")

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
