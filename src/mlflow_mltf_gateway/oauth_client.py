"""
OAuth2 Client Implementation for MLflow MLTF Gateway

This module provides OAuth2 authentication capabilities for the CLI client,
including device flow authentication and token management.
"""

import os
import time
import webbrowser
from typing import Optional, Dict, Any


import requests

# Configuration - These should be configurable via environment variables or config file
CLIENT_ID = os.environ.get("MLTF_CLIENT_ID", "mlflow")
AUTHORIZATION_ENDPOINT = os.environ.get(
    "MLTF_AUTH_URL",
    "https://keycloak.k8s.accre.vanderbilt.edu/realms/mltf-dual-login/protocol/openid-connect/auth/device",
)
TOKEN_ENDPOINT = os.environ.get(
    "MLTF_TOKEN_URL",
    "https://keycloak.k8s.accre.vanderbilt.edu/realms/mltf-dual-login/protocol/openid-connect/token",
)
SCOPES = os.environ.get("MLTF_SCOPES", "read write").split()

# Used to keep user from having to type a password with each CLI call
if "MLTF_KEYRING_PASSWORD" in os.environ:
    os.environ["KEYRING_CRYPTFILE_PASSWORD"] = os.environ.get("MLTF_KEYRING_PASSWORD")
# Prevent DBUS backend from being visible since this doesn't seem to work headless
if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
    del os.environ["DBUS_SESSION_BUS_ADDRESS"]

import keyring

DID_WARN_KEYRING = False


def get_stored_credentials() -> Optional[Dict[str, Any]]:
    """Retrieve stored credentials from keyring"""
    start_time = time.time()
    try:
        access_token = keyring.get_password("mltf_gateway", "access_token")
        refresh_token = keyring.get_password("mltf_gateway", "refresh_token")
        token_expires_at = keyring.get_password("mltf_gateway", "expires_at")

        if access_token and refresh_token:
            end_time = time.time()
            # If it takes longer than 5 secs to retrieve the token, this implies the
            # user was prompted for a password to unlock the encrypted keyring
            # Let them know they can set a variable with the password if they
            # want
            global DID_WARN_KEYRING
            if not DID_WARN_KEYRING and ((end_time - start_time) > 5.0):
                DID_WARN_KEYRING = True
                print(
                    """
To prevent prompting for a password, you can cache the password with

  export MLTF_KEYRING_PASSWORD=<your password>

Note: This password should be kept secure since it can unlock the secure
      token storage. Anyone with the password will be able to access
      your tokens

"""
                )
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": token_expires_at,
            }

    except Exception as e:
        print(f"Error retrieving stored credentials {e}")

    return None


def store_credentials(access_token: str, refresh_token: str, expires_at: int):
    """Store credentials securely using keyring"""
    try:
        keyring.set_password("mltf_gateway", "access_token", access_token)
        keyring.set_password("mltf_gateway", "refresh_token", refresh_token)
        keyring.set_password("mltf_gateway", "expires_at", str(expires_at))
        print("Credentials stored securely")
    except Exception as e:
        print(f"Error storing credentials: {e}")


def clear_stored_credentials():
    """Clear stored credentials from keyring"""
    try:
        keyring.delete_password("mltf_gateway", "access_token")
        keyring.delete_password("mltf_gateway", "refresh_token")
        keyring.delete_password("mltf_gateway", "expires_at")
        print("Stored credentials cleared")
    except Exception as e:
        print(f"Error clearing stored credentials: {e}")


