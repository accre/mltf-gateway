import logging

from mlflow.projects.submitted_run import SubmittedRun

from mlflow_mltf_gateway.adapters.base import BackendAdapter

_logger = logging.getLogger(__name__)


class ClientSideSubmittedRun(SubmittedRun):
    """
    Client-side representation of a submitted run. Only used by the client (hence the ref to
    the adapter!)

    This should also be the only place inheriting from MLFlow's SubmittedRun
    since this is the only class visible to a client who cares
    """

    def __init__(self, adapter: BackendAdapter, run_id, gateway_id, creation_time):
        self.adapter = adapter
        self._id = run_id
        self.gateway_id = gateway_id
        self.creation_time = creation_time

    @classmethod
    def from_dict(cls, adapter: BackendAdapter, data) -> "ClientSideSubmittedRun":
        """
        Static constructor that creates a ClientSideSubmittedRun instance from an adapter
        and a dictionary containing run_id and gateway_id.
        Args:
            adapter: The adapter instance to use
            data (dict): Dictionary containing 'run_id' and 'gateway_id' keys
        Returns:
            ClientSideSubmittedRun: New instance with the provided values
        """

        return cls(adapter, data["run_id"], data["gateway_id"], data["creation_time"])

    def wait(self):
        _logger.info(f"Waiting on GatewaySubmittedRun({self.gateway_id})")
        self.adapter.wait(self.gateway_id)

    def get_status(self):
        _logger.info(f"Checking status of GatewaySubmittedRun({self.gateway_id})")
        return self.adapter.get_status(self.gateway_id)

    def cancel(self):
        _logger.info(f"Cancelling GatewaySubmittedRun({self.gateway_id})")
        self.adapter.cancel(self.gateway_id)

    @property
    def run_id(self):
        _logger.info(
            f"Retrieving mlflow run_id for GatewaySubmittedRun({self.gateway_id})"
        )
        return self._id

    def __str__(self):
        return f"<GatewaySubmittedRun run_id={self._id}, gateway_id={self.gateway_id}"
