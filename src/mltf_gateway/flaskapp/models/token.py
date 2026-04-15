from ..extensions import db


class Token(db.Model):
    """
    Model to store OAuth tokens
    """

    __tablename__ = "tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=True)
    token_type = db.Column(db.String(64), nullable=True)
    expires_in = db.Column(db.Integer, nullable=True)
    scope = db.Column(db.String(256), nullable=True)
    user = db.relationship("User", backref=db.backref("tokens", lazy=True))
