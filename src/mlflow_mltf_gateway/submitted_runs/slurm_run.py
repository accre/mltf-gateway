import logging
from mlflow.projects.submitted_run import SubmittedRun


class SLURMSubmittedRun:
    """
    Instance of SubmittedRun
    corresponding to a Slurm Job to run an MLflow
    project.
    :param run_id: ID of the MLflow project run.
    :param slurm_id: ID of the submitted Slurm Job.
    """

    def __init__(self, run_id, slurm_id):
        super().__init__()
        self.run_id = run_id
        self.slurm_id = slurm_id

    def wait(self):
        logging.info(f"Waiting on SLURMSubmittedRun({self.slurm_id})")

    def get_status(self):
        logging.info(f"Checking status of SLURMSubmittedRun({self.slurm_id})")
        return "UNKNOWN"

    def cancel(self):
        logging.info(f"Cancelling SLURMSubmittedRun({self.slurm_id})")

    @property
    def run_id(self):
        logging.info(f"Retrieving mlflow run_id for SLURMSubmittedRun({self.slurm_id})")
        return self.run_id
