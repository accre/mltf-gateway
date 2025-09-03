#!/usr/bin/env python3
import json
import os
import os.path
import requests
import functools
import tarfile
import time
import mlflow_mltf_gateway.project_packer as project_packer

URL = "https://gateway-dev.mltf.k8s.accre.vanderbilt.edu"


def get_state():
    if os.path.exists(".token"):
        try:
            return json.load(open(".token", "r"))
        except:
            clear_state()
            return None
    return None


def save_state(s):
    json.dump(s, open(".token", "w"))


def clear_state():
    if os.path.exists(".token"):
        os.remove(".token")


def get_token():
    s = get_state()
    if s:
        return s
    else:
        s = refresh_token()
        save_state(s)
        return s


def refresh_token():
    global URL
    r = requests.get(URL + "/auth/url")
    r.raise_for_status()

    auth_url_response = r.json()
    print(f"Visit {auth_url_response['verification_uri_complete']}")
    token_info = None
    for _ in range(
        int(auth_url_response["expires_in"] / auth_url_response["interval"])
    ):
        r = requests.post(
            URL + "/auth/poll", data={"device_code": auth_url_response["device_code"]}
        )
        r.raise_for_status()
        ret = r.json()
        print(ret)
        print(f"response code {r.status_code}")
        if "error" in ret:
            print("sleeping")
            time.sleep(auth_url_response["interval"])
        else:
            print("Login complete")
            token_info = ret
            token_info["requested_time"] = int(time.time())
            break
    return token_info


token = get_token()

print("Current requests:")
auth_get = functools.partial(
    requests.get, headers={"Authorization": f"Bearer {token['access_token']}"}
)
auth_post = functools.partial(
    requests.post, headers={"Authorization": f"Bearer {token['access_token']}"}
)
r = auth_get(URL + "/api/projects")
print(r.json())

INPUT_DIR = "/Users/meloam/projects/mltf-gateway/client/mlflow-mltf-gateway/demo"

project_tarball = project_packer.prepare_tarball(INPUT_DIR)
print(f"tarball is {project_tarball}")
r = auth_post(
    URL + "/api/projects",
    data={"name": "testreq1"},
    files={"file": open(project_tarball, "rb")},
)
print(r)
print(r.json())
r.raise_for_status()

r = auth_get(URL + "/api/projects")
print(r.json())


class decotest:
    pass


@decotest()
def f():
    print("hi")
