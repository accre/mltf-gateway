import unittest
import os
import tempfile
import copy

import mltf_gateway.client.backend_adapter
import mltf_gateway.server.gateway_server
from mltf_gateway.server.constants import reload_config
from mltf_gateway.client.backend_adapter import RESTAdapter


class MockAPIBaseCase(unittest.TestCase):
    def configure_flaskapp(self):
        """
        Called by setUp/setUpClass just before making app instance
        """
        pass


class BasicAPITestCase(unittest.TestCase):
    def setUp(self):
        self.tempDirObj = tempfile.TemporaryDirectory()
        self.tempDir = self.tempDirObj.name
        self.old_env = copy.copy(os.environ)
        mltf_gateway.client.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.server.gateway_server.RUN_DATABASE = (
            f"{self.tempDir}/gateway_run_db.pkl"
        )
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        os.environ["MLFLOW_TRACKING_URI"] = f"file://{self.tempDir}/mlflow"
        os.environ["MLTF_EXECUTOR"] = "local"
        self.backend = RESTAdapter(gateway_uri="LOCAL")

    def tearDown(self):
        os.environ = self.old_env
        reload_config()
        self.tempDirObj.cleanup()


class ConfigEndpointTestCase(BasicAPITestCase):
    def setUp(self):
        super().setUp()
        # Set up known OIDC environment values
        os.environ["KEYCLOAK_URL"] = "https://keycloak.example.com"
        os.environ["REALM"] = "test-realm"
        os.environ["CLIENT_ID"] = "test-client"
        reload_config()

    def test_config_returns_oidc_fields(self):
        """Verify config endpoint returns OIDC discovery fields with correct values."""
        conf = self.backend.get_api_config()

        # Required fields should be present
        self.assertIn("oauth_issuer", conf)
        self.assertIn("oauth_config", conf)
        self.assertIn("well_known_url", conf)
        self.assertIn("device_authorization_endpoint", conf)

        # Verify oauth_issuer value
        expected_issuer = "https://keycloak.example.com/realms/test-realm"
        self.assertEqual(conf["oauth_issuer"], expected_issuer)

        # Verify well_known_url is derived from issuer
        expected_well_known = (
            "https://keycloak.example.com/realms/test-realm/.well-known/openid-configuration"
        )
        self.assertEqual(conf["well_known_url"], expected_well_known)

        # Verify device_authorization_endpoint is derived from issuer
        expected_device_endpoint = (
            "https://keycloak.example.com/realms/test-realm/protocol/openid-connect/device"
        )
        self.assertEqual(
            conf["device_authorization_endpoint"], expected_device_endpoint
        )

        # Verify oauth_config contains expected fields
        oauth_config = conf["oauth_config"]
        self.assertIn("client_id", oauth_config)
        self.assertIn("scopes", oauth_config)
        self.assertIn("authorize_url", oauth_config)
        self.assertIn("token_url", oauth_config)

        # Verify client_id was set from environment
        self.assertEqual(oauth_config["client_id"], "test-client")

        # Verify client_secret is not exposed
        self.assertNotIn("client_secret", oauth_config)


class APITestCase(BasicAPITestCase):
    def test_config(self):
        backend = self.backend
        conf = backend.get_api_config()
        self.assertIsInstance(conf, dict, "Need a dict back from config endpoint")
        runs = backend.list()
        self.assertIsInstance(runs, list, "Need a dict back from job list endpoint")
        self.assertEqual(len(runs), 0, "Database should be empty initially")
        print(runs)


if __name__ == "__main__":
    unittest.main()
