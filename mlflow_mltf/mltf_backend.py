
import logging
import os
import tempfile
import json
from pathlib import Path

import requests
from mlflow import tracking
from mlflow.projects import load_project
from mlflow.projects.backend.abstract_backend import AbstractBackend
from mlflow.projects.utils import (
    fetch_and_validate_project,
    get_or_create_run,
    PROJECT_STORAGE_DIR,
    get_entry_point_command,
)
from mlflow.tracking import MlflowClient
from mlflow.utils.conda import (
    get_or_create_conda_env,
)
from mlflow.utils.environment import _PythonEnv
from mlflow.utils.logging_utils import _configure_mlflow_loggers
from mlflow.utils.mlflow_tags import MLFLOW_PROJECT_ENV, MLFLOW_SOURCE_NAME

from mlflow_mltf.submitted_run import SSAMSubmittedRun
from mlflow_mltf.utils import get_ssam_job_description, generate_entrypoint_script
from mlflow_mltf.project_packer import package_project

_configure_mlflow_loggers(root_module_name=__name__)
_logger = logging.getLogger(__name__)


# Entrypoint for Project Backend
def mltf_backend_builder() -> AbstractBackend:
    """
    Constructs an instance of the MLTFProjectBackend, which is an implementation
    of the AbstractBackend class for running MLflow projects on Slurm.
    :return: Instance of MLTFProjectBackend.
    """
    return MLTFProjectBackend()


