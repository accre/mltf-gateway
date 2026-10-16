import jwt
from flask import abort
from jwt import PyJWKClient

from .constants import OAUTH2_CONFIG

jwks_url = OAUTH2_CONFIG["jwks_url"]
issuer = OAUTH2_CONFIG["issuer"]
audience = OAUTH2_CONFIG["client_id"]

jwks_client = None


def get_jwks_client():
    global jwks_client
    if jwks_client is None:
        try:
            jwks_client = PyJWKClient(jwks_url)
        except Exception as e:
            abort(401, description=f"Failed to load JWKS from {jwks_url}: {e}")
    return jwks_client


def decode(token):
    """
    Validate and decode a JWT access token locally.
    """
    try:
        client = get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],  # or the alg your provider uses
            audience=audience,
            issuer=issuer,
        )
        return payload
    except jwt.ExpiredSignatureError:
        abort(401, description="Token expired")
    except jwt.InvalidTokenError as e:
        abort(401, description=f"Invalid token: {e}")
    except Exception as e:
        abort(401, description=f"Token validation error: {e}")
