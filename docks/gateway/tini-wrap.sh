#!/bin/bash

if [ "$(uname -m)" == "x86_64" ]; then
  exec /tini-amd64 "$@"
else
  exec /tini-arm64 "$@"
fi
