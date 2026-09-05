from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    composite,
)


class BaseModel(MappedAsDataclass, DeclarativeBase):
    """subclasses will be converted to dataclasses"""

    pass


db = SQLAlchemy(model_class=BaseModel)
login_manager = LoginManager()
login_manager.login_view = "auth.login"  # where to redirect for @login_required
