"""
SSAMSubmittedRun class to manage a Slurm job launched through SSAM to run an MLflow project.
"""

import logging
import time
from threading import RLock
from typing import List

import requests
from mlflow.entities import RunStatus
from mlflow.tracking import MlflowClient
from mlflow.utils.logging_utils import _configure_mlflow_loggers

_configure_mlflow_loggers(root_module_name=__name__)
_logger = logging.getLogger(__name__)


class SSAMSubmittedRun:
    """
    Instance of SubmittedRun
    corresponding to a Slum Job launched through SSAM to run an MLflow
    project.
    :param ssam_job_id: ID of the submitted SSAM Job.
    :param mlflow_run_id: ID of the MLflow project run.
    """

    def __init__(
        self,
        mlflow_run_id: str,
        ssam_job_ids: List[str],
        ssam_url: str,
        auth_token: str,
        user_subject: str,
    ) -> None:
        super().__init__()
        self._mlflow_run_id = mlflow_run_id
        self.ssam_job_ids = ssam_job_ids
        self._ssam_url = ssam_url
        self._auth_token = auth_token
        self.user_subject = user_subject
        self._status = RunStatus.SCHEDULED
        self._failure_reason = None
        self._status_lock = RLock()

    # How often to poll run status when waiting on a run
    POLL_STATUS_INTERVAL = 5

    @property
    def run_id(self) -> str:
        return self._mlflow_run_id

    @property
    def job_id(self) -> str:
        """
        :return: The final SSAM Job ID of the submitted job list.
        """
        return self.ssam_job_ids[-1]

    def is_terminated_or_gone(self):
        """
        :return: True if the SSAM job is terminated or gone, False otherwise.
        """
        self._update_status()
        return not self._status or RunStatus.is_terminated(self._status)

    def wait(self):
        """
        Implements the wait functionality for a ssam job. When we notice that the job
        is complete, attempt to grab the job logs and attach them to the run as an
        artifact
        :return: Boolean success
        """
        while not self.is_terminated_or_gone():
            time.sleep(self.POLL_STATUS_INTERVAL)

        try:
            headers = {
                "Authorization": f"Bearer {self._auth_token}",
            }
            response = requests.get(
                f"{self._ssam_url}/api/slurm/{self.job_id}/output",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            response_json = response.json()
            if response_json.get("success"):
                log_data = response_json.get("data", {})
                # The log is the value of the first key in the data dictionary
                if log_data:
                    log_lines = next(iter(log_data.values()))
                    MlflowClient().log_text(
                        self.run_id, log_lines, f"ssam-{self.job_id}.txt"
                    )
        except requests.exceptions.RequestException as e:
            message = f"Error fetching logs for job {self.job_id}: {e}"
            _logger.error(message)

        return self._status == RunStatus.FINISHED

    def cancel(self) -> None:
        """Cancels the submitted job."""
        try:
            headers = {
                "Authorization": f"Bearer {self._auth_token}",
            }
            response = requests.post(
                f"{self._ssam_url}/api/slurm/{self.job_id}/cancel",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            _logger.info(f"Successfully sent cancel request for job {self.job_id}")
        except requests.exceptions.RequestException as e:
            _logger.warning(
                f"Could not cancel job {self.job_id} via API (it may be already completed): {e}"
            )

        self._update_status()

    def get_status(self) -> RunStatus:
        self._update_status()
        return self._status

    def get_run_details(self, show_logs=False):
        status = self.get_status()

        if status is None:
            return {
                "status": "UNKNOWN",
                "failure_reason": "Could not retrieve status from SSAM.",
            }

        details = {"status": RunStatus.to_string(status)}
        if status == RunStatus.FAILED and self._failure_reason:
            details["failure_reason"] = self._failure_reason

        if show_logs:
            details["logs"] = self.get_logs()

        return details

    def get_logs(self):
        try:
            headers = {
                "Authorization": f"Bearer {self._auth_token}",
            }
            response = requests.get(
                f"{self._ssam_url}/api/slurm/{self.job_id}/output",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            response_json = response.json()
            if response_json.get("success"):
                log_data = response_json.get("data", {})
                if log_data:
                    return next(iter(log_data.values()))
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching logs for job {self.job_id}: {e}")
        return None

    def _update_status(self) -> RunStatus:
        try:
            headers = {
                "Authorization": f"Bearer {self._auth_token}",
            }
            response = requests.get(
                f"{self._ssam_url}/api/slurm/{self.job_id}", headers=headers, timeout=30
            )
            response.raise_for_status()
            response_json = response.json()
            if response_json.get("success"):
                job_state = response_json.get("data", {}).get("job_state")

                with self._status_lock:
                    # Mapping SSAM status to MLflow RunStatus
                    if job_state == "PENDING":
                        self._status = RunStatus.SCHEDULED
                    elif job_state == "COMPLETED":
                        self._status = RunStatus.FINISHED
                    elif job_state == "FAILED":
                        self._status = RunStatus.FAILED
                        self._failure_reason = response_json.get("data", {}).get(
                            "failure_reason"
                        )
                    elif job_state == "RUNNING":
                        self._status = RunStatus.RUNNING
                    else:
                        _logger.warning(
                            "Job ID %s, has an unmapped status of: %s",
                            self.job_id,
                            job_state,
                        )
                        self._status = None  # Or some other default
            else:
                message = f"Failed to get status for job {self.job_id}: {response_json.get('message')}"
                _logger.error(message)
                with self._status_lock:
                    self._status = None

        except requests.exceptions.RequestException as e:
            message = f"Error fetching status for job {self.job_id}: {e}"
            _logger.error(message)
            with self._status_lock:
                self._status = None
        except Exception as e:
            message = f"An unexpected error occurred during status update for job {self.job_id}: {e}"
            _logger.error(message)
            with self._status_lock:
                self._status = None

        return self._status

    # Locks cannot be pickled, add these dunder methods to delete/restore lock
    def __getstate__(self):
        """Return state values to be pickled."""
        state = self.__dict__.copy()
        del state["_status_lock"]
        return state

    def __setstate__(self, state):
        """Restore state from the unpickled state values."""
        self.__dict__.update(state)
        self._status_lock = RLock()
