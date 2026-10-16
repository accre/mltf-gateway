from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class BaseModel(DeclarativeBase):
    """subclasses will be converted to dataclasses"""

    pass


db = SQLAlchemy(model_class=BaseModel)
login_manager = LoginManager()
login_manager.login_view = "auth.login"  # where to redirect for @login_required