class MLTFProjectBackend(AbstractBackend):
    """
    Backend implementation for running MLflow projects on Slurm.

    Args:
        AbstractBackend: Inherits from the AbstractBackend class.
    """

    @staticmethod
    def setup_slurm_token(ssam_url: str, auth_token: str, slurm_token: str):
        """
            Setup SLURM_TOKEN for SSAM server.
            :param ssam_url: The base URL of the SSAM server API.
            :param auth_token: The bearer token for authenticating with the SSAM server.
            :param slurm_token: The slurm token for authenticating with the SSAM server
        """
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"slurm_token": slurm_token}
        response = requests.post(
            f"{ssam_url}/api/cluster_slurm_token",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

    @staticmethod
    def setup_project_root(ssam_url: str, auth_token: str, project_root_dir: str):
        """
            Setup PROJECT_ROOT_DIR for SSAM server.
            :param ssam_url: The base URL of the SSAM server API.
            :param auth_token: The bearer token for authenticating with the SSAM server.
            :param project_root_dir: The project root dir where these experiments will be kept.
        """
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"base_experiment_path": project_root_dir}
        response = requests.post(
            f"{ssam_url}/api/experiment_folder",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

    @staticmethod
    def ssam_request(
        ssam_url: str,
        auth_token: str,
        slurm_request: dict,
        entrypoint_script_path: str,
        project_tarball_path: str,
    ) -> str:
        """
            Submit a job to slurm using the ssam command.
        """
        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        with open(entrypoint_script_path, 'r', encoding="utf-8") as entrypoint_file,\
            open(project_tarball_path, 'rb') as project_tarball:
            multipart_form_data = [
                ('files', ('project.tar.gz', project_tarball, 'application/gzip')),
                ('entry_script', (None, entrypoint_file.read())),
                ('slurm_request', (None, json.dumps(slurm_request))),
            ]
            response = requests.post(
                f"{ssam_url}/api/slurm",
                files=multipart_form_data,
                headers=headers,
                timeout=30
            )

        response.raise_for_status()
        response_json = response.json()
        if response_json.get("success"):
            return response_json.get("data", {}).get("job_uuid")

        message = f"SSAM request failed: {response_json.get('message')}"
        raise RuntimeError(message)

    def run(
        self,
        project_uri: str,
        entry_point: str,
        params: dict,
        version: str,
        backend_config: dict,
        tracking_uri: str,
        experiment_id: str
    ) -> SSAMSubmittedRun:
        """
            Run an MLflow project on Slurm.
            :param project_uri: URI of the project.
            :param entry_point: Entry point to run.
            :param params: Parameters for the entry point.
            :param version: Version of the project.
            :param backend_config: Backend configuration dictionary from mltf_config.json.
            :param tracking_uri: Tracking URI for MLflow.
            :param experiment_id: Experiment ID for MLflow.
            :return: An instance of SSAMSubmittedRun representing the submitted job.
        """
        print(f"Ready to submit with params: {params}")
        work_dir = fetch_and_validate_project(project_uri, version, entry_point, params)
        active_run = get_or_create_run(
            None,
            project_uri,
            experiment_id,
            work_dir,
            version,
            entry_point,
            params
        )

        source_name = active_run.data.tags.get(MLFLOW_SOURCE_NAME)
        if source_name and source_name.startswith("file://"):
            source_name = source_name[7:]
            source_parts = source_name.split("#", 1)
            source_path = source_parts[0]
            relative_path = os.path.relpath(source_path)

            if len(source_parts) > 1:
                entry_point_path = source_parts[1]
                new_source_name = f"{relative_path}#{entry_point_path}"
            else:
                new_source_name = relative_path

            MlflowClient().set_tag(active_run.info.run_id, MLFLOW_SOURCE_NAME, new_source_name)

        _logger.info("run_id=%s", active_run.info.run_id)
        _logger.info("work_dir=%s", work_dir)

        project = load_project(work_dir)

        storage_dir = backend_config.get(PROJECT_STORAGE_DIR)

        ssam_url = os.environ.get("SSAM_URL")
        auth_token = os.environ.get("AUTH_TOKEN")
        slurm_token = os.environ.get("SLURM_TOKEN")
        project_root_dir = os.environ.get("PROJECT_ROOT_DIR")

        if not ssam_url:
            _logger.fatal("SSAM_URL environment variable not set")
            return None
        if not auth_token:
            _logger.fatal("AUTH_TOKEN environment variable not set")
            return None
        if slurm_token:
            # Setup SLURM_TOKEN and PROJECT_ROOT_DIR
            self.setup_slurm_token(ssam_url, auth_token, slurm_token)
        if project_root_dir:
            self.setup_project_root(ssam_url, auth_token, project_root_dir)

        command_args = []
        command_separator = " && "

        if project.env_type == "python_env":
            tracking.MlflowClient().set_tag(
                active_run.info.run_id,
                MLFLOW_PROJECT_ENV,
                "virtualenv"
            )
            python_env = _PythonEnv.from_yaml(project.env_config_path)

            # Write dependencies to a requirements.txt file
            # that will be bundled in the project tarball
            requirements_path = Path(work_dir) / "mltf_requirements.txt"
            with open(requirements_path, "w", encoding="utf-8") as f:
                f.write("\n".join(python_env.dependencies))

            # Generate commands to create and activate a virtualenv,
            # and install dependencies on the remote node
            venv_dir = "venv"
            create_venv_cmd = f"python3 -m venv {venv_dir}"
            activate_cmd = f". {venv_dir}/bin/activate"
            pip_install_upgrade_cmd = "pip install --upgrade pip"
            install_deps_cmd = f"pip install -r {requirements_path.name}"

            command_args.extend([
                create_venv_cmd,
                activate_cmd,
                pip_install_upgrade_cmd,
                install_deps_cmd
            ])
        elif project.env_type == "conda_env":
            tracking.MlflowClient().set_tag(
                active_run.info.run_id,
                MLFLOW_PROJECT_ENV,
                "conda"
            )
            conda_env = get_or_create_conda_env(project.env_config_path)
            command_args += conda_env.get_activate_command()
        else:
            _logger.fatal("Unknown project environment type provided: %s", project.env_type)
            return None

        entry_point_command = get_entry_point_command(project, entry_point, params, storage_dir)
        entry_point_command = [c.replace(work_dir, ".") for c in entry_point_command]
        command_args += entry_point_command
        command_str = command_separator.join(command_args)

        project_tarball_path = package_project(work_dir)
        slurm_request = get_ssam_job_description(backend_config)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".sh") as tmp_script:
            generate_entrypoint_script(
                command_str,
                backend_config,
                active_run.info.run_id,
                tmp_script.name
            )
            entrypoint_script_path = tmp_script.name

        job_id = MLTFProjectBackend.ssam_request(
            ssam_url,
            auth_token,
            slurm_request,
            entrypoint_script_path,
            project_tarball_path,
        )

        # TODO: make it such that data is sent streaming without having to delete anything
        os.remove(project_tarball_path)
        os.remove(entrypoint_script_path)

        MlflowClient().set_tag(active_run.info.run_id, "ssam_job_id", job_id)
        _logger.info("ssam job id=%s", job_id)

        return SSAMSubmittedRun(active_run.info.run_id, [job_id], ssam_url, auth_token)
