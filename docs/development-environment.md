# Development Environment Setup Guide

This guide explains how to set up your local development environment for the MLOps platform.

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker**: [Installation Guide](https://docs.docker.com/get-docker/)
- **kubectl**: [Installation Guide](https://kubernetes.io/docs/tasks/tools/)
- **k3d** (for local Kubernetes): [Installation Guide](https://k3d.io/#installation)
- **Python 3.9+**: [Installation Guide](https://www.python.org/downloads/)
- **Git**: [Installation Guide](https://git-scm.com/downloads)

## Setup Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/MLOps-Platform.git
cd MLOps-Platform
```

### 2. Set Up Python Virtual Environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Linux/macOS
source .venv/bin/activate
# On Windows
# .venv\Scripts\activate

# Install dependencies
pip install -r src/tests/requirements.txt
```

### 3. Set Up Local Kubernetes Cluster with k3d

```bash
# Create a local Kubernetes cluster with k3d
k3d cluster create mlops-dev --servers 1 --agents 2 --port "8080:80@loadbalancer" --api-port 6550

# Verify the cluster is running
kubectl get nodes
```

### 4. Deploy Core Components Locally

```bash
# Run the setup script with the local flag
./setup-mlops-platform.sh --local

# Wait for all components to be ready
kubectl get pods -A
```

### 5. Local Data Store Setup

For local development, we use lightweight alternatives to AWS services:

- **MinIO** instead of S3 for object storage
- **LocalStack** for AWS service emulation (if needed)

Run the local storage services:

```bash
docker-compose -f docker-compose-dev.yml up -d
```

### 6. Set Up IDE

We recommend using one of the following IDEs:

- **VS Code**: Install the Python, Docker, and Kubernetes extensions
- **PyCharm**: Configure the Python interpreter to use your virtual environment

### 7. Configure Environment Variables

Create a `.env.dev` file based on the example provided:

```bash
cp .env.example .env.dev
```

Edit `.env.dev` with your local configuration.

To load the environment variables:

```bash
export $(grep -v '^#' .env.dev | xargs)
```

### 8. Run Tests Locally

Ensure all tests pass in your local environment:

```bash
python src/tests/run_all_tests.py --verbose
```

## Development Workflow

### Running Components Individually

For faster development cycles, you can run individual components outside the cluster:

#### Feature Engineering API

```bash
cd src/feature_engineering
python api.py --dev
```

#### Model Serving API

```bash
cd src/model_serving
python serving_api.py --dev
```

### Making Changes

1. Create a new feature branch from `develop`
2. Make your changes
3. Run tests locally
4. Submit a pull request

### Testing with Real Data

To test with real data instead of generated test data:

1. Add your test data to the `data/` directory
2. Run the specific processor:

```bash
python src/processing/process_data.py --source-path data/mydata.csv
```

## Troubleshooting

### Common Issues

#### Pod Status Shows 'CrashLoopBackOff'

Check the pod logs:

```bash
kubectl logs <pod-name> -n <namespace>
```

#### Cannot Connect to Services

Ensure port forwarding is active:

```bash
kubectl port-forward svc/<service-name> <local-port>:<service-port> -n <namespace>
```

#### Dependency Issues

Ensure your virtual environment is activated and dependencies are up to date:

```bash
pip install -r src/tests/requirements.txt
```

## Additional Resources

- [Project Documentation](./README.md)
- [Git Workflow Guide](./git-workflow.md)
- [API Documentation](./api-docs.md)
- [Kubernetes Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/) 