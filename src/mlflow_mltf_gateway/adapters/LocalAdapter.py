import logging
import shutil
import tempfile
import time

from mlflow_mltf_gateway.adapters.base import BackendAdapter
from mlflow_mltf_gateway.oauth_client import get_access_token

_logger = logging.getLogger(__name__)

import mlflow_mltf_gateway.submitted_runs.client_run

ClientSideSubmittedRun = (
    mlflow_mltf_gateway.submitted_runs.client_run.ClientSideSubmittedRun
)


# Just a dummy user subject when running locally
LOCAL_ADAPTER_USER_SUBJECT = "LOCAL_USER"
# Process-wide gateway object, so all adapters talk to the same instance instead of making a new one each time
LOCAL_GATEWAY_OBJECT = None


class LocalAdapter(BackendAdapter):
    """
    Enables a client process to directly call backend functions, skipping REST
    """

    gw = None

    def __init__(self, *, debug_gateway=None):
        super().__init__()  # Call the parent class constructor
        self.gw = debug_gateway if debug_gateway else self.return_or_load_gateway()
        if not self.gw:
            raise RuntimeError("MLTF local gateway unavailable in this environment")

    def return_or_load_gateway(self):
        global LOCAL_GATEWAY_OBJECT
        if not LOCAL_GATEWAY_OBJECT:
            try:
                import mlflow_mltf_gateway.gateway_server

                LOCAL_GATEWAY_OBJECT = (
                    mlflow_mltf_gateway.gateway_server.GatewayServer()
                )
            except ImportError:
                LOCAL_GATEWAY_OBJECT = None
        self.gw = LOCAL_GATEWAY_OBJECT
        return self.gw

    def list(self, list_all):
        return self.gw.list(list_all, LOCAL_ADAPTER_USER_SUBJECT)

    def wait(self, run_id):
        return self.gw.wait(run_id)

    def get_status(self, run_id):
        return self.gw.get_status(run_id)

    def show_details(self, run_id, show_logs):
        return self.gw.show(run_id)

    def delete(self, run_id):
        return self.gw.delete(run_id)

    def enqueue_run(
        self,
        run_id,
        project_tarball,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
    ):

        # FIXME: need to think about when these temporary files can be deleted
        tarball_copy = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
        with open(project_tarball, "rb") as f:
            shutil.copyfileobj(f, tarball_copy)
        tarball_copy.close()
        _logger.info(f"Copying tarball from {project_tarball} to {tarball_copy.name}")
        # The Server side will return a run reference, which points to the object on the server side. Let's wrap that
        # in the SubmittedRun object the client expects

        run_reference = self.gw.enqueue_run_client(
            run_id,
            tarball_copy.name,
            entry_point,
            params,
            backend_config,
            tracking_uri,
            experiment_id,
            LOCAL_ADAPTER_USER_SUBJECT,
            get_access_token()["access_token"],
        )

        ret = ClientSideSubmittedRun(
            self, run_id, run_reference.gateway_id, time.time()
        )
        return ret

    def get_config(self):
        return {"tracking_uri": "https://mlflow-test.mltf.k8s.accre.vanderbilt.edu"}
