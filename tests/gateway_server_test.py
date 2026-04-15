import os.path
import shutil
import tempfile
import unittest

from mlflow.entities import RunStatus

from mltf_gateway.gateway_server import (
    GatewayRunDescription,
    GatewayServer,
    get_script,
    MovableFileReference,
    SLURMExecutor,
)
from mltf_gateway.submitted_runs.server_run import (
    ServerSideSubmittedRunDescription,
)
from tests.common_test_base import MockedGatewayTestBase


class GatewayServerTest(MockedGatewayTestBase):
    def test_getscript(self):
        pass_path = get_script("inside.sh")
        self.assertEqual(os.path.exists(pass_path), True)
        self.assertRaises(RuntimeError, get_script, "nonexistent")

    def test_movablefile(self):
        with tempfile.TemporaryDirectory() as d:
            filename = os.path.join(d, "write")
            with open(filename, "w") as f:
                f.write("beep beep")
            movable = MovableFileReference(filename)
            assert os.path.exists(movable.target)
            with tempfile.TemporaryDirectory() as d2:
                movable2 = movable.copy_to_dir(d2)
                self.assertEqual(movable.target, movable2.target)
                self.assertTrue(os.path.exists(movable2.target))

    def test_generate_commandline(self):
        with tempfile.TemporaryDirectory() as d:
            filename = os.path.join(d, "input.tar.gz")
            with open(filename, "w") as f:
                f.write("beep beep")

            run_desc = GatewayRunDescription("", filename, "", {}, {}, self.tracking_uri, "", "")
            srv = GatewayServer(tracking_server=self.tracking_uri)
            ret = srv.get_execution_snippet(run_desc)
            curr = ret["files"]["outside.sh"]
            assert os.path.exists(curr.target)
            curr = curr.copy_to_dir(d)
            assert os.path.exists(curr.target)

    def test_generate_slurm_template(self):
        with tempfile.TemporaryDirectory() as d:
            filename = os.path.join(d, "input.tar.gz")
            with open(filename, "w") as f:
                f.write("beep beep")

            run_desc = GatewayRunDescription("", filename, "", {}, {}, self.tracking_uri, "", "")
            srv = GatewayServer(tracking_server=self.tracking_uri)
            ctx = srv.get_execution_snippet(run_desc)

            executor = SLURMExecutor()
            print(executor.generate_slurm_template(ctx, run_desc))

    def test_execute_hello(self):
        srv = GatewayServer(inside_script="test/inside-noop.sh",tracking_server=self.tracking_uri)
        tarball = get_script("mltf-hello-world.tar.gz")
        ret = srv.enqueue_run("", tarball, "", {}, {}, self.tracking_uri, "", "", "FAKE-TOKEN")
        self.assertIsInstance(ret, ServerSideSubmittedRunDescription)
        ret.submitted_run.wait()
        if not ret.submitted_run.get_status() == RunStatus.to_string(RunStatus.FINISHED):
            mylog, _ = ret.submitted_run.command_proc.communicate()
            mylog = mylog.decode("utf-8")
            self.fail("bad return")

    def test_client_hello(self):
        srv = GatewayServer(inside_script="test/inside-noop.sh",tracking_server=self.tracking_uri)
        tarball = get_script("mltf-hello-world.tar.gz")
        client_id = srv.enqueue_run_client(
            "", tarball, "", {}, {}, self.tracking_uri, "", "", "FAKE-TOKEN"
        )
        server_id = srv.reference_to_run(client_id)
        self.assertIsInstance(server_id, ServerSideSubmittedRunDescription)
        server_id.submitted_run.wait()
        self.assertEqual(
            server_id.submitted_run.get_status(),
            RunStatus.to_string(RunStatus.FINISHED),
        )

    @unittest.skipUnless(shutil.which("sbatch"), "Requires SLURM")
    def test_slurm_template(self):
        srv = GatewayServer(
            executor=SLURMExecutor(), inside_script="test/inside-noop.sh",tracking_server=self.tracking_uri
        )
        tarball = get_script("mltf-hello-world.tar.gz")
        ret = srv.enqueue_run("", tarball, "", {}, {}, self.tracking_uri, "", "", "FAKE-TOKEN")
        # self.assertIsInstance(ret, SubmittedRun)
        ret.wait()
        self.assertEqual(ret.get_status(), RunStatus.to_string(RunStatus.FINISHED))


if __name__ == "__main__":
    unittest.main()
