import json
import logging
import os
import time
from urllib.parse import urljoin

import requests as requests_base
from requests import HTTPError

from mltf_gateway.flaskapp.app import create_app

INPROCESS_GATEWAY_APP = None


class Response:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.status_code = self.wrapped.status_code

    def raise_for_status(self):
        status = self.wrapped.status_code
        if 200 <= status < 300:
            return
        else:
            raise HTTPError(f"Received status {status}")

    def json(self):
        return self.wrapped.json


class RequestAdaptor:
    def __init__(self, gateway_uri):
        self.gateway_uri = gateway_uri
        self.app = None
        self.app_client = None
        if self.is_local():
            self.make_inprocess_gateway()

    def is_local(self):
        return self.gateway_uri == "LOCAL"

    def make_inprocess_gateway(self):
        global INPROCESS_GATEWAY_APP
        if not INPROCESS_GATEWAY_APP:
            INPROCESS_GATEWAY_APP = create_app()
        self.app = INPROCESS_GATEWAY_APP
        self.app_client = self.app.test_client()

    def make_request(self, verb, path, *args, **kwargs):
        if self.is_local():
            try:
                return Response(getattr(self.app_client, verb)(path, *args, **kwargs))
            except Exception as e:
                return Response({})
        else:
            return getattr(requests_base, verb)(
                urljoin(self.gateway_uri, path), *args, **kwargs
            )

    def get(self, path, *args, **kwargs):
        return self.make_request("get", path, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self.make_request("post", path, *args, **kwargs)

    def delete(self, path, *args, **kwargs):
        return self.make_request("delete", path, *args, **kwargs)


_logger = logging.getLogger(__name__)

import mltf_gateway.submitted_runs.client_run

ClientSideSubmittedRun = (
    mltf_gateway.submitted_runs.client_run.ClientSideSubmittedRun
)

# Import OAuth2 client for authentication
from mltf_gateway.oauth_client import (
    add_auth_header_to_request,
    get_access_token,
)


class RESTAdapter:
    """
    Enables a client process to call backend functions via REST
    """

    def __init__(self, *, gateway_uri=None):
        super().__init__()
        self.gateway_uri = gateway_uri
        self.token = os.environ.get("MLTF_GATEWAY_TOKEN")
        if not self.token:
            self.token = get_access_token()["access_token"]
        self.client = RequestAdaptor(self.gateway_uri)

    def get_api_config(self):
        response = self.client.get("api/config")
        response.raise_for_status()
        api_config = response.json()
        return api_config

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
        job_url = "api/job"
        files = {"tarball": open(project_tarball, "rb")}

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

        response = self.client.post(
            job_url, files=files, data=data, headers=headers, timeout=30
        )
        response.raise_for_status()
        run_reference = response.json()
        import pprint

        pprint.pprint(run_reference)
        ret = ClientSideSubmittedRun(
            self, run_id, run_reference["gateway_id"], time.time()
        )
        return ret

    def list(self, list_all=False):
        # Prepare the request URL
        url = f"api/jobs"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = self.client.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def wait(self, run_id) -> dict:
        # Prepare the request URL
        url = f"wait/{run_id}"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to wait for completion
        response = self.client.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to wait for run: {response.text}")

        return response.json()

    def get_status(self, run_id):
        # Prepare the request URL
        url = f"status/{run_id}"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = self.client.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def show_details(self, run_id, show_logs):
        # Prepare the request URL
        url = f"api/jobs/{run_id}"
        params = {"show_logs": show_logs}

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = self.client.get(url, headers=headers, params=params)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def delete(self, run_id):
        url = f"api/jobs/{run_id}"

        headers = {}
        headers = add_auth_header_to_request(headers)
        response = self.client.delete(url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to delete run: {response.text}")

        return response.json()

    def get_config(self, run_id):
        # Prepare the request URL
        url = "api/config"

        # Prepare headers with authentication
        headers = {}
        headers = add_auth_header_to_request(headers)

        # Make the GET request to check status
        response = self.clients.get(url, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get run status: {response.text}")

        return response.json()

    def get_tracking_server(self):
        return self.gateway_uri
