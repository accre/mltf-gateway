#
# Had to break this into a separate file to break a circular import
#
import logging

from mlflow.projects import SubmittedRun

_logger = logging.getLogger(__name__)


class GatewaySubmittedRun(SubmittedRun):
    """
    Tracks a single Run submitted to an MLTF Gateway
    """

    def __init__(self, adapter, run_id, gateway_id):
        self.adapter = adapter
        self.id = run_id
        self.gateway_id = gateway_id

    def wait(self):
        _logger.info(f"Waiting on GatwaySubmittedRun({self.gateway_id})")
        self.adapter.wait(self.gateway_id)

    def get_status(self):
        _logger.info(f"Checking status of GatwaySubmittedRun({self.gateway_id})")
        return self.adapter.get_status(self.gateway_id)

    def cancel(self):
        _logger.info(f"Cancelling GatwaySubmittedRun({self.gateway_id})")
        self.adapter.cancel(self.gateway_id)

    @property
    def run_id(self):
        _logger.info(
            f"Retrieving mlflow run_id for GatwaySubmittedRun({self.gateway_id})"
        )
        return self.id

    def __str__(self):
        return f"<GatewaySubmittedRun run_id={self.id}, gateway_id={self.gateway_id}"
