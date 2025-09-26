"""
Token management views and utilities
"""

from flask import Blueprint, jsonify, url_for
from ..extensions import db
from ..utils import get_token_url


token_api_bp = Blueprint("token_api", __name__)


@token_api_bp.route("/url", methods=["GET"])
def token_url():
    """
    Get a mock URL for obtaining OAuth2 tokens
    Returns:
        JSON with a mock token URL
    """
    url = get_token_url(
        redirect_uri=url_for("auth.oauth2_callback", api=True, _external=True)
    )
    return jsonify({"token_url": url}), 200
