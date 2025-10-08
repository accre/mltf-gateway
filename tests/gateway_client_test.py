import unittest

from mlflow_mltf_gateway.gateway_server import (
    get_script,
)
from mlflow_mltf_gateway.gateway_client import (
    GatewayProjectBackend,
)


class GatewayClientTestCase(unittest.TestCase):

    def test_execute_hello(self):
        project_path = get_script("test/hello_world_project")
        srv = GatewayProjectBackend()

        ret = srv.run(project_path, "main", {}, None, {}, "", "")
        ret.wait()
        self.assertEqual(
            "FINISHED",
            ret.get_status(),
        )


if __name__ == "__main__":
    unittest.main()
