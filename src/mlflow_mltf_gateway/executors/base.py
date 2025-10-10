import os

from jinja2 import Environment, FunctionLoader

import mlflow_mltf_gateway.resources as script_path


def get_script(script_name):
    """
    Helper to load a script from the python package
    :param script_name: Name within the package
    :return: Absolute path to the file
    """
    ret = os.path.join(os.path.dirname(script_path.__file__), script_name)
    if not os.path.exists(ret):
        raise RuntimeError(f"Script {script_name} not found")
    return ret


def jinja_loader(script_name):
    """
    Loads a script for Jinja
    :param script_name: Script to load
    :return: String containing text
    """
    with open(get_script(script_name)) as f:
        return f.read()


jinja_env = Environment(loader=FunctionLoader(jinja_loader))


class ExecutorBase:
    """
    Base class for executors
    """

    def run_context_async(self, ctx, run_desc, gateway_id):
        """
        Executes a task asynchronosly
        :param ctx: execution context - input files and command line to execute
        :param run_desc: run descriptor
        :return:
        """
        raise NotImplementedError("This method should be overridden by subclasses")
