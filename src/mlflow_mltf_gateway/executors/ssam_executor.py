import os
import tempfile
import json
import shlex
import requests

from .base import ExecutorBase, jinja_env
from ..submitted_runs.ssam_run import SSAMSubmittedRun
from ..utils import get_ssam_job_description


class SSAMExecutor(ExecutorBase):
    """
    Executor that submits jobs to a Slurm cluster via SSAM server
    """

    def __init__(
        self, ssam_url=None, auth_token=None, project_root=None, slurm_token=None
    ):
        self.ssam_url = ssam_url or os.environ.get("SSAM_URL")
        self.auth_token = auth_token or os.environ.get("AUTH_TOKEN")

        self.project_root = project_root or os.environ.get(
            "PROJECT_ROOT_DIR", "/tmp/mltf-experiments"
        )
        self.slurm_token = slurm_token or os.environ.get("SLURM_TOKEN")

        if not self.ssam_url:
            raise ValueError(
                "SSAM_URL is not provided or set as an environment variable."
            )
        if not self.auth_token:
            raise ValueError(
                "AUTH_TOKEN is not provided or set as an environment variable."
            )

    @staticmethod
    def _setup_slurm_token(ssam_url: str, auth_token: str, slurm_token: str):
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
            timeout=30,
        )
        response.raise_for_status()

    @staticmethod
    def _setup_project_root(ssam_url: str, auth_token: str, project_root_dir: str):
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
            timeout=30,
        )
        response.raise_for_status()

    def _ssam_request(self, slurm_request, entrypoint_script_path, files):
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
        }

        multipart_form_data = []
        file_handles = []
        try:
            for name, path in files.items():
                handle = open(path, "rb")
                file_handles.append(handle)
                multipart_form_data.append(
                    ("files", (name, handle, "application/octet-stream"))
                )

            with open(entrypoint_script_path, "r", encoding="utf-8") as entrypoint_file:
                multipart_form_data.append(
                    ("entry_script", (None, entrypoint_file.read()))
                )

            multipart_form_data.append(
                ("slurm_request", (None, json.dumps(slurm_request)))
            )

            response = requests.post(
                f"{self.ssam_url}/api/slurm",
                files=multipart_form_data,
                headers=headers,
                timeout=30,
            )
        finally:
            for handle in file_handles:
                handle.close()

        response.raise_for_status()
        response_json = response.json()
        if response_json.get("success"):
            return response_json.get("data", {}).get("job_uuid")

        message = f"SSAM request failed: {response_json.get('message')}"
        raise RuntimeError(message)

    def generate_ssam_template(self, ctx, run_desc):
        cmdline_resolved = shlex.join([str(x) for x in ctx["commands"]])
        slurm_template = jinja_env.get_template("slurm-wrapper.sh")
        return slurm_template.render({"command": cmdline_resolved})

    def run_context_async(self, ctx, run_desc):
        backend_config = run_desc.backend_config
        slurm_request = get_ssam_job_description(backend_config)
        generated_wrapper = self.generate_ssam_template(ctx, run_desc)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".sh") as tmp_script:
            tmp_script.write(generated_wrapper.encode("utf-8"))
            tmp_script.flush()
            entrypoint_script_path = tmp_script.name

        files_to_upload = {
            "project.tar.gz": run_desc.tarball_path,
            "outside.sh": ctx["files"]["outside.sh"].target,
            "inside.sh": ctx["files"]["inside.sh"].target,
        }

        if self.slurm_token:
            self._setup_slurm_token(self.ssam_url, self.auth_token, self.slurm_token)

        if self.project_root:
            self._setup_project_root(self.ssam_url, self.auth_token, self.project_root)

        job_id = self._ssam_request(
            slurm_request,
            entrypoint_script_path,
            files_to_upload,
        )

        os.remove(entrypoint_script_path)

        return SSAMSubmittedRun(
            run_desc.run_id, [job_id], self.ssam_url, self.auth_token
        )
