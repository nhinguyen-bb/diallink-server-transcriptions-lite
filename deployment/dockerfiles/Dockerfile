FROM ubuntu:22.04

# Set timezone and avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PYTHONUNBUFFERED=1

# Install system packages and Python 3.12
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
        software-properties-common \
        curl \
        ffmpeg \
        git && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3-pip && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Python 3.12 as default (like your local setup)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Create a user (like local development)
WORKDIR /home/app

# Create virtual environment (like local development)
RUN python -m venv .venv
ENV PATH="/home/app/.venv/bin:$PATH"

