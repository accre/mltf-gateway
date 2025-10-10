import json
import logging
import os
from urllib.parse import urljoin

import requests

from mlflow_mltf_gateway.adapters.base import BackendAdapter

_logger = logging.getLogger(__name__)

import mlflow_mltf_gateway.submitted_runs.client_run

ClientSideSubmittedRun = (
    mlflow_mltf_gateway.submitted_runs.client_run.ClientSideSubmittedRun
)

# Import OAuth2 client for authentication
from mlflow_mltf_gateway.oauth_client import (
    add_auth_header_to_request,
    get_access_token,
)


class RESTAdapter(BackendAdapter):
    """
    Enables a client process to call backend functions via REST
    """

    def __init__(self, *, gateway_uri=None):
        super().__init__()
        self.gateway_uri = gateway_uri
        self.token = os.environ.get("MLTF_GATEWAY_TOKEN")
        if not self.token:
            self.token = get_access_token()["access_token"]

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
        job_url = urljoin(self.gateway_uri, "api/job")
        files = {"tarball": open(project_tarball, "rb")}
        print("backend_config:", backend_config)
        data = {
            "run_id": run_id,
            "entry_point": entry_point,
            "params": json.dumps(params),
            "backend_config": json.dumps(backend_config),
            "tracking_uri": tracking_uri,
            "experiment_id": experiment_id,
        }
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.post(
            job_url, files=files, data=data, headers=headers, timeout=30
        )
        response.raise_for_status()
        run_reference = response.json()

        return run_reference

    def list(self, list_all):
        # Prepare the request URL
        url = f"{self.gateway_uri}/api/jobs"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

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

    def show_details(self, run_id, show_logs):
        # Prepare the request URL
        url = f"{self.gateway_uri}/api/jobs/{run_id}"
        params = {"show_logs": show_logs}

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def delete(self, run_id):
        url = f"{self.gateway_uri}/api/jobs/{run_id}"

        headers = {}
        headers = add_auth_header_to_request(headers)
        response = requests.delete(url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to delete run: {response.text}")

        return response.json()

    def get_config(self, run_id):
        # Prepare the request URL
        url = f"{self.gateway_uri}/api/config"

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
