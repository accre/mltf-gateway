import unittest
import os
import tempfile
import time
import jwt
import mltf_gateway.client.backend_adapter
import mltf_gateway.server.gateway_server
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
        mltf_gateway.client.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.server.gateway_server.RUN_DATABASE = f"{self.tempDir}/gateway_run_db.pkl"
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        os.environ["MLFLOW_TRACKING_URI"] = f"file://{self.tempDir}/mlflow"
        os.environ["SLURM_TOKEN"] = "dummy-test-token"
        self.backend = RESTAdapter(gateway_uri="LOCAL")

    def tearDown(self):
        self.tempDirObj.cleanup()

class APITestCase(BasicAPITestCase):
    def test_config(self):
        backend = self.backend
        conf = backend.get_api_config()
        self.assertIsInstance(conf, dict, "Need a dict back from config endpoint")
        runs = backend.list()
        self.assertIsInstance(runs, list, "Need a dict back from job list endpoint")
        self.assertEqual(len(runs), 0, "Database should be empty initially")
        print(runs)

if __name__ == '__main__':
    unittest.main()
