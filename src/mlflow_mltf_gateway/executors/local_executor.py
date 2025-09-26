import subprocess

from mlflow.projects.submitted_run import LocalSubmittedRun
from .base import ExecutorBase


class LocalExecutor(ExecutorBase):
    """
        Executor that runs jobs locally
    """
    def run_context_async(self, ctx, run_desc):
        cmdline_resolved = [str(x) for x in ctx["commands"]]
        child = subprocess.Popen(args=cmdline_resolved, start_new_session=True)
        return LocalSubmittedRun(run_desc.run_id, child)