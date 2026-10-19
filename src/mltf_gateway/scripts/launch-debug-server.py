#!/usr/bin/env

#
# Runs the server in a sanitized mode
#
import os.path
import sys

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")

os.environ["AUTH_TOKEN_PATH"] = os.path.join(project_root, "ssam-token")
os.environ["SLURM_TOKEN_PATH"] = os.path.join(project_root, "slurm-token")
os.environ["SSAM_URL"] = "https://ssam.accre.vanderbilt.edu"
from mltf_gateway.scripts.cli import main

sys.argv = [os.path.basename(__file__), "--debug", "server", "--debug"]
main()
