from mlflow.projects.submitted_run import LocalSubmittedRun as BaseLocalSubmittedRun


class LocalSubmittedRun(BaseLocalSubmittedRun):
    # Popen objs cannot be pickled, add this dunder method to delete the object
    # Maybe in the future it can be re-hydrated into a different object?
    def __getstate__(self):
        """Return state values to be pickled."""
        state = self.__dict__.copy()
        if "command_proc" in state:
            state["command_pid"] = state["command_proc"].pid
            del state["command_proc"]
        return state

    def get_run_details(self, show_logs):
        if not hasattr(self, "logs"):
            self.logs = ""

        if show_logs:
            self.get_log()

        return {
            "status": self.get_status(),
            "pid": self.command_proc.pid,
            "logs": self.logs,
        }

    def get_log(self):
        stdout, stderr = self.command_proc.communicate()
        assert not stderr
        self.logs = self.logs + stdout.decode()
        return self.logs