import functools
import pickle

from mlflow_mltf_gateway.submitted_runs.server_run import (
    ServerSideSubmittedRunDescription,
)
from .data_classes import (
    MovableFileReference,
    RunReference,
    GatewayRunDescription,
)
from .executors.base import get_script, ExecutorBase
from .executors.local_executor import LocalExecutor
from .executors.slurm_executor import SLURMExecutor
from .executors.ssam_executor import SSAMExecutor

DEBUG = False

# Very simple persistence for now, can be shoved into SQLite or similar later
RUN_DATABASE = "gateway_run_db.pkl"


def persist_runs(runs):
    with open(RUN_DATABASE, "wb") as f:
        pickle.dump(runs, f)


def unpersist_runs():
    try:
        with open(RUN_DATABASE, "rb") as f:
            return pickle.load(f)
    except:
        pass
    return []


def return_id_decorator(f):
    """
    Helper wrapper to take a function which returns a SubmittedRun
    and converts to return a RunReference
    """

    @functools.wraps(f)
    def wrapper(self: "GatewayServer", *args, **kwargs):
        ret = f(self, *args, **kwargs)
        return self.run_to_reference(ret)

    return wrapper


class GatewayServer:
    """
    Implements functionality which accepts Projects from user and executes
    them via plugabble executors
    """

    runs: list[ServerSideSubmittedRunDescription]

    def __init__(
        self,
        *,
        executor_name: str = "local",
        executor: ExecutorBase = None,
        inside_script="",
        outside_script="",
    ):
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
        self.runs = unpersist_runs()

    def list(self, list_all, user_subject):
        """
        Returns runs this server is aware of belonging to a given user_subject
        :param list_all: if true, return all jobs regardless if they've been completed/cancelled
        :param user_subject: subject of the user doing the querying
        :return: list of GatewaySubmittedRun
        """
        # FIXME support filtering jobs based on list_all param
        ret = []
        for idx in range(len(self.runs)):
            r = self.runs[idx]
            if r.run_desc.user_subject != user_subject:
                continue
            ret.append(r.to_client_json())

        return ret

    def reference_to_run(self, ref: RunReference) -> ServerSideSubmittedRunDescription:
        """
        We store/persist run information within GatewayServer, but we shouldn't bother the client with those details.
        Instead, give the client an (opaque) integer reference to the run object
        :param ref: Integer reference to the run
        :return: GatewaySubmittedRun referred to by reference
        """
        for r in self.runs:
            if ref.gateway_id == r.gateway_id:
                return r
        raise IndexError()

    def run_to_reference(self, run: ServerSideSubmittedRunDescription) -> RunReference:
        """
        See reference_to_run. This is the opposite
        :param run: GatewaySubmittedRun object
        :return: Integer reference to run
        """
        return RunReference(run.gateway_id)

    def wait(self, run_ref):
        """
        Waits for a specified run to complete execution
        :param run_ref: Integer reference to run
        :return:
        """
        self.reference_to_run(run_ref).submitted_run.wait()

    def get_status(self, run_ref):
        """
        Get execution status of a run
        :param run_ref: Integer reference to run
        :return: Stateus
        """
        return self.reference_to_run(run_ref).submitted_run.get_status()

    def enqueue_run(
        self,
        run_id,
        tarball_path,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
        user_subj,
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
        run = ServerSideSubmittedRunDescription(run_desc, async_req)
        self.runs.append(run)
        persist_runs(self.runs)
        return run

    # See docs for RunReference for an explanation
    enqueue_run_client = return_id_decorator(enqueue_run)

    @staticmethod
    def get_execution_snippet(
        run_desc, inside_script="inside.sh", outside_script="outside.sh"
    ):
        """
        :param run_desc: Descriptor provided by MLFlow
        :param inside_script: Script to run inside the container
        :param outside_script: Script which executes the container, passing control to the inside_script
        :return: what to run - list of files, then a list of lists for command lines
        """
        input_files = {
            "outside.sh": MovableFileReference(get_script(outside_script)),
            "inside.sh": MovableFileReference(get_script(inside_script)),
            "client-tarball": MovableFileReference(run_desc.tarball_path),
        }
        # FIXME point input files to input_files dict so files can be moved
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
