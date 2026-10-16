import time

from mlflow.projects import SubmittedRun
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column
from mltf_gateway.server.extensions import db
from mltf_gateway.data_classes import GatewayRunDescription
from mltf_gateway.server.utils import TextPickleType


class TaskDescription(db.Model):
    """
    Stores information about a Run submitted to an executor.

    run_desc: the user-provided definition of the run
    submitted_run: handle pointing to the actual execution (e.g. SLURM job)
    """

    __tablename__ = "runs"

    db_idx: Mapped[int] = db.mapped_column(
        primary_key=True, autoincrement=True, nullable=False
    )
    run_desc: Mapped[GatewayRunDescription] = db.mapped_column(TextPickleType())
    submitted_run: Mapped[SubmittedRun] = db.mapped_column(TextPickleType())
    gateway_id: Mapped[str] = db.mapped_column()
    creation_time: Mapped[int] = db.mapped_column()
    user_subject: Mapped[str] = db.mapped_column()
    status: Mapped[str] = db.mapped_column(default="SCHEDULED")

    def __init__(self, run_desc, submitted_run, gateway_id):
        self.run_desc = run_desc
        self.submitted_run = submitted_run
        self.gateway_id = gateway_id
        self.creation_time = int(time.time())
        self.user_subject = run_desc.user_subject
        self.status = "SCHEDULED"

    @property
    def name(self) -> str:
        """
        User-provided display name for this task (optional).
        Records pickled before the name field existed lack it in their __dict__,
        so guard with getattr + type check and fall back to "".
        """
        task_name = getattr(self.run_desc, "name", "")
        return task_name if isinstance(task_name, str) else ""

    def to_client_json(self):
        """
        Extract/sanitize static info from this description for return back to the
        client. This shouldn't contain dynamic information like status, etc
        :return: json
        """
        return {
            "run_id": self.run_desc.run_id,
            "gateway_id": self.gateway_id,
            "name": self.name,
            "creation_time": self.creation_time,
        }

    def update_status_from_submitted_run(self):
        """
        Update the status field from the submitted_run's status
        """
        if hasattr(self.submitted_run, "get_status"):
            try:
                run_status = self.submitted_run.get_status()
                if isinstance(run_status, str):
                    self.status = run_status
                else:
                    from mlflow.entities import RunStatus

                    self.status = RunStatus.to_string(run_status)
            except Exception:
                pass

    def wait(self):
        return self.submitted_run.wait()

    def can_read(self, user_subject):
        """
        Can the given subject read this object?
        """
        return self.user_subject == user_subject

    def can_write(self, user_subject):
        """
        Can the given subject read this object?
        """
        return self.user_subject == user_subject

    def raise_can_read(self, user_subject):
        """
        Can the given subject read this object?
        throw if not
        """
        if not self.can_read(user_subject):
            raise RuntimeError("Forbidden")

    def raise_can_write(self, user_subject):
        """
        Can the given subject read this object?
        throw if not
        """
        if not self.can_write(user_subject):
            raise RuntimeError("Forbidden")


@event.listens_for(TaskDescription, "before_insert")
@event.listens_for(TaskDescription, "before_update")
def reset_subject(mapper, connection, target):
    """
    Keep inner and outer definition of user_subject in sync. this is called by sqlalchemy
    """
    target.user_subject = target.run_desc.user_subject
