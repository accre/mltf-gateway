#!/bin/bash

#
# Entrypoint for mltf gateway server
#

source /mltf/venv/bin/activate
mltf server --debug
