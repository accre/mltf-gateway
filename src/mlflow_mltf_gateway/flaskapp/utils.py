import time
import secrets
from functools import wraps
from urllib.parse import urlencode
import requests

from flask_login import login_user
from flask import current_app, session, abort, request, g, jsonify

from .extensions import db
from .models.user import User
from .models.token import Token
from .jwt_decoder import decode
from .constants import OAUTH2_CONFIG


def init_db():
    """Initialize the database and create tables if they do not exist"""
    with current_app.app_context():
        db.create_all()
    print("Database initialized and tables created.")


def reset_db():
    """Dangerous: drops and recreates all tables"""
    with current_app.app_context():
        db.drop_all()
        db.create_all()
    print("Database reset complete.")


def handle_user_login(email, oauth_response=None, auth_code=None, is_token_flow=False):
    """
    Handle user login by creating or retrieving a user and logging them in
    Args:
        email (str): The email of the user
        oauth_response (dict, optional): The OAuth2 response data
        auth_code (str, optional): The authorization code from OAuth2
        is_token_flow (bool): Whether this is a token-based flow
    Returns: None
    """
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None:
        user = User(email=email, username=email.split("@")[0])
        db.session.add(user)
        db.session.commit()

    login_user(user)

    # Optionally, store OAuth2 tokens or other info in the token database
    if oauth_response:
        token = Token(
            user_id=user.id,
            access_token=oauth_response.get("access_token"),
            refresh_token=oauth_response.get("refresh_token"),
            token_type=oauth_response.get("token_type"),
            expires_in=oauth_response.get("expires_in"),
            scope=oauth_response.get("scope"),
        )
        db.session.add(token)
        db.session.commit()

    if not is_token_flow:
        # we will use the auth_code to fetch tokens later if needed
        session["auth_code"] = auth_code
        print(f"User {user.email} logged in.")


def get_token_url(redirect_uri, state=None) -> str:
    """
    Generate a mock URL for obtaining OAuth2 tokens
    Args:
        redirect_uri (str): The redirect URI for the OAuth2 flow
        state (str): The state parameter for CSRF protection
    Returns:
        str: A URL that can be followed to obtain OAuth2 tokens
    """
    if state is None:
        session["oauth2_state"] = secrets.token_urlsafe(16)

    # create a query string with all the OAuth2 parameters
    qs = urlencode(
        {
            "client_id": OAUTH2_CONFIG["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(OAUTH2_CONFIG["scopes"]),
            "state": session["oauth2_state"],
        }
    )

    token_url = OAUTH2_CONFIG["authorize_url"] + "?" + qs
    return token_url


def get_auth_token(client_id, code, token_url, redirect_uri) -> dict:
    """
    Exchange an authorization code for an access token
    Args:
        client_id (str): The OAuth2 client ID
        code (str): The authorization code received from the OAuth2 provider
        token_url (str): The OAuth2 token endpoint URL
    Returns:
    dict: The OAuth2 token response
    """
    # exchange the authorization code for an access token
    post_data = {
        "client_id": client_id,
        # 'client_secret': provider_data['client_secret'],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    response = requests.post(
        token_url, data=post_data, timeout=60, headers={"Accept": "application/json"}
    )
    if response.status_code != 200:
        abort(401)

    oauth_response = response.json()
    oauth2_token = oauth_response.get("access_token")
    if not oauth2_token:
        abort(401)

    return oauth_response


# Cache userinfo responses per token
_userinfo_cache = {}


def get_userinfo(token):
    cached = _userinfo_cache.get(token)
    if cached and cached["expires_at"] > time.time():
        return cached["data"]

    resp = requests.get(
        OAUTH2_CONFIG["userinfo"]["url"],
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None

    data = resp.json()
    # Assume provider includes exp in token response or use a TTL (e.g. 5 min)
    _userinfo_cache[token] = {"data": data, "expires_at": time.time() + 300}
    return data


def require_oauth_token(f):
    """
    Decorator to protect API endpoints with a valid OAuth2 access token.
    Checks 'Authorization: Bearer <token>' header.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif "access_token" in request.args:
            # optional: allow ?access_token=... as a fallback
            token = request.args.get("access_token")

        if not token:
            return jsonify({"error": "Missing access token"}), 401

        try:
            decoded = decode(token)
            if not decoded:
                return jsonify({"error": "Invalid or expired token"}), 401
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        # make g.user available in the endpoint
        # optionally, you could also create a User object in the DB here
        # and associate the token with that user
        g.user = {
            "email": decoded.get("email", "NA"),
            "username": decoded.get("name", "NA"),
            "runtime_token": token,
        }

        return f(*args, **kwargs)

    return decorated_function
