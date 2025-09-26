from flask import Blueprint, jsonify, g, request, current_app
from ..utils import require_oauth_token
import json
import tempfile
from ...gateway_server import GatewayServer


gateway_api_bp = Blueprint('gateway_api', __name__)

@gateway_api_bp.route("/securedata")
@require_oauth_token
def secure_data():
    return jsonify({
        "message": "Hello",
        "email": g.user["email"],
        "username": g.user["username"]
    })


@gateway_api_bp.route("/job", methods=["POST"])
@require_oauth_token
def submit():
    """
        Submit a new job to the gateway server
        Expects a multipart/form-data request with the following fields:
            - tarball: The tarball file containing the MLflow project
            - entry_point: The entry point to run
            - params: JSON string of parameters for the entry point
            - backend_config: JSON string of backend configuration
            - tracking_uri: The MLflow tracking URI
            - experiment_id: The MLflow experiment ID
        Returns:
            JSON response with job reference details
    """
    tarball = request.files["tarball"]
    run_id = request.form["run_id"]
    entry_point = request.form["entry_point"]
    params = json.loads(request.form["params"])
    backend_config = json.loads(request.form["backend_config"])
    tracking_uri = request.form["tracking_uri"]
    experiment_id = request.form["experiment_id"]
    user_subj = g.user["username"]

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tarball.save(tmp.name)
        gateway_server = current_app.extensions["mltf_gateway"]
        run_reference = gateway_server.enqueue_run_client(
            run_id=run_id,
            tarball_path=tmp.name,
            entry_point=entry_point,
            params=params,
            backend_config=backend_config,
            tracking_uri=tracking_uri,
            experiment_id=experiment_id,
            user_subj=user_subj,
        )
        return jsonify(run_reference.__dict__)


@gateway_api_bp.route("/job/<job_id>", methods=["GET"])
@require_oauth_token
def status(job_id):
    status = "running"
    return jsonify({"job_id": job_id, "status": status}), 200


@gateway_api_bp.route("/job/<job_id>", methods=["DELETE"])
@require_oauth_token
def result(job_id):
    return jsonify({"job_id": job_id, "message": "Job cancelled"}), 200
