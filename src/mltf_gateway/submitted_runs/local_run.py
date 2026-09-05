from dataclasses import dataclass
import copy

from mlflow.projects.submitted_run import LocalSubmittedRun as BaseLocalSubmittedRun

CACHED_COMMAND_PROC = {}
class LocalSubmittedRun(BaseLocalSubmittedRun):
    """
    SERVER-SIDE: Stores information about a Run being executed via Popen
    """


    # Popen objs cannot be pickled, add this dunder method to delete the object
    # Maybe in the future it can be re-hydrated into a different object?
    def __getstate__(self):
        """Return state values to be pickled."""
        global CACHED_COMMAND_PROC
        state = self.__dict__.copy()
        if "command_proc" in state:
            pid = state["command_proc"].pid
            state["command_pid"] = pid
            CACHED_COMMAND_PROC[pid] = state["command_proc"]
            del state["command_proc"]
        return state

    def __setstate__(self, state):
        """This will only work in the dumbest cases because WSGI is req-per-process. You'll
           have to get lucky"""
        global CACHED_COMMAND_PROC
        pid = state["command_pid"]
        if pid in CACHED_COMMAND_PROC:
            state["command_proc"] = CACHED_COMMAND_PROC[pid]
        self.__dict__.update(state)

    def cancel(self):
        if hasattr(self, "command_proc"):
            super(LocalSubmittedRun, self).cancel()

    def get_run_details(self, show_logs):
        if not hasattr(self, "logs"):
            self.logs = ""

        if hasattr(self, "command_proc"):
            if show_logs:
                self.get_log()

            return {
                "status": self.get_status(),
                "pid": self.command_proc.pid,
                "logs": self.logs,
            }
        else:
            # If we're getting status on a job that ran in a previous life. We can't get to command_proc over
            # restarts, so just fake something
            return {
                "status": "UNKNOWN",
                "pid": 42,
                "logs": "No logs! Local executor previous run",
            }

    def get_log(self):
        stdout, stderr = self.command_proc.communicate()
        assert not stderr
        self.logs = self.logs + stdout.decode()
        return self.logs