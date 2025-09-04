from abc import ABCMeta, abstractmethod
import uuid
import shutil
import tempfile
import logging

_logger = logging.getLogger(__name__)

from mlflow_mltf_gateway.client_submitted_run import GatewaySubmittedRun


class BackendAdapter:
    """
    Base class for connections between the client and backend.
    """

    __metaclass__ = ABCMeta

    # Note that the tarball can be deleted by the caller so we need to save it somewhere before returning
    @abstractmethod
    def enqueue_run(
        self,
        project_tarball,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
    ):
        raise NotImplementedError()

    @abstractmethod
    def wait(self, run_id):
        raise NotImplementedError()

    @abstractmethod
    def get_status(self, run_id):
        raise NotImplementedError()


class RESTAdapter(BackendAdapter):
    """
    Enables a client process to call backend functions via REST
    """

    def __init__(self, *, debug_gateway_uri=None):
        super().__init__(self)

    def enqueue_run(
        self,
        project_tarball,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
    ):
        raise NotImplementedError("To fix")

    def wait(self, run_id):
        raise NotImplementedError("To fix")

    def get_status(self, run_id):
        raise NotImplementedError("To fix")


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

    def wait(self, run_id):
        return self.gw.wait(run_id)

    def get_status(self, run_id):
        return self.gw.get_status(run_id)

    def enqueue_run(
        self,
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
        print(f"Copying tarball from {project_tarball} to {tarball_copy.name}")
        # The Server side will return a run reference, which points to the object on the server side. Let's wrap that
        # in the SubmittedRun object the client expects
        run_reference = self.gw.enqueue_run_client(
            uuid.uuid4(),
            tarball_copy.name,
            entry_point,
            params,
            backend_config,
            tracking_uri,
            experiment_id,
            LOCAL_ADAPTER_USER_SUBJECT,
        )
        ret = GatewaySubmittedRun(self, run_reference.index)
        return ret
