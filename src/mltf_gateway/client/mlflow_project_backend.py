import json
import logging
import os
import sys
from functools import wraps

import jwt
import mlflow
import requests
from dotenv import load_dotenv
from mlflow import tracking
from mlflow.projects.backend.abstract_backend import AbstractBackend
from mlflow.projects.utils import (
    fetch_and_validate_project,
    get_or_create_run,
)
from mlflow.utils.mlflow_tags import MLFLOW_RUN_NAME, MLFLOW_USER

from mltf_gateway.client.backend_adapter import RESTAdapter
from mltf_gateway.client.project_packer import prepare_tarball, produce_tarball
from mltf_gateway.submitted_runs.client_run import ClientSideSubmittedRun
from mltf_gateway.utils import get_tracking_uri
from .oauth import get_access_token

logger = logging.getLogger(__name__)


def gateway_uri():
    return os.environ.get("MLTF_GATEWAY_URI", "https://gw.mltf.vu")


def adapter_factory() -> RESTAdapter:
    """
    Different "adapters" let the client connect to either a local or remote gateway.
    Abstract it out so there's one place for the configuration stuff to hook
    :return: Instance of AbstractBackend the client should use
    """
    load_dotenv()
    return RESTAdapter(gateway_uri=gateway_uri())


def trap_common_api_errors(f):
    """
    Make it so raw urllib/requests/etc errors don't throw stacktrace
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            print("Cannot connect to gateway. Please verify URL is correct")
            sys.exit(1)
        except Exception as e:
            print("Unknown error was received. Please report this")
            print(f"  error: {e}")

    return wrapper


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

    @trap_common_api_errors
    def run(
        self,
        project_uri,
        entry_point,
        params,
        version,
        backend_config,
        tracking_uri,
        experiment_id,
        name=None,
    ):
        if tracking_uri.startswith("file://"):
            logger.warning("""Tracking URI was not set""")
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

        if experiment_id in (None, 0, "0"):
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
        if name:
            tracking.MlflowClient().set_tag(
                mlflow_run_obj.info.run_id, MLFLOW_RUN_NAME, name
            )
        mlflow_run = mlflow_run_obj.info.run_id

        logger.info(f"Bundling user environment at {work_dir}")
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
            logger.info(f"Tarball produced at {project_tarball}")
            ret = impl.enqueue_run(
                mlflow_run,
                project_tarball,
                entry_point,
                params,
                backend_config,
                tracking_uri,
                experiment_id,
                name or "",
            )
            logger.info(f"Execution enqueued: {ret}")
            print(
                f"Find your MLFlow run at:\n\n  {tracking_uri}/#/experiments/{experiment_id}/runs/{mlflow_run}\n\n"
            )
            return ret
        finally:
            if project_tarball and os.path.exists(project_tarball):
                os.remove(project_tarball)
