from flask_login import UserMixin
from ..extensions import db, login_manager


class User(UserMixin, db.Model):
    """
    Simple User model for authentication
    """

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(64), nullable=True)


@login_manager.user_loader
def load_user(identifier):
    """
    Load a user by ID
    Args:
        identifier (str): The user ID
    Returns:
        User object or None if not found
    """
    return db.session.get(User, int(identifier))
