#
# MLTF CLI - an actual script people can run
#

# Parser calls (after subcommand definitions)
import argparse
import sys

# Import OAuth2 client
from mlflow_mltf_gateway.oauth_client import is_authenticated, authenticate_with_device_flow, logout, add_auth_header_to_request


# Subcommand function definitions (grouped together)
def handle_list_subcommand(args):
    """Handle the 'list' subcommand."""
    if not is_authenticated():
        print("Authentication required. Please run 'mltf login' first.")
        sys.exit(1)

    if args.all:
        print("Listing all items...")
    else:
        print("Listing active items...")


def handle_create_subcommand(args):
    """Handle the 'create' subcommand."""
    if not is_authenticated():
        print("Authentication required. Please run 'mltf login' first.")
        sys.exit(1)

    if args.name:
        print(f"Creating item: {args.name}")
    else:
        print("Please provide a name for the new item.")


def handle_delete_subcommand(args):
    """Handle the 'delete' subcommand."""
    if not is_authenticated():
        print("Authentication required. Please run 'mltf login' first.")
        sys.exit(1)

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


def create_parser():
    parser = argparse.ArgumentParser(description="CLI tool for managing MLTF jobs")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument(
        "--all", action="store_true", help="List all jobs, not just active ones"
    )

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new MLTF job")
    create_parser.add_argument(
        "--name", required=True, help="Name of the item to create"
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an MLTF job")
    delete_parser.add_argument("--id", required=True, help="ID of the job to delete")

    # Login command
    login_parser = subparsers.add_parser("login", help="Login to MLTF Gateway")

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Logout from MLTF Gateway")

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "list":
        handle_list_subcommand(args)
    elif args.command == "create":
        handle_create_subcommand(args)
    elif args.command == "delete":
        handle_delete_subcommand(args)
    elif args.command == "login":
        handle_login_subcommand(args)
    elif args.command == "logout":
        handle_logout_subcommand(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
