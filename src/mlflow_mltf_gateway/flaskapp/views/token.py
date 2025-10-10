"""
Token management views and utilities
"""

import secrets
from flask import Blueprint, render_template, flash, url_for, session, redirect
from flask_login import login_required, current_user
from ..extensions import db
from ..models.token import Token
from ..utils import get_token_url


token_bp = Blueprint("token", __name__)


def get_current_tokens():
    """
    Retrieve all tokens for the current user
    Returns:
        List of Token objects
    """
    if not current_user.is_authenticated:
        return []
    print(dir(current_user))
    return db.session.scalars(
        db.select(Token).where(Token.user_id == current_user.get_id())
    ).all()


@token_bp.route("/", methods=["GET"])
def index():
    """
    Simple index route for the token blueprint
    Returns:
        rendered template with token information
    """
    new_token_url = get_token_url(
        redirect_uri=url_for("auth.oauth2_callback", token=True, _external=True)
    )
    return render_template(
        "token.html", tokens=get_current_tokens(), new_token_url=new_token_url
    )


@token_bp.route("/token", methods=["GET"])
def create_token():
    """
    Simple index route for the token blueprint
    Returns:
        rendered template with token information
    """
    # generate a random string for the state parameter
    session["oauth2_state"] = secrets.token_urlsafe(16)
    token_url = get_token_url(
        redirect_uri=url_for("auth.oauth2_callback", token=True, _external=True),
        state=session["oauth2_state"],
    )
    # redirect the user to the OAuth2 provider authorization URL
    return redirect(token_url)


@token_bp.route("/delete_token/<int:token_id>", methods=["POST"])
@login_required
def delete_token(token_id):
    """
    Delete a specific token by ID
    Args:
        token_id (int): The ID of the token to delete
    Returns:
        rendered template with updated token list
    """
    token = db.session.get(Token, token_id)
    if token is None or token.user_id != current_user.get_id():
        # push into messages flask
        flash("Token not found or unauthorized", "error")
        return render_template("token.html", tokens=get_current_tokens())

    db.session.delete(token)
    db.session.commit()

    return render_template("token.html", tokens=get_current_tokens())
