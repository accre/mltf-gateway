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
