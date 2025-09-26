import os
import os.path
import shutil
from dataclasses import dataclass

from mlflow.projects.submitted_run import SubmittedRun

@dataclass
class MovableFileReference:
    """
        Wrap around a path so that we can store this in a command line then concrete 
        executors can move files to somewhere appropriate (e.g. slurm w/o a shared filesystem).
        If the path is just a string then this becomes difficult
    """

    target: str

    def copy_to_dir(self, target_dir: str):
        """
            Copy the file to a directory, updating our target to point to the new location
            :param target_dir: Directory to copy to
            :return: self
        """
        target = os.path.join(target_dir, os.path.basename(self.target))
        assert os.path.isdir(target_dir)
        assert not os.path.exists(target)
        shutil.copy(self.target, target)
        self.target = target
        return self

    def __str__(self):
        return self.target


@dataclass
class RunReference:
    """
        The primary use-case of the Gateway server is to be called via REST,
        which means we don't want to exchange SubmittedRun references with clients
        (since they contain things that either don't serialize or are sensitive).
        Instead, we exchange RunReferences with the client, which points to a
        SubmittedRun reference the GatewayServer object owns
    """

    # For now, this is just the index into GatewayServer's runs list where the "real" object lives
    index: int


@dataclass
class GatewayRunDescription:
    """
    Wraps values passed in from mlflwo directly, except user_subject which we add from the HTTP layer to identify users
    """

    run_id: str
    tarball_path: str
    entry_point: str
    params: dict
    backend_config: dict
    tracking_uri: str
    experiment_id: str
    user_subject: str


@dataclass
class GatewaySubmittedRunDescription:
    """
    Stores information about a Run submitted to an executor.

    run_desc: the user-provided definition of the run
    submitted_run: handle pointing to the actual execution (e.g. SLURM job)
    """

    run_desc: GatewayRunDescription
    submitted_run: SubmittedRun
