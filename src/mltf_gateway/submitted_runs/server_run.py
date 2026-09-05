import time
from dataclasses import dataclass, field

from mlflow.projects import SubmittedRun
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, composite
from mltf_gateway.server.extensions import db
from mltf_gateway.data_classes import GatewayRunDescription
from mltf_gateway.server.utils import TextPickleType


class Director(db.Model):
    __tablename__ = "directors2"

    id: Mapped[int] = db.mapped_column(primary_key=True, init=False)
    name: Mapped[str] = db.mapped_column(nullable=False, unique=True)
    run_desc: Mapped[GatewayRunDescription] = db.mapped_column(TextPickleType())



class TaskDescription(db.Model):
    """
    Stores information about a Run submitted to an executor.

    run_desc: the user-provided definition of the run
    submitted_run: handle pointing to the actual execution (e.g. SLURM job)
    """
    __tablename__ = "test5"

    db_idx: Mapped[int] = db.mapped_column(primary_key=True, init=False, autoincrement=True, nullable=False)
    run_desc: Mapped[GatewayRunDescription] = db.mapped_column(TextPickleType())
    submitted_run: Mapped[SubmittedRun] = db.mapped_column(TextPickleType())
    gateway_id: Mapped[str] = db.mapped_column()
    creation_time: Mapped[int] = db.mapped_column(init=False)
    user_subject: Mapped[str] = db.mapped_column(init=False)

    def __post_init__(self):
        self.creation_time = int(time.time())
        self.user_subject = self.run_desc.user_subject

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
def reset_subject(mapper,connection, target):
    """
    Keep inner and outer definition of user_subject in sync
    """
    target.user_subject = target.run_desc.user_subject