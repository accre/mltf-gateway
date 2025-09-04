from flask import Flask

app = Flask(__name__)


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
