# MLOps Platform Setup Guide

This guide provides instructions for setting up the MLOps platform infrastructure and core components.

## Local Development Setup

For local development and testing, we've created a consolidated management script that makes it easy to work with the platform:

1. Clone the repository:
```bash
git clone https://github.com/yourusername/MLOps-Platform.git
cd MLOps-Platform
```

2. Make the management script executable:
```bash
chmod +x mlops-platform.sh
```

3. Verify installation requirements:
```bash
./mlops-platform.sh verify
```

4. Start the platform:
```bash
./mlops-platform.sh start
```

5. Check service status:
```bash
./mlops-platform.sh status
```

Available commands:
- `start` - Start the MLOps platform
- `stop` - Stop the MLOps platform 
- `restart` - Restart the MLOps platform
- `status` - Check status of all services
- `logs [service]` - Show logs for a specific service or all services
- `test` - Run tests against the platform
- `verify` - Verify platform installation
- `clean` - Remove all containers and volumes
- `help` - Show help message

## Cloud Infrastructure Prerequisites

Before you begin setting up the platform in a cloud environment, ensure you have the following tools installed:

- AWS CLI (configured with appropriate credentials)
- Terraform (v1.0 or higher)
- kubectl
- Helm (v3.x)

### Installing Prerequisites

The setup script can automatically install prerequisites on macOS using Homebrew. For other systems, follow these instructions:

#### macOS

Using Homebrew:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install awscli terraform kubectl helm
```

#### Linux (Ubuntu/Debian)

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Terraform
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform

# Install kubectl
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/kubernetes-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update && sudo apt-get install -y kubectl

# Install Helm
curl https://baltocdn.com/helm/signing.asc | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update && sudo apt-get install helm
```

#### AWS Configuration

After installing the AWS CLI, configure it with your credentials:

```bash
aws configure
```

You'll need to provide:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-west-2)
- Default output format (json is recommended)

## Phase 1: Infrastructure Setup

### Option 1: Automated Setup

The easiest way to set up the entire platform is to use the provided setup script:

```bash
./setup-mlops-platform.sh
```

This script will:
1. Check for required tools and offer to install missing prerequisites (on macOS)
2. Deploy AWS infrastructure using Terraform
3. Configure kubectl to work with the EKS cluster
4. Deploy all core Kubernetes components

### Option 2: Manual Setup

If you prefer to set up components individually, follow these steps:

#### 1. Provision AWS Infrastructure

```bash
cd terraform
terraform init
terraform apply
```

Take note of the outputs, which include database endpoints, storage bucket names, etc.

#### 2. Configure kubectl

```bash
aws eks update-kubeconfig --region <aws-region> --name <cluster-name>
```

#### 3. Create Kubernetes Namespaces

```bash
kubectl apply -f kubernetes/namespaces.yaml
```

#### 4. Deploy Kafka and Schema Registry

```bash
kubectl apply -f kubernetes/kafka/strimzi-operator.yaml
# Wait for the operator to start
kubectl apply -f kubernetes/kafka/kafka-cluster.yaml
kubectl apply -f kubernetes/kafka/schema-registry.yaml
```