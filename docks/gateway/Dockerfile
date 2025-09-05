FROM rockylinux:9


# Tini comes with Docker run, but not sure how it works with k8s and company
# so lets install it manually
ENV TINI_VERSION=v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-amd64 /tini-amd64
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-arm64 /tini-arm64

COPY tini-wrap.sh /
RUN chmod +x /tini-amd64 /tini-arm64 /tini-wrap.sh
ENTRYPOINT ["/tini-wrap.sh", "--"]


ARG MLTF_VERSION=0.0.1

RUN yum install -y python3.12 git && yum clean all

RUN <<EOF
mkdir -p /mltf/{venv,state}

python3.12 -m venv /mltf/venv
source /mltf/venv/bin/activate
set -e
if [ -z "$MLTF_VERSION" ]; then
  pip install mlflow-mltf-gateway
else
  pip install mlflow-mltf-gateway==$MLTF_VERSION
fi

EOF

# Inbound port to gateway
EXPOSE 5000
# Where the gateway is executed
WORKDIR /mltf/state
COPY cmd.sh /
CMD ["/bin/bash", "/cmd.sh"]
