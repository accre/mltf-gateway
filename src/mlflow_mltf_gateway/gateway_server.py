import os
import os.path
import shutil
import subprocess
import shlex
import tempfile
import datetime
import functools

from dataclasses import dataclass

import jinja2
from jinja2 import Environment, FunctionLoader
from mlflow.projects.submitted_run import LocalSubmittedRun, SubmittedRun

DEBUG = False


def jinja_loader(script_name):
    """
    Loads a script for Jinja
    :param script_name: Script to load
    :return: String containing text
    """
    with open(get_script(script_name)) as f:
        return f.read()


jinja_env = Environment(loader=FunctionLoader(jinja_loader))


def get_script(script_name):
    """
    Helper to load a script from the python package
    :param script_name: Name within the package
    :return: Absolute path to the file
    """
    import mlflow_mltf_gateway.resources as script_path

    ret = os.path.join(os.path.dirname(script_path.__file__), script_name)
    if not os.path.exists(ret):
        raise RuntimeError(f"Script {script_name} not found")
    return ret


def return_id_decorator(f):
    """
    Helper wrapper to take a function which returns a SubmittedRun and converts to return a RunReference
    """

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        print(self.runs)
        return RunReference(self.runs.index(ret))

    return wrapper


class GatewayServer:
    """
    Implements functionality which accepts Projects from user and executes
    them via plugabble executors
    """

    def __init__(self, *, executor=None, inside_script="", outside_script=""):
        self.executor = executor if executor else LocalExecutor()
        self.inside_script = inside_script or "inside.sh"
        self.outside_script = outside_script or "outside.sh"
        # List of runs we know about
        # Should be persisted to a database
        self.runs = []

    def reference_to_run(self, ref):
        return self.runs[ref.index]

    def run_to_reference(self, run):
        return self.runs.index[run]

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
        run = GatewaySubmittedRun(run_desc, async_req)
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
            input_files["outside.sh"],
            "-i",
            input_files["inside.sh"],
            "-t",
            input_files["client-tarball"],
        ]
        all_lines = cmdline
        return {"commands": all_lines, "files": input_files}


@dataclass
class RunReference:
    """
    The primary use-case of the Gateway server is to be called via REST, which means we don't want to exchange
    SubmittedRun references with clients (since they contain things that either don't serialize or are sensitive). Instead,
    we exchange RunReferences with the client, which points to a SubmittedRun reference the GatewayServer object owns
    """

    # For now, this is just the index into GatewayServer's runs list where the "real" object lives
    index: int


@dataclass
class MovableFileReference:
    """
    Wrap around a path so that we can store this in a command line then concrete executors can move files to somewhere
    appropriate (e.g. slurm w/o a shared filesystem). If the path is just a string then this becomes difficult
    """

    target: str

    def copy_to_dir(self, target_dir: str):
        target = os.path.join(target_dir, os.path.basename(self.target))
        assert os.path.isdir(target_dir)
        assert not os.path.exists(target)
        shutil.copy(self.target, target)
        self.target = target
        return self

    def __str__(self):
        return self.target


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
class GatewaySubmittedRun:
    """
    Stores information about a Run submitted to an executor.

    run_desc: the user-provided definition of the run
    submitted_run: handle pointing to the actual execution (e.g. SLURM job)
    """

    run_desc: GatewayRunDescription
    submitted_run: SubmittedRun


class ExecutorBase:
    def run_context_async(self, ctx, run_desc):
        """
        Executes a task asynchronosly
        :param ctx: execution context - input files and command line to execute
        :param run_desc: run descriptor
        :return:
        """
        raise RuntimeError("Not Implemented?")


class LocalExecutor(ExecutorBase):
    def run_context_async(self, ctx, run_desc):
        cmdline_resolved = [str(x) for x in ctx["commands"]]
        child = subprocess.Popen(args=cmdline_resolved, start_new_session=True)
        return LocalSubmittedRun(run_desc.run_id, child)


class SLURMSubmittedRun(SubmittedRun):
    def __init__(self, run_id, slurm_id):
        super().__init__()
        self.run_id = run_id
        self.slurm_id = slurm_id


class SLURMExecutor(ExecutorBase):

    # Files in below this directory are visible to all hosts
    # Needs to be configurable
    # For some reason, /home doesn't work here on MacOS because of something
    # with realpath()
    shared_paths = ["/panfs/", "/cvmfs/", "/home", os.path.expanduser("~")]

    def __init__(self):
        # Where files should be spooled. Should become configurable
        self.spool_base = os.path.expanduser("~/mltf-spool")

    def ensure_files_spooled(self, input_files):
        """
        Since we're submitting to SLURM, it's probable that /tmp on the submittion host is not visible to the
        executing hosts. This function any files in the run descriptor to a spool dir if it is not in a
        whitelist of shared paths
        :param input_files: A list of MovableFileReference

        """

        # Find files not in the shared path we're expecting
        to_move = []
        for f in input_files.values():
            initial_path = os.path.realpath(str(f), strict=True)
            path_matched = False
            for p in self.shared_paths:
                # Samefile fails if the path doesn't exist, so let's not check
                # against shared_paths not on the executing host
                if not os.path.exists(p):
                    continue
                real_p = os.path.realpath(p)
                common = os.path.commonpath([initial_path, real_p])
                if os.path.samefile(common, real_p):
                    path_matched = True
                    break
            if not path_matched:
                to_move.append(f)

        # We have some files that need to move, let's make a spool subdir and copy them
        if to_move:
            spool_date = datetime.date.today().isoformat()
            if not os.path.exists(self.spool_base):
                os.mkdir(self.spool_base)
            with tempfile.TemporaryDirectory(
                dir=self.spool_base, prefix=f"mltf-{spool_date}-", delete=False
            ) as spool_dir:
                for f in to_move:
                    f.copy_to_dir(spool_dir)

    def generate_slurm_template(self, ctx, run_desc):
        self.ensure_files_spooled(ctx["files"])
        cmdline_resolved = shlex.join([str(x) for x in ctx["commands"]])
        slurm_template = jinja_env.get_template("slurm-wrapper.sh")
        return slurm_template.render({"command": cmdline_resolved})

    def run_context_async(self, ctx, run_desc):
        generated_wrapper = self.generate_slurm_template(ctx, run_desc)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(generated_wrapper.encode("utf-8"))
            f.close()
            print(f"SBATCH at {f.name}")
            child = subprocess.Popen(["sbatch", f.name])
        return LocalSubmittedRun(run_desc.run_id, child)
        # return SLURMSubmittedRun(run_desc.run_id, 42)
