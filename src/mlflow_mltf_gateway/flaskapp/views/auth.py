"""
Authentication blueprint for the Flask application
"""

import secrets
import requests
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    request,
    redirect,
    session,
    url_for,
)

from flask_login import current_user
from flask_login import logout_user
from ..utils import handle_user_login, get_auth_token, get_token_url
from ..constants import OAUTH2_CONFIG

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/logout")
def logout():
    """
    Handle user logout
    Returns:
        Redirect to landing page after logout
    """
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("landing"))


@auth_bp.route("/login")
def login():
    """
    Redirect the user to the OAuth2 provider for authentication

    Returns: A redirect response to the OAuth2 provider's authorization URL
    """
    if not current_user.is_anonymous:
        return redirect(url_for("landing"))

    provider_data = OAUTH2_CONFIG
    if provider_data is None:
        abort(404)

    # generate a random string for the state parameter
    session["oauth2_state"] = secrets.token_urlsafe(16)
    redirect_uri = url_for("auth.oauth2_callback", _external=True)
    token_url = get_token_url(redirect_uri=redirect_uri, state=session["oauth2_state"])
    # redirect the user to the OAuth2 provider authorization URL
    return redirect(token_url)


@auth_bp.route("/callback")
def oauth2_callback():
    """
    Handle the OAuth2 callback from the provider
    Args:
        api: Optional parameter to identify if this is an API call
        token: Optional parameter to identify if this is a token request
    Returns:
    """
    is_token_flow = request.args.get("token", "false").lower() == "true"
    is_api_flow = request.args.get("api", "false").lower() == "true"

    # only apply if this is not a token flow or api flow and the user is already logged in
    if not (is_token_flow or is_api_flow) and not current_user.is_anonymous:
        return redirect(url_for("landing"))

    provider_data = OAUTH2_CONFIG
    if provider_data is None:
        abort(404)

    # if there was an authentication error, flash the error messages and exit
    if "error" in request.args:
        for k, v in request.args.items():
            if k.startswith("error"):
                flash(f"{k}: {v}")
        return redirect(url_for("landing"))

    # make sure that the state parameter matches the one we created in the
    # authorization request

    if not (is_token_flow or is_api_flow) and request.args["state"] != session.get(
        "oauth2_state"
    ):
        abort(401)

    # make sure that the authorization code is present
    if "code" not in request.args:
        abort(401)

    if is_token_flow:
        redirect_uri = url_for("auth.oauth2_callback", token=True, _external=True)
    elif is_api_flow:
        redirect_uri = url_for("auth.oauth2_callback", api=True, _external=True)
    elif is_token_flow and is_api_flow:
        redirect_uri = url_for(
            "auth.oauth2_callback", token=True, api=True, _external=True
        )
    else:
        redirect_uri = url_for("auth.oauth2_callback", _external=True)
    oauth_response = get_auth_token(
        provider_data["client_id"],
        request.args["code"],
        provider_data["token_url"],
        redirect_uri,
    )
    oauth2_token = oauth_response.get("access_token")
    # use the access token to get the user's email address
    response = requests.get(
        provider_data["userinfo"]["url"],
        headers={
            "Authorization": "Bearer " + oauth2_token,
            "Accept": "application/json",
        },
        timeout=60,
    )
    if response.status_code != 200:
        abort(401)
    email = provider_data["userinfo"]["email"](response.json())

    # creates or retrieves a user from the database and logs them in
    # maintains a session for the user
    handle_user_login(
        email, oauth_response, request.args["code"], is_token_flow=is_token_flow
    )
    if is_api_flow:
        return jsonify({"success": True, **oauth_response}), 200

    if is_token_flow:
        token_details = f"""
            <h2>Token Generated Successfully with following details:</h2>
            <p> Note: Please store the access token securely. This is the only time it will be displayed.</p> 
            <p><strong>Access Token:</strong> <button onclick="copyText('token')"> Copy </button> </p>
            <pre id="token"> { oauth_response.get('access_token')}</pre>
            <p><strong>Refresh Token:</strong> <button onclick="copyText('refresh')"> Copy </button> </p>
            <pre id="refresh"> { oauth_response.get('refresh_token', 'N/A')}</pre>
            <p><strong>Expires In:</strong> {oauth_response.get('expires_in', 'N/A')} seconds</p>
        """
        flash(token_details)
        return redirect(url_for("token.index"))

    return redirect(url_for("landing"))
