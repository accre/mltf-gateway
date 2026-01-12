import json
import logging
import os

import jwt
import mlflow
from dotenv import load_dotenv
from mlflow import tracking
from mlflow.projects.backend.abstract_backend import AbstractBackend
from mlflow.projects.utils import (
    fetch_and_validate_project,
    get_or_create_run,
)
from mlflow.utils.mlflow_tags import MLFLOW_USER
from mlflow_mltf_gateway.oauth_client import get_access_token
from mlflow_mltf_gateway.adapters.LocalAdapter import LocalAdapter
from mlflow_mltf_gateway.adapters.RESTAdapter import RESTAdapter
from mlflow_mltf_gateway.adapters.base import BackendAdapter
from mlflow_mltf_gateway.project_packer import prepare_tarball, produce_tarball
from mlflow_mltf_gateway.submitted_runs.client_run import ClientSideSubmittedRun
from mlflow_mltf_gateway.utils import get_tracking_uri

_logger = logging.getLogger(__name__)


def adapter_factory() -> BackendAdapter:
    """
    Different "adapters" let the client connect to either a local or remote gateway.
    Abstract it out so there's one place for the configuration stuff to hook
    :return: Instance of AbstractBackend the client should use
    """
    load_dotenv()
    gateway_uri = os.environ.get("MLTF_GATEWAY_URI", "http://localhost:5001")
    if gateway_uri and gateway_uri != "LOCAL":
        return RESTAdapter(gateway_uri=gateway_uri)
    else:
        # FIXME:
        # Make an error message if someone doesn't choose a gateway URI
        # Otherwise, they will have a bad experience running a LocalAdapter
        return LocalAdapter()


class GatewayProjectBackend(AbstractBackend):
    """
    API Enforced from MLFlow - see
    https://mlflow.org/docs/3.3.2/ml/projects/#custom-backend-development

    Annoyingly, only the "run" API is exposed to the mlflow CLI, so all other methods are MLTF-specific
    """

    def list(self, list_all=True, detailed=False) -> list[ClientSideSubmittedRun]:
        impl = adapter_factory()
        return impl.list(list_all)

    def show_details(self, run_id: str, show_logs: bool):
        """Get the details of a run."""
        impl = adapter_factory()
        return impl.show_details(run_id, show_logs)

    def delete(self, run_id: str):
        """Delete a run."""
        impl = adapter_factory()
        return impl.delete(run_id)

    def run(
        self,
        project_uri,
        entry_point,
        params,
        version,
        backend_config,
        tracking_uri,
        experiment_id,
    ):
        if tracking_uri.startswith("file://"):
            _logger.warning("""Tracking URI was not set""")
            # FIXME We should eb able to get this from the server
            tracking_uri = get_tracking_uri()

        mlflow.set_tracking_uri(tracking_uri)
        creds = get_access_token()
        os.environ["MLFLOW_TRACKING_TOKEN"] = creds["access_token"]
        decoded = jwt.decode(creds["access_token"], options={"verify_signature": False})

        # Determine experiment based on username
        try:
            suffix = decoded["preferred_username"].split("@")[0]
        except (KeyError, SyntaxError, IndexError):
            suffix = "unknown_user"

        experiment_name = f"default_{suffix}"
        experiment = mlflow.set_experiment(experiment_name)
        experiment_id = experiment.experiment_id

        impl = adapter_factory()

        work_dir = fetch_and_validate_project(project_uri, version, entry_point, params)

        config_path = os.path.join(work_dir, "gateway_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                gateway_config = json.load(f)
            backend_config.update(gateway_config)

        mlflow_run_obj = get_or_create_run(
            None, project_uri, experiment_id, work_dir, version, entry_point, params
        )

        tracking.MlflowClient().set_tag(
            mlflow_run_obj.info.run_id, MLFLOW_USER, decoded["preferred_username"]
        )
        mlflow_run = mlflow_run_obj.info.run_id

        _logger.info("Bundling user environment")
        file_catalog = prepare_tarball(work_dir)
        tarball_limit = 1024 * 1024 * 1024  # 1Gigabyte
        tarball_size = 0
        for _, value in file_catalog.items():
            tarball_size += value[0]
        if tarball_size > tarball_limit:
            raise RuntimeError(
                f"Tarball size ({tarball_size}) exceeds limit of 1GB. Please shrink the size of your project"
            )
        project_tarball = None
        try:
            project_tarball = produce_tarball(file_catalog)
            _logger.info(f"Tarball produced at {project_tarball}")
            ret = impl.enqueue_run(
                mlflow_run,
                project_tarball,
                entry_point,
                params,
                backend_config,
                tracking_uri,
                experiment_id,
            )
            _logger.info(f"Execution enqueued: {ret}")
            print(
                f"Find your MLFlow run at:\n\n  {tracking_uri}/#/experiments/{experiment_id}/runs/{mlflow_run}\n\n"
            )
            return ret
        finally:
            if project_tarball and os.path.exists(project_tarball):
                os.remove(project_tarball)
