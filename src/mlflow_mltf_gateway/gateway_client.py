#
# Client-side code for MLFLOW
#
#
# Heavily inspired by mlflow-slurm: https://github.com/ncsa/mlflow-slurm
#

import logging
import os

from mlflow.projects import (
    fetch_and_validate_project,
    get_or_create_run,
)
from mlflow.projects.backend.abstract_backend import AbstractBackend
from mlflow.utils.logging_utils import _configure_mlflow_loggers

from mlflow_mltf_gateway.backend_adapter import LocalAdapter, RESTAdapter
from mlflow_mltf_gateway.project_packer import prepare_tarball, produce_tarball

_configure_mlflow_loggers(root_module_name=__name__)
_logger = logging.getLogger(__name__)

# Debug flag
IS_DEBUG = True


# Entrypoint for Project Backend
def gateway_backend_builder() -> AbstractBackend:
    return GatewayProjectBackend()


def adaptor_factory():
    """
    Different "adaptors" let the client connect to either a local or remote gateway.
    Abstract it out so there's one place for the configuration stuff to hook
    :return: Instance of AbstractBackend the client should use
    """
    if os.environ.get("MLTF_GATEWAY_URI"):
        return RESTAdapter(os.environ.get("MLTF_GATEWAY_URI"))
    else:
        # FIXME Make an error message if someone doesn't choose a gateway URI
        #       Otherwise, they will have a bad experience running a LocalAdapter
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
        mlflow_run_obj = get_or_create_run(
            None, project_uri, experiment_id, work_dir, version, entry_point, params
        )
        mlflow_run = mlflow_run_obj.info.run_id
        _logger.info(f"Bundling user environment")
        file_catalog = prepare_tarball(work_dir)
        tarball_limit = 1024 * 1024 * 1024  # 1Gigabyte
        tarball_size = 0
        for f in file_catalog:
            tarball_size += file_catalog[f][0]
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
