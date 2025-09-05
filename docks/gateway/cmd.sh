#!/bin/bash

#
# Entrypoint for mltf gateway server
#

source /mltf/venv/bin/activate
flask --app mlflow_mltf_gateway.flaskapp.gateway run --debug
