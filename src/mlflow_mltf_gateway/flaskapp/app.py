import os
from flask import Flask, render_template, g, request, session
from dotenv import load_dotenv
from .extensions import db, login_manager
from .utils import init_db
from .views.auth import auth_bp
from .views.token import token_bp
from .api_views.token_api import token_api_bp
from .api_views.gateway_api import gateway_api_bp
from .models.user import User

from ..gateway_server import GatewayServer


def init_routes(app):
    """
    Initialize application routes
    Args:
        app: Flask application instance
    Returns: None
    """

    @app.before_request
    def load_user():
        # Example: pull user from session, header, or DB
        user_id = session.get("_user_id", None)
        if user_id:
            g.user = db.session.get(User, int(user_id))
        else:
            g.user = request.headers.get("X-User", None)  # fallback to None

    @app.route("/")
    def landing():
        return render_template("landing.html")


def create_app():
    """
        Create and configure the Flask application

    Returns:
        app: Flask application instance
    """
    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(token_bp, url_prefix="/token")
    app.register_blueprint(token_api_bp, url_prefix="/api/token")
    app.register_blueprint(gateway_api_bp, url_prefix="/api")
    load_dotenv()

    # use env variables or defaults
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///mlflow_mltf_gateway.db"
    )

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)
    if not hasattr(app, "extensions"):
        app.extensions = {}

    executor_name = os.environ.get("MLTF_EXECUTOR", "ssam")
    app.extensions["mltf_gateway"] = GatewayServer(executor_name=executor_name)
    init_routes(app)

    with app.app_context():
        init_db()

    return app
