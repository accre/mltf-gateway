"""
Client-side code for MLFlow, used for MLFlow API
Heavily inspired by mlflow-slurm: https://github.com/ncsa/mlflow-slurm
"""

from mlflow.projects.backend.abstract_backend import AbstractBackend
from dotenv import load_dotenv

from .backends.GatewayBackend import GatewayProjectBackend, adapter_factory


# Debug flag
load_dotenv()
IS_DEBUG = True


def gateway_backend_builder() -> AbstractBackend:
    """
    Entrypoint for MLflow to create an instance of the custom backend.
    See https://mlflow.org/docs/3.3.2/ml/projects/#custom-backend-development for details.

    Returns:
        AbstractBackend: The custom backend instance.
    """
    return GatewayProjectBackend()


def get_config():
    impl = adapter_factory()
