#
# Had to break this into a separate file to break a circular import
#
from mlflow.projects import SubmittedRun


class GatewaySubmittedRun(SubmittedRun):
    """
    Tracks a single Run submitted to an MLTF Gateway
    """

    def __init__(self, adapter, run_id):
        self.adapter = adapter
        self.id = run_id

    def wait(self):
        self.adapter.wait(self.id)

    def get_status(self):
        return self.adapter.get_status(self.id)

    def cancel(self):
        self.adapter.cancel(self.id)

    @property
    def run_id(self):
        return self.id
