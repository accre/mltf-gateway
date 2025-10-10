import os
import shlex
import tempfile
import datetime
import subprocess


from .base import ExecutorBase, jinja_env
from mlflow.projects.submitted_run import LocalSubmittedRun


class SLURMExecutor(ExecutorBase):
    """
    Files in below this directory are visible to all hosts
    Needs to be configurable
    For some reason, /home doesn't work here on MacOS because of something
    with realpath()
    """

    shared_paths = ["/panfs/", "/cvmfs/", "/home", os.path.expanduser("~")]

    def __init__(self):
        # Where files should be spooled. Should become configurable
        self.spool_base = os.path.expanduser("~/mltf-spool")

    def ensure_files_spooled(self, input_files):
        """
        Since we're submitting to SLURM, it's probable that /tmp on the submittion host is not visible to the
        executing hosts. This function any files in the run descriptor to a spool dir if it is not in a
        whitelist of shared paths
        :param input_files: A list of MovableFileReference

        """

        # Find files not in the shared path we're expecting
        to_move = []
        for f in input_files.values():
            initial_path = os.path.realpath(str(f), strict=True)
            path_matched = False
            for p in self.shared_paths:
                # Samefile fails if the path doesn't exist, so let's not check
                # against shared_paths not on the executing host
                if not os.path.exists(p):
                    continue
                real_p = os.path.realpath(p)
                common = os.path.commonpath([initial_path, real_p])
                if os.path.samefile(common, real_p):
                    path_matched = True
                    break
            if not path_matched:
                to_move.append(f)

        # We have some files that need to move, let's make a spool subdir and copy them
        if to_move:
            spool_date = datetime.date.today().isoformat()
            if not os.path.exists(self.spool_base):
                os.mkdir(self.spool_base)
            with tempfile.TemporaryDirectory(
                dir=self.spool_base, prefix=f"mltf-{spool_date}-", delete=False
            ) as spool_dir:
                for f in to_move:
                    f.copy_to_dir(spool_dir)

    def generate_slurm_template(self, ctx, run_desc):
        self.ensure_files_spooled(ctx["files"])
        cmdline_resolved = shlex.join([str(x) for x in ctx["commands"]])
        slurm_template = jinja_env.get_template("slurm-wrapper.sh")
        return slurm_template.render({"command": cmdline_resolved})

    def run_context_async(self, ctx, run_desc, gateway_id):
        generated_wrapper = self.generate_slurm_template(ctx, run_desc)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(generated_wrapper.encode("utf-8"))
            f.close()
            print(f"SBATCH at {f.name}")
            child = subprocess.Popen(["sbatch", f.name])
        return LocalSubmittedRun(run_desc.run_id, child)
        # return SLURMSubmittedRun(run_desc.run_id, 42)
