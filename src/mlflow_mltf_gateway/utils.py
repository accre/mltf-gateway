"""
Utility functions for MLTF backend.
"""

import shlex
from typing import Tuple, List


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
    return {
        "job_name": backend_config.get("job_name", "mlflow-job"),
        "partition": backend_config.get("partition", "interactive"),
        "nodes": backend_config.get("nodes", 1),
        "ntasks-per-node": backend_config.get("ntasks-per-node", 1),
        "cpus-per-task": backend_config.get("cpus-per-task", 1),
        "mem": backend_config.get("mem", "4gb"),
        "time": backend_config.get("time", "00:20:00"),
        "gpus": backend_config.get("gpus", None),
    }
