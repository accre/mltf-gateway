from abc import ABCMeta, abstractmethod
import uuid
import shutil
import tempfile
import logging
import requests
import os
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

from mlflow_mltf_gateway.client_submitted_run import GatewaySubmittedRun
from mlflow.projects.utils import fetch_and_validate_project, get_or_create_run

# Import OAuth2 client for authentication
from mlflow_mltf_gateway.oauth_client import add_auth_header_to_request


class BackendAdapter:
    """
    Base class for connections between the client and backend.
    """

    # Note that the tarball can be deleted by the caller so we need to save it somewhere before returning
    @abstractmethod
    def enqueue_run(
        self,
        mlflow_run,
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

    @abstractmethod
    def get_tracking_server(self):
        raise NotImplementedError()


class RESTAdapter(BackendAdapter):
    """
    Enables a client process to call backend functions via REST
    """

    def __init__(self, *, debug_gateway_uri=None):
        super().__init__(self)
        # Store the gateway URI for later use in requests
        self.gateway_uri = debug_gateway_uri or (os.environ.get("MLTF_GATEWAY_URI") if os.environ.get("MLTF_GATEWAY_URI") else "http://localhost:5000")

    def enqueue_run(
        self,
        mlflow_run,
        project_tarball,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
    ):
        # Prepare the request URL
        url = f"{self.gateway_uri}/enqueue"

        # Prepare headers with authentication
        headers = {
            "Content-Type": "application/json",
        }
        headers = add_auth_header_to_request(headers)

        # Prepare data for the request
        data = {
            "mlflow_run": mlflow_run,
            "entry_point": entry_point,
            "params": params,
            "backend_config": backend_config,
            "tracking_uri": tracking_uri,
            "experiment_id": experiment_id,
        }

        # Make the POST request to enqueue the run
        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to enqueue run: {response.text}")

        return response.json()

    def wait(self, run_id):
        # Prepare the request URL
        url = f"{self.gateway_uri}/wait/{run_id}"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to wait for completion
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to wait for run: {response.text}")

        return response.json()

    def get_status(self, run_id):
        # Prepare the request URL
        url = f"{self.gateway_uri}/status/{run_id}"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def get_tracking_server(self):
        return self.gateway_uri


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

    def wait(self, run_id):
        return self.gw.wait(run_id)

    def get_status(self, run_id):
        return self.gw.get_status(run_id)

    def enqueue_run(
        self,
        mlflow_run,
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
            mlflow_run,
            tarball_copy.name,
            entry_point,
            params,
            backend_config,
            tracking_uri,
            experiment_id,
            LOCAL_ADAPTER_USER_SUBJECT,
        )
        ret = GatewaySubmittedRun(self, mlflow_run, run_reference.index)
        return ret


