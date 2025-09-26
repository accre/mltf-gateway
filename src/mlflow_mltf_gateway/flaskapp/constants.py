import os
from dotenv import load_dotenv

load_dotenv()

# check wellknown here:
# https://keycloak.k8s.accre.vanderbilt.edu/realms/mltf-dual-login/.well-known/openid-configuration

REALM = os.environ.get("REALM", "mltf-dual-login")
KEYCLOAK_URL = os.environ.get(
    "KEYCLOAK_URL", "https://keycloak.k8s.accre.vanderbilt.edu"
)
ISSUER = f"{KEYCLOAK_URL}/realms/{REALM}"
BASE_URL = f"{ISSUER}/protocol/openid-connect"

OAUTH2_CONFIG = {
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET"),
    "authorize_url": f"{BASE_URL}/auth",
    "token_url": f"{BASE_URL}/token",
    "userinfo": {
        "url": f"{BASE_URL}/userinfo",
        "email": lambda json: json["email"],
    },
    "scopes": ["openid", "email", "profile"],
    "jwks_url": f"{BASE_URL}/certs",
    "issuer": ISSUER,
}
