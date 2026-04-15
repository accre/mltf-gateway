import unittest

import mltf_gateway.gateway_server
from mltf_gateway.executors.base import get_script
from tests.common_test_base import MockedGatewayTestBase

GatewayServer = mltf_gateway.gateway_server.GatewayServer


class IntegrationTest(MockedGatewayTestBase):

    def test_submit_and_show(self):
        srv = GatewayServer(executor_name='local', inside_script="test/inside-noop.sh")
        tarball = get_script("mltf-hello-world.tar.gz")
        run = srv.enqueue_run("", tarball, "", {}, {}, self.tracking_uri, "", "FAKE-USER", "FAKE-TOKEN")
        run.wait()
        print(run)
        all_runs = srv.list(list_all=False, user_subject="FAKE-USER")
        assert (len(all_runs) > 0)
        other_user_runs = srv.list(list_all=False, user_subject="ANOTHER-FAKE-USER")
        assert (len(other_user_runs) == 0)
        run_inf = srv.show_details(run.gateway_id, show_logs=True)
        assert (run_inf)
        assert (len(run_inf['logs']) > 0)

    def test_submit_and_show_bare(self):
        self.setEnv('MLTF_DEBUG_NO_CONTAINER', 'true')
        srv = GatewayServer(executor_name='local', inside_script="test/inside-dump.py")
        tarball = get_script("mltf-hello-world.tar.gz")
        run = srv.enqueue_run("", tarball, "", {}, {}, self.tracking_uri, "", "FAKE-USER", "FAKE-TOKEN")
        run.wait()
        print(run)
        all_runs = srv.list(list_all=False, user_subject="FAKE-USER")
        assert (len(all_runs) > 0)
        other_user_runs = srv.list(list_all=False, user_subject="ANOTHER-FAKE-USER")
        assert (len(other_user_runs) == 0)
        run_inf = srv.show_details(run.gateway_id, show_logs=True)
        assert (run_inf)
        assert (run_inf['status'] == "FINISHED")
        assert (len(run_inf['logs']) > 0)
        print(run_inf['logs'])

    def test_submit_and_fail(self):
        self.setEnv('MLTF_DEBUG_NO_CONTAINER', 'true')
        srv = GatewayServer(executor_name='local', inside_script="test/inside-fail.py")
        tarball = get_script("mltf-hello-world.tar.gz")
        run = srv.enqueue_run("", tarball, "", {}, {}, self.tracking_uri, "", "FAKE-USER", "FAKE-TOKEN")
        run.wait()
        print(run)
        all_runs = srv.list(list_all=False, user_subject="FAKE-USER")
        assert (len(all_runs) > 0)
        other_user_runs = srv.list(list_all=False, user_subject="ANOTHER-FAKE-USER")
        assert (len(other_user_runs) == 0)
        run_inf = srv.show_details(run.gateway_id, show_logs=True)
        assert (run_inf)
        assert (run_inf['status'] == "FAILED")
        assert (len(run_inf['logs']) > 0)
        print(run_inf['logs'])


if __name__ == '__main__':
    unittest.main()
