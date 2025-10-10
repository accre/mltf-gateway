import subprocess

from mlflow_mltf_gateway.submitted_runs.local_run import LocalSubmittedRun
from .base import ExecutorBase
import time


class LocalExecutor(ExecutorBase):
    """
    Executor that runs jobs locally
    """

    def run_context_async(self, ctx, run_desc, gateway_id):
        cmdline_resolved = [str(x) for x in ctx["commands"]]
        child = subprocess.Popen(args=cmdline_resolved, start_new_session=True)
        # Racy, but we can at least try to see if the job fails immediately
        try:
            child.wait(1)
            if child.returncode != 0:
                # OK, we would like to give some stdout/err here, but we can't do that (easily)
                # and also have a subprocess that is backgrounded
                raise RuntimeError(f"Task exited early")
        except subprocess.TimeoutExpired:
            pass

        return LocalSubmittedRun(run_desc.run_id, child)
