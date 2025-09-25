"""
    Gateway API endpoints. Main place for apis to exist
"""

from flask import Blueprint, jsonify, g
from ..utils import require_oauth_token

gateway_api_bp = Blueprint('gateway_api', __name__)

@gateway_api_bp.route("/securedata")
@require_oauth_token
def secure_data():
    return jsonify({
        "message": "Hello",
        "email": g.user["email"],
        "username": g.user["username"]
    })
