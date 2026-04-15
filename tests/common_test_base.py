import os
import subprocess
import tempfile
import unittest

import mltf_gateway.backend_adapter
import mltf_gateway.gateway_server


class MockedGatewayTestBase(unittest.TestCase):
    def setUp(self):
        self.pushedEnv = {}
        self.tempDirObj = tempfile.TemporaryDirectory()
        self.tempDir = self.tempDirObj.name
        self.setEnv("TMPDIR", self.tempDir)
        mltf_gateway.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.gateway_server.RUN_DATABASE = f"{self.tempDir}/gateway_run_db.pkl"
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        self.tracking_uri = os.environ["MLFLOW_TRACKING_URI"] = f"file://{self.tempDir}/mlflow"


    def setEnv(self, key: str, value: str):
        old_env = os.environ.get(key, None)
        if old_env is not None:
            self.pushedEnv[key] = old_env
        os.environ[key] = value

    def tearDown(self):
        self.tempDirObj.cleanup()
        for k, v in self.pushedEnv.items():
            os.environ[k] = v

    @classmethod
    def setUpClass(cls):
        # Make sure there's a containerization engine available, if not these
        # tests will fail in a confusing way, so error early
        status_cmds = [["docker", "ps"],
                       ("nerdctl", "ps"),
                       ("singularity", "version"),
                       ("apptainer", "version")]
        for cmd in status_cmds:
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                # This one worked, so leave
                return
            except:
                # This one wasn't up, no problem
                pass

        raise RuntimeError("No containerization engine found for test")
