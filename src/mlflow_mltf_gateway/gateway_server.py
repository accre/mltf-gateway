import functools

from .executors.local_executor import LocalExecutor
from .executors.slurm_executor import SLURMExecutor
from .executors.ssam_executor import SSAMExecutor
from .executors.base import get_script
from .data_classes import (
    MovableFileReference,
    RunReference,
    GatewayRunDescription,
    GatewaySubmittedRunDescription
)

DEBUG = False


def return_id_decorator(f):
    """
        Helper wrapper to take a function which returns a SubmittedRun
        and converts to return a RunReference
    """

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        return RunReference(self.runs.index(ret))

    return wrapper

class GatewayServer:
    """
        Implements functionality which accepts Projects from user and executes
        them via plugabble executors
    """

    def __init__(self, *, executor_name="local", executor=None, inside_script="", outside_script=""):
        if executor:
            self.executor = executor
        else:
            if executor_name == "local":
                self.executor = LocalExecutor()
            elif executor_name == "slurm":
                self.executor = SLURMExecutor()
            elif executor_name == "ssam":
                self.executor = SSAMExecutor()
            else:
                raise ValueError(f"Unknown executor: {executor_name}")
        self.inside_script = inside_script or "inside.sh"
        self.outside_script = outside_script or "outside.sh"
        # List of runs we know about
        # Should be persisted to a database
        self.runs = []

    def reference_to_run(self, ref):
        return self.runs[ref.index]

    def run_to_reference(self, run):
        return self.runs.index(run)

    def wait(self, run_id):
        self.runs[run_id].submitted_run.wait()

    def get_status(self, run_id):
        return self.runs[run_id].submitted_run.get_status()

    def enqueue_run(
        self,
        run_id,
        tarball_path,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
        user_subj="",
    ):
        """
        Takes the user request, then submits to a job backend on their behalf (either local or SLURM)

        :param run_id: MLFlow RunID
        :param tarball_path: Path to the users' sandbox
        :param entry_point: Entry point to execute (from MLProject config)
        :param params: Paramaters to pass to task (from MLProject config)
        :param backend_config: MLTF backend config, hardware requests, etc.. (from MLProject config)
        :param tracking_uri: What URI to use to send MLFlow logging (from client env if provided, default set otherwise)
        :param experiment_id: What experiment to group this run under (from client if provided)
        :param user_subj: Subject of the user submitting task (string) (from REST layer)
        :return: A SubmittedRun describing the asynchronously-running task
        """

        run_desc = GatewayRunDescription(
            run_id,
            tarball_path,
            entry_point,
            params,
            backend_config,
            tracking_uri,
            experiment_id,
            user_subj,
        )

        exec_context = self.get_execution_snippet(
            run_desc, self.inside_script, self.outside_script
        )

        async_req = self.executor.run_context_async(exec_context, run_desc)
        run = GatewaySubmittedRunDescription(run_desc, async_req)
        self.runs.append(run)

        return run

    # See docs for RunReference for an explanation
    enqueue_run_client = return_id_decorator(enqueue_run)

    @staticmethod
    def get_execution_snippet(
        run_desc, inside_script="inside.sh", outside_script="outside.sh"
    ):
        """
        :param run_desc: Descriptor provided by MLFlow
        :return: what to run - list of files, then a list of lists for command lines
        """
        input_files = {
            "outside.sh": MovableFileReference(get_script(outside_script)),
            "inside.sh": MovableFileReference(get_script(inside_script)),
            "client-tarball": MovableFileReference(run_desc.tarball_path),
        }
        cmdline = [
            "/bin/bash",
            "input/outside.sh",
            "-i",
            "input/inside.sh",
            "-t",
            "input/project.tar.gz",
        ]
        all_lines = cmdline
        return {"commands": all_lines, "files": input_files}