# MLOps Platform Setup Guide

This guide provides instructions for setting up the MLOps platform infrastructure and core components.

## Prerequisites

Before you begin, ensure you have the following tools installed:

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

#### 5. Deploy Redis

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis bitnami/redis --namespace storage \
  --set architecture=replication \
  --set auth.enabled=true \
  --set auth.password=<your-password>
```

#### 6. Deploy MLflow

```bash
helm repo add larribas https://larribas.me/helm-charts
helm install mlflow larribas/mlflow --namespace mlflow \
  --set backendStore.postgres.enabled=true \
  --set backendStore.postgres.host=<db-endpoint> \
  --set backendStore.postgres.port=5432 \
  --set backendStore.postgres.database=mlops \
  --set backendStore.postgres.user=postgres \
  --set backendStore.postgres.password=<db-password> \
  --set artifactRoot.s3.enabled=true \
  --set artifactRoot.s3.bucket=<bucket-name> \
  --set artifactRoot.s3.region=<aws-region>
```

#### 7. Deploy Spark Operator

```bash
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm install spark-operator spark-operator/spark-operator --namespace spark \
  --set sparkJobNamespace=spark \
  --set webhook.enable=true
```

#### 8. Deploy Airflow

```bash
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow --namespace airflow \
  --set executor=KubernetesExecutor \
  --set postgresql.enabled=false \
  --set externalDatabase.host=<db-endpoint> \
  --set externalDatabase.port=5432 \
  --set externalDatabase.database=mlops \
  --set externalDatabase.user=postgres \
  --set externalDatabase.password=<db-password>
```

## Accessing Components

After deployment, you can access the various components using port-forwarding:

### MLflow UI

```bash
kubectl port-forward -n mlflow svc/mlflow 5000:5000
```

Access MLflow at http://localhost:5000

### Airflow UI

```bash
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080
```

Access Airflow at http://localhost:8080

### Kafka UI (if deployed)

```bash
kubectl port-forward -n kafka svc/kafka-ui 8080:8080
```

Access Kafka UI at http://localhost:8080

## Destroying Infrastructure

When you're done, you can destroy all AWS resources to avoid incurring charges:

```bash
cd terraform
terraform destroy
```

## Troubleshooting

### Common Issues

1. **EKS Cluster Creation Fails**: Check IAM permissions and VPC limits
2. **Helm Chart Installation Fails**: Check Kubernetes connectivity and namespace existence
3. **Database Connection Issues**: Verify security group configurations
4. **Missing Prerequisites**: Run the setup script which will detect and offer to install missing tools

For more help, see the project README or open an issue on the repository. 