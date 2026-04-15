import os
import tempfile
import unittest
import copy

from mltf_gateway.flaskapp.constants import reload_config
import mltf_gateway.backend_adapter
import mltf_gateway.gateway_server
import mltf_gateway.oauth_client as oauth_client
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
        self.old_oauth_token = oauth_client.TOKEN_ENDPOINT
        self.old_oauth_authorization = oauth_client.AUTHORIZATION_ENDPOINT
        mock_oauth_base = "https://localhost:5001/api/mockoauth"
        oauth_client.TOKEN_ENDPOINT = f"{mock_oauth_base}/token"
        oauth_client.AUTHORIZATION_ENDPOINT = f"{mock_oauth_base}/auth/device"
        reload_config()
        self.old_keyring = keyring.get_keyring()
        keyring.set_keyring(TestingKeyring())
        mltf_gateway.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.gateway_server.RUN_DATABASE = f"{self.tempDir}/gateway_run_db.pkl"
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        self.tracking_uri = os.environ["MLFLOW_TRACKING_URI"] = f"file://{self.tempDir}/mlflow"

    def testAuthStatus(self, m):
        assert (keyring.get_password("testpass", "noneuser") == None)
        oauth_base = "https://localhost:5001/api/mockoauth"
        device_return = {
            "device_code": "DEVICECODE123",
            "user_code": "ABCD-1234",
            "verification_uri": f"{oauth_base}/auth/verify_client"
        }
        to_mock = f"{oauth_base}/auth/device"
        m.register_uri("POST", to_mock, json=device_return)
        token_resp = {'access_token': 'TESTACCESSTOKEN',
                      'expires_in': 3600}
        m.register_uri("POST", f"{oauth_base}/token", json=token_resp)
        res = oauth_client.get_access_token()
        print(res)

    def tearDown(self):
        os.environ = self.old_env
        reload_config()
        oauth_client.TOKEN_ENDPOINT = self.old_oauth_token
        oauth_client.AUTHORIZATION_ENDPOINT = self.old_oauth_authorization
        self.tempDirObj.cleanup()
        keyring.set_keyring(self.old_keyring)


if __name__ == '__main__':
    unittest.main()
