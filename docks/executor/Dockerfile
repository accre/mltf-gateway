FROM rockylinux:9

RUN yum groupinstall -y --nodocs "Development Tools" && yum clean all
RUN yum install -y openssl-devel readline-devel ncurses-devel libffi-devel bzip2-devel sqlite-devel python3.12 git epel-release && yum clean all
RUN yum install -y slurm && yum clean all

COPY slurm.conf /etc/slurm/slurm.conf
