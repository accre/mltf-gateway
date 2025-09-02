import unittest

from mlflow.entities import RunStatus

from mlflow_mltf_gateway.backend_adapter import LocalAdapter
from mlflow_mltf_gateway.gateway_server import (
    GatewayRunDescription,
    GatewayServer,
    get_script,
    MovableFileReference,
    SLURMExecutor,
)
from mlflow_mltf_gateway.gateway_client import (
    GatewayProjectBackend,
)
from mlflow_mltf_gateway.client_submitted_run import GatewaySubmittedRun


class GatewayClientTestCase(unittest.TestCase):

    def test_execute_hello(self):
        project_path = get_script("test/hello_world_project")
        srv = GatewayProjectBackend()

        ret = srv.run(project_path, "main", {}, None, {}, "", "")
        self.assertIsInstance(ret, GatewaySubmittedRun)
        ret.wait()
        self.assertEqual(
            "FINISHED",
            # RunStatus.to_string(RunStatus.FINISHED),
            ret.get_status(),
        )


if __name__ == "__main__":
    unittest.main()
