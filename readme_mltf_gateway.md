# MLflow MLTF Gateway

This document describes how to use the MLflow MLTF Gateway to submit MLflow projects to a remote server.

## Installation

Install the `mlflow-mltf-gateway` package using pip:

```bash
pip install .
```

## Configuration

To use the gateway, you need to configure the following environment variables:

- `MLTF_GATEWAY_URI`: The URI of the MLTF Gateway server. For example, `http://localhost:5000`.
- `MLTF_GATEWAY_TOKEN`: Your OAuth2 access token for the gateway.

```bash
export MLTF_GATEWAY_URI="http://localhost:5000"
export MLTF_GATEWAY_TOKEN="your-access-token"
```

## Authentication

The MLTF Gateway uses OAuth2 for authentication. To get an access token, follow these steps:

1.  **Start the gateway server:**

    ```bash
    python start_server.py
    ```

2.  **Get the token URL:**

    Open your browser and navigate to `http://localhost:5000/api/token/url`. This will give you a url to follow which then creates you a token.

3.  **Login and get the token:**

    After logging in, you will be redirected to a page that displays your access token. Copy the token and set it as the `MLTF_GATEWAY_TOKEN` environment variable.

## Usage

To submit an MLflow project to the gateway, use the `mlflow run` command with the `gateway` backend:

```bash
mlflow run . --backend gateway
```

## Example

This example shows how to submit the MLflow project in the `demo` folder to the MLTF Gateway.

1.  **Start the gateway server:**

    ```bash
    python start_server.py
    ```

2.  **Set the environment variables:**

    ```bash
    export MLTF_GATEWAY_URI="http://localhost:5000"
    export MLTF_GATEWAY_TOKEN="your-access-token" # Replace with your token
    ```

3.  **Navigate to the demo folder:**

    ```bash
    cd demo
    ```

4.  **Submit the project:**

    ```bash
    mlflow run . --backend gateway
    ```

You should see output indicating that the project has been submitted to the gateway.
