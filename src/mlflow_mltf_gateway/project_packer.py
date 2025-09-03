import json
import os
import os.path
import tarfile
import tempfile
import urllib.parse


def prepare_tarball(url):
    """
    Given a URL to a workspace, generate a tarball to upload to the gateway.
    Handle ignoring large/unneeded files like virtual env or git trees. This is split
    into two parts so the client can refuse to package/transmit enormous tarfiles

    :param url: A URL or local file path pointing to the desired workspace
    :return: Dict of files to store. Keys are path in tarfile, values are a tuple
                        of (size, modify time, absolute path to file on host)
    """
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme and parsed_url.scheme != "file":
        raise RuntimeError("Loading remote workspaces currently unsupported")
    file_catalog = {}
    for root, dirs, files in os.walk(parsed_url.path):
        relative_root = os.path.relpath(root, parsed_url.path)
        if relative_root == "." and "mlruns" in dirs:
            dirs.remove("mlruns")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        if ".git" in dirs:
            dirs.remove(".git")
        for onedir in dirs:
            if os.path.exists(os.path.join(root, onedir, "pyvenv.cfg")):
                dirs.remove(onedir)
        for f in files:
            # Don't add pyc files
            if f.endswith(".pyc"):
                noext = f[:-4] + ".py"
                if noext in files:
                    continue
            absolute_path = os.path.join(root, f)
            relative_path = os.path.join(relative_root, f)
            info = os.stat(absolute_path)
            file_catalog[relative_path] = (info.st_size, info.st_mtime, absolute_path)
    return file_catalog


def produce_tarball(file_catalog):
    """
    With given file catalog, write a tarball with the user environment.

    TODO: make this a streaming interface, so the tarfile can be piped directly to
          the HTTP socket w/o needing to write a tarball to the local filesystem

    :param file_catalog: Dict of files to store. Keys are path in tarfile, values are a tuple
                        of (size, modify time, absolute path to file on host)
    :return: Path to tarball, it is caller's responsibility to clean up this file after use
    """
    with tempfile.NamedTemporaryFile(delete=False, delete_on_close=False) as nf:
        with tarfile.TarFile(fileobj=nf, mode="w") as tf:
            # Put some metadata at the front of the tarball
            with tempfile.NamedTemporaryFile(buffering=0) as meta:
                meta_info = {"file_catalog": file_catalog}
                meta.write(json.dumps(meta_info).encode("utf-8"))
                tf.add(name=meta.name, arcname="./.mltf_meta")
            # Sorting the filenames makes it so the shorter filenames are added first, hopefully making it so the
            # MLProject and env files are "earlier" in the tarfile, so the server has to do less searching
            for f in sorted(file_catalog.keys()):
                tf.add(name=file_catalog[f][2], arcname=f, recursive=False)
        return nf.name


def package_project(url):
    """
    Given a project URL, package it into a tarball

    :param url: URI of user project
    :return: path to generated tarball. It is callers responsibility to delete this file
    """
    return produce_tarball(prepare_tarball(url))


if __name__ == "__main__":
    print(
        package_project(
            "/Users/meloam/projects/mltf-gateway/client/mlflow-mltf-gateway"
        )
    )
