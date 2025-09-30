import logging
import os
import json

from mlflow.projects.backend.abstract_backend import AbstractBackend
from mlflow.projects import (
    fetch_and_validate_project,
    get_or_create_run,
)
from mlflow.utils.logging_utils import _configure_mlflow_loggers
from dotenv import load_dotenv

from ..project_packer import prepare_tarball, produce_tarball
from ..backend_adapter import LocalAdapter, RESTAdapter


_configure_mlflow_loggers(root_module_name=__name__)
_logger = logging.getLogger(__name__)


def adaptor_factory():
    """
    Different "adaptors" let the client connect to either a local or remote gateway.
    Abstract it out so there's one place for the configuration stuff to hook
    :return: Instance of AbstractBackend the client should use
    """
    load_dotenv()
    gateway_uri = os.environ.get("MLTF_GATEWAY_URI", "http://localhost:5001")
    if gateway_uri:
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
    """

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

        impl = adaptor_factory()

        work_dir = fetch_and_validate_project(project_uri, version, entry_point, params)

        config_path = os.path.join(work_dir, "gateway_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                gateway_config = json.load(f)
            backend_config.update(gateway_config)

        mlflow_run_obj = get_or_create_run(
            None, project_uri, experiment_id, work_dir, version, entry_point, params
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
            return ret
        finally:
            if project_tarball and os.path.exists(project_tarball):
                os.remove(project_tarball)
