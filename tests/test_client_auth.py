import os
import tempfile
import unittest
import copy

from mltf_gateway.server.constants import reload_config
import mltf_gateway.client.backend_adapter
import mltf_gateway.server.gateway_server
import mltf_gateway.client.oauth as oauth_client
import keyring
import keyring.backend
from keyring.compat import properties
import requests_mock


class TestingKeyring(keyring.backend.KeyringBackend):
    """
    In-memory keyring for testing reasons
    """

    def __init__(self):
        super().__init__()
        self.vals = {}

    @properties.classproperty
    def priority(cls) -> float:
        return -1

    def get_password(self, service, username):
        if service in self.vals:
            return self.vals.get(username, None)
        else:
            return None

    def set_password(self, service, username, password):
        if not service in self.vals:
            self.vals[service] = {}
        self.vals[service][username] = password

    def del_password(self, service, username):
        if service in self.vals:
            if username in self.vals[service]:
                del self.vals[service][username]
            if len(self.vals[service]) == 0:
                del self.vals[service]


@requests_mock.Mocker()
class ClientAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.tempDirObj = tempfile.TemporaryDirectory()
        self.tempDir = self.tempDirObj.name
        self.old_env = copy.copy(os.environ)
        os.environ["KEYCLOAK_URL"] = "https://localhost:5001"
        os.environ["MLTF_TEST_DISABLE_WEBBROWSER"] = "1"
        # Disable gateway config fetching for tests
        os.environ["MLTF_GATEWAY_URI"] = "https://localhost:5000"
        reload_config()
        self.old_keyring = keyring.get_keyring()
        keyring.set_keyring(TestingKeyring())
        mltf_gateway.client.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.server.gateway_server.RUN_DATABASE = (
            f"{self.tempDir}/gateway_run_db.pkl"
        )
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        self.tracking_uri = os.environ["MLFLOW_TRACKING_URI"] = (
            f"file://{self.tempDir}/mlflow"
        )

    def testAuthStatus(self, m):
        assert keyring.get_password("testpass", "noneuser") == None
        oauth_base = "https://localhost:5001/api/mockoauth"

        # Mock gateway config endpoint
        m.get(
            "https://localhost:5000/api/config",
            json={
                "oauth_config": {
                    "client_id": "mlflow",
                    "scopes": ["openid", "email", "profile"],
                    "issuer": "https://localhost:5001/realms/test",
                    "token_url": f"{oauth_base}/token",
                },
                "oauth_issuer": "https://localhost:5001/realms/test",
                "well_known_url": "https://localhost:5001/realms/test/.well-known/openid-configuration",
                "device_authorization_endpoint": f"{oauth_base}/auth/device",
            },
        )

        # Mock OIDC discovery
        m.get(
            "https://localhost:5001/realms/test/.well-known/openid-configuration",
            json={
                "issuer": "https://localhost:5001/realms/test",
                "authorization_endpoint": f"{oauth_base}/auth/authorize",
                "token_endpoint": f"{oauth_base}/token",
                "device_authorization_endpoint": f"{oauth_base}/auth/device",
            },
        )

        device_return = {
            "device_code": "DEVICECODE123",
            "user_code": "ABCD-1234",
            "verification_uri": f"{oauth_base}/auth/verify_client",
        }
        m.register_uri("POST", f"{oauth_base}/auth/device", json=device_return)
        token_resp = {"access_token": "TESTACCESSTOKEN", "expires_in": 3600}
        m.register_uri("POST", f"{oauth_base}/token", json=token_resp)

        res = oauth_client.get_access_token()
        print(res)

    def tearDown(self):
        os.environ = self.old_env
        reload_config()
        self.tempDirObj.cleanup()
        keyring.set_keyring(self.old_keyring)
