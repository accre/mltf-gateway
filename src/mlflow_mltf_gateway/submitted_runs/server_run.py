import time
import uuid
from dataclasses import dataclass, field

from mlflow.projects import SubmittedRun

from mlflow_mltf_gateway.data_classes import GatewayRunDescription


@dataclass
class ServerSideSubmittedRunDescription:
    """
    Stores information about a Run submitted to an executor.

    run_desc: the user-provided definition of the run
    submitted_run: handle pointing to the actual execution (e.g. SLURM job)
    """

    run_desc: GatewayRunDescription
    submitted_run: SubmittedRun
    gateway_id: str
    creation_time: int = field(init=False)

    def __post_init__(self):
        self.creation_time = int(time.time())

    def to_client_json(self):
        """
        Extract/sanitize static info from this description for return back to the
        client. This shouldn't contain dynamic information like status, etc
        :return: json
        """
        return {
            "run_id": self.run_desc.run_id,
            "gateway_id": self.gateway_id,
            "creation_time": self.creation_time,
        }
