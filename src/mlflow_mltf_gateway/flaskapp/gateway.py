from flask import Flask, request, jsonify
import os
import functools

# Import OAuth2 client for authentication
from mlflow_mltf_gateway.oauth_client import is_authenticated, get_access_token

app = Flask(__name__)


def require_oauth(f):
    """Decorator to require OAuth2 authentication for routes"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if the request has a valid OAuth2 token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401

        # In a real implementation, we would validate the token with the OAuth2 provider
        # For now, we'll just check if we have valid stored credentials
        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401

        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def hello_world():
    return """<p>This URL is intended to be accessed by the CLI. Please see
              <a href="http://github.com/accre/mltf-gateway"> GitHub</a> for more info</p>"""


@app.route("/.mltf_gateway_version")
def get_version():
    """
    A dummy for now, but can be used in the future to support REST schema evolution
    :return: API version of this server
    """
    return "0.0.1"


# Example protected routes that would require OAuth2 authentication
@app.route("/enqueue", methods=['POST'])
@require_oauth
def enqueue_run():
    """Endpoint to enqueue a new run - requires authentication"""
    # In a real implementation, you'd process the request data here
    return jsonify({'message': 'Run enqueued successfully'})


@app.route("/wait/<run_id>", methods=['GET'])
@require_oauth
def wait_for_run(run_id):
    """Endpoint to wait for a run completion - requires authentication"""
    # In a real implementation, you'd implement waiting logic here
    return jsonify({'message': f'Waiting for run {run_id}'})


@app.route("/status/<run_id>", methods=['GET'])
@require_oauth
def get_run_status(run_id):
    """Endpoint to get run status - requires authentication"""
    # In a real implementation, you'd return the actual status
    return jsonify({'status': 'running', 'run_id': run_id})


@app.route("/health", methods=['GET'])
def health_check():
    """Health check endpoint - no authentication required"""
    return jsonify({'status': 'healthy'})

