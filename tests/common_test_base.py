import os
import subprocess
import tempfile
import unittest

from flask import Flask

import mltf_gateway.client.backend_adapter
import mltf_gateway.server.gateway_server
from mltf_gateway.server.extensions import db


def container_engine_available() -> bool:
    """
    Probe for a running containerization engine. Tests which actually run
    containers should gate on this; the MLTF_DEBUG_NO_CONTAINER tests don't need it
    """
    status_cmds = [
        ["docker", "ps"],
        ("nerdctl", "ps"),
        ("singularity", "version"),
        ("apptainer", "version"),
    ]
    for cmd in status_cmds:
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)
            # This one worked
            return True
        except Exception:
            # This one wasn't up, no problem
            pass
    return False


class MockedGatewayTestBase(unittest.TestCase):
    def setUp(self):
        self.pushedEnv = {}
        self.tempDirObj = tempfile.TemporaryDirectory()
        self.tempDir = self.tempDirObj.name
        self.setEnv("TMPDIR", self.tempDir)
        mltf_gateway.client.backend_adapter.INPROCESS_GATEWAY_APP = None
        mltf_gateway.server.gateway_server.RUN_DATABASE = (
            f"{self.tempDir}/gateway_run_db.pkl"
        )
        os.environ["DATABASE_URL"] = f"sqlite:///:memory:"
        self.tracking_uri = os.environ["MLFLOW_TRACKING_URI"] = (
            f"file://{self.tempDir}/mlflow"
        )

        # The gateway server persists runs through SQLAlchemy, so give each
        # test its own in-memory database and an active app context
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
        db.init_app(app)
        self.app = app
        self.app_ctx = app.app_context()
        self.app_ctx.push()
        db.create_all()

    def setEnv(self, key: str, value: str):
        old_env = os.environ.get(key, None)
        if old_env is not None:
            self.pushedEnv[key] = old_env
        os.environ[key] = value

    def tearDown(self):
        db.session.remove()
        self.app_ctx.pop()
        self.tempDirObj.cleanup()
        for k, v in self.pushedEnv.items():
            os.environ[k] = v

    @classmethod
    def setUpClass(cls):
        # Record whether a containerization engine is running. Tests that need
        # one should use unittest.skipUnless with container_engine_available()
        # so the no-container (MLTF_DEBUG_NO_CONTAINER) tests can still run
        cls.CONTAINER_ENGINE_AVAILABLE = container_engine_available()
