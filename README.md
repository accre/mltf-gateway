# MLflow MLTF Gateway

This project provides a gateway for managing MLflow projects with distributed execution capabilities.

## Features

- MLflow project execution with custom backends
- Support for local and remote execution environments
- OAuth2 authentication support for secure access

## OAuth2 Authentication

The MLTF CLI now supports OAuth2 device flow authentication:

### Setup

Before using the CLI, you need to set up your OAuth2 credentials. You can do this by setting environment variables:

```bash
export MLTF_CLIENT_ID="your_client_id"
export MLTF_CLIENT_SECRET="your_client_secret"
export MLTF_AUTH_URL="https://your-oauth-provider.com/oauth/authorize"
export MLTF_TOKEN_URL="https://your-oauth-provider.com/oauth/token"
export MLTF_SCOPES="read write"
```

### Usage

1. **Login**:
   ```bash
   mltf login
   ```

2. **Use the CLI**:
   ```bash
   mltf list
   mltf create --name "my-job"
   mltf delete --id "job-id"
   ```

3. **Logout**:
   ```bash
   mltf logout
   ```

## Installation

```bash
pip install -e .
```

## Usage

The main CLI command is `mltf`:

```bash
mltf --help
```

## Development

To run tests:

```bash
python -m pytest tests/
```
```
