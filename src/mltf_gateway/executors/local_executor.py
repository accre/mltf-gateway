import subprocess

from mltf_gateway.submitted_runs.local_run import LocalSubmittedRun
from .base import ExecutorBase
import os
import copy

class LocalExecutor(ExecutorBase):
    """
    Executor that runs jobs locally
    """

    def run_context_async(self, ctx, run_desc, gateway_id):
        cmdline_resolved = [str(x) for x in ctx["commands"]]

        child = subprocess.Popen(
            args=cmdline_resolved,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        return LocalSubmittedRun(run_desc.run_id, child)