def request_device_code():
    """Request device code from OAuth2 provider"""
    data = {"client_id": CLIENT_ID, "scope": " ".join(SCOPES)}

    try:
        endpoint_uri = AUTHORIZATION_ENDPOINT.replace("/authorize", "/device/code")
        response = requests.post(endpoint_uri, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error requesting device code: {e}")
        return None


def poll_token(device_code, interval=5):
    """Poll for access token using device code"""
    data = {
        "client_id": CLIENT_ID,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }

    # Go ahead and sleep a second since it will be a bit before the user gets
    # to the page and whatnot
    time.sleep(10)
    while True:
        try:
            response = requests.post(TOKEN_ENDPOINT, data=data)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                result = response.json()
                if result.get("error") == "authorization_pending":
                    print("Waiting for user authorization...")
                    time.sleep(interval)
                    continue
                elif result.get("error") == "slow_down":
                    # Increase polling interval as per spec
                    interval += 5
                    print(f"Slowing down polling, new interval: {interval}s")
                    time.sleep(interval)
                    continue
                else:
                    print(f"Authorization error: {result}")
                    return None
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error polling for token: {e}")
            return None


def refresh_access_token(refresh_token):
    """Refresh access token using refresh token"""
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    try:
        response = requests.post(TOKEN_ENDPOINT, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing token: {e}")
        return None


def authenticate_with_device_flow() -> Optional[Dict[str, Any]]:
    """Main function to perform OAuth2 device flow authentication"""

    # Check for existing stored credentials
    stored = get_stored_credentials()
    if stored:
        print("Using existing stored credentials")
        return stored

    print("Starting MLTF Gateway OAuth2 Device Flow...")

    # Step 1: Request device code
    device_response = request_device_code()
    if not device_response:
        print("Failed to obtain device code")
        return None

    device_code = device_response.get("device_code")
    user_code = device_response.get("user_code")
    verification_uri = device_response.get("verification_uri")
    expires_in = device_response.get("expires_in", 300)  # Default 5 minutes

    print(f"Device code: {user_code}")
    print(f"Visit {verification_uri} to authorize this application")

    # Open browser if possible
    try:
        webbrowser.open(verification_uri)
    except Exception as e:
        # Most of our users will be headless, so don't complain if se cant
        # open a browser
        pass

    # Step 2: Poll for access token
    print("Waiting for user authorization...")

    token_response = poll_token(device_code)
    if not token_response:
        print("Failed to obtain access token")
        return None

    # Store credentials securely
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_at = int(time.time()) + token_response.get("expires_in", 3600)

    store_credentials(access_token, refresh_token, expires_at)

    print("Authentication successful!")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }


def get_access_token() -> Optional[Dict[str, Any]]:
    """Get a valid access token"""
    # Check if we have stored credentials
    creds = get_stored_credentials()

    if not creds:
        print("No stored credentials found, performing device flow authentication")
        return authenticate_with_device_flow()

    # If token is expired, try to refresh it
    if token_expired(creds):
        print("Access token expired, attempting to refresh...")
        return attempt_token_refresh(creds)

    return creds


def attempt_token_refresh(creds):
    """Try to make a new access token from refresh token"""
    if token_expired(creds):
        refresh_response = refresh_access_token(creds["refresh_token"])

        if refresh_response:
            access_token = refresh_response.get("access_token")
            expires_at = int(time.time()) + refresh_response.get("expires_in", 3600)

            # Update stored credentials
            store_credentials(access_token, creds["refresh_token"], expires_at)

            return {
                "access_token": access_token,
                "refresh_token": creds["refresh_token"],
                "expires_at": expires_at,
            }
        return None
    return creds


def add_auth_header_to_request(headers: dict) -> dict:
    """Add OAuth2 Bearer token to request headers if available"""
    credentials = get_access_token()
    if credentials and "access_token" in credentials:
        headers["Authorization"] = f'Bearer {credentials["access_token"]}'
    return headers


def token_expired(creds):
    curr_time = int(time.time())
    exp_time = int(creds.get("expires_at", 0))
    if curr_time > exp_time:
        return True
    return False


def is_authenticated() -> bool:
    """Check if the client has valid authentication"""
    creds = get_stored_credentials()
    if not creds:
        return False
    # Check if token is still valid
    if token_expired(creds):
        if attempt_token_refresh(creds):
            # nonnull means we got good creds back
            return True
        else:
            return False
    return True


def logout():
    """Logout by clearing stored credentials"""
    clear_stored_credentials()
    print("Logged out successfully")
