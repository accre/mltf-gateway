"""
Utility functions for MLTF backend.
"""
import os
import shlex
from typing import Tuple, List

DEFAULT_TRACKING_SERVER = "https://mlflow-test.mltf.k8s.accre.vanderbilt.edu"

def get_tracking_uri() -> str:
    """
    Get the tracking URI from environment variable or use default.
    :return: The tracking URI.
    """
    tracking_uri = DEFAULT_TRACKING_SERVER
    if os.environ.get("MLFLOW_TRACKING_URI"):
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    return tracking_uri

def try_split_cmd(cmd: str) -> Tuple[str, List[str]]:
    """
    Given a command string, try to split it into an entry point and args.
    This is a best-effort approach that tries to handle various cases, but
    may not work in all cases.
    :param cmd: The command string to split.
    :return: A tuple of (entry_point, args).
    """
    parts = []
    found_python = False
    for part in shlex.split(cmd):
        if part == "-m":
            continue
        elif not found_python and part.startswith("python"):
            found_python = True
            continue
        parts.append(part)
    entry_point = ""
    args = []
    if len(parts) > 0:
        entry_point = parts[0]
    if len(parts) > 1:
        args = parts[1:]
    return entry_point, args


def get_ssam_job_description(backend_config: dict) -> dict:
    """
    Given a backend config, return a dictionary of Slurm directives.
    :param backend_config: The backend configuration dictionary.
    :return: A dictionary of Slurm directives.
    """
    new_config = backend_config.copy()
    if "job_name" not in new_config:
        new_config["job_name"] = "mltf-train"
    if "url" in new_config:
        del new_config["url"]
    if "auth_token" in new_config:
        del new_config["auth_token"]

    return new_config
