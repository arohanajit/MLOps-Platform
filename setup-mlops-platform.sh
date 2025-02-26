#!/bin/bash
set -e

# MLOps Platform Setup Script
echo "===== MLOps Platform Setup ====="
echo "This script will set up the MLOps platform infrastructure and core components."

# Function to install prerequisites on macOS
install_prerequisites_mac() {
    echo "Installing prerequisites on macOS using Homebrew..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew is not installed. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install missing tools
    if ! command -v aws &> /dev/null; then
        echo "Installing AWS CLI..."
        brew install awscli
    fi
    
    if ! command -v terraform &> /dev/null; then
        echo "Installing Terraform..."
        brew install terraform
    fi
    
    if ! command -v kubectl &> /dev/null; then
        echo "Installing kubectl..."
        brew install kubectl
    fi
    
    if ! command -v helm &> /dev/null; then
        echo "Installing Helm..."
        brew install helm
    fi
    
    echo "Prerequisites installation completed."
}

# Check prerequisites with installation option
check_and_install_prerequisites() {
    local missing_tools=()
    
    # Check for required tools
    command -v aws &> /dev/null || missing_tools+=("AWS CLI")
    command -v terraform &> /dev/null || missing_tools+=("Terraform")
    command -v kubectl &> /dev/null || missing_tools+=("kubectl")
    command -v helm &> /dev/null || missing_tools+=("Helm")
    
    # If tools are missing, offer to install them
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo "The following required tools are missing:"
        for tool in "${missing_tools[@]}"; do
            echo "- $tool"
        done
        
        # Detect OS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            read -p "Would you like to install these tools using Homebrew? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                install_prerequisites_mac
            else
                echo "Please install the missing tools manually and run this script again."
                echo "Installation instructions:"
                echo "- AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
                echo "- Terraform: https://developer.hashicorp.com/terraform/install"
                echo "- kubectl: https://kubernetes.io/docs/tasks/tools/"
                echo "- Helm: https://helm.sh/docs/intro/install/"
                exit 1
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Please install the missing tools using your distribution's package manager."
            echo "Installation instructions:"
            echo "- AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
            echo "- Terraform: https://developer.hashicorp.com/terraform/install"
            echo "- kubectl: https://kubernetes.io/docs/tasks/tools/"
            echo "- Helm: https://helm.sh/docs/intro/install/"
            exit 1
        else
            echo "Your operating system is not directly supported by this script."
            echo "Please install the missing tools manually following the documentation."
            exit 1
        fi
        
        # Verify tools were installed successfully
        for tool in "${missing_tools[@]}"; do
            tool_cmd=$(echo "$tool" | tr '[:upper:]' '[:lower:]' | tr -d ' ')
            if ! command -v "$tool_cmd" &> /dev/null; then
                echo "Failed to install $tool. Please install it manually."
                exit 1
            fi
        done
    fi
    
    echo "All prerequisites are installed."
}

# Check AWS configuration
check_aws_configuration() {
    echo "Checking AWS configuration..."
    if ! aws sts get-caller-identity &> /dev/null; then
        echo "AWS credentials are not configured or are invalid."
        echo "Please run 'aws configure' to set up your AWS credentials."
        exit 1
    else
        echo "AWS credentials are valid."
    fi
}

# Check and install prerequisites
echo "Checking prerequisites..."
check_and_install_prerequisites

# Check AWS configuration
check_aws_configuration

# Ask for confirmation
read -p "This will provision AWS resources that may incur costs. Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup canceled."
    exit 1
fi

# Phase 1: Infrastructure Setup
echo
echo "Phase 1: Setting up cloud infrastructure..."

# Initialize Terraform
echo "Initializing Terraform..."
cd terraform
terraform init

# Apply Terraform configuration
echo "Provisioning AWS infrastructure..."
terraform apply -auto-approve || {
    echo "Terraform apply failed. Check the error messages above."
    exit 1
}

# Get Terraform outputs
echo "Retrieving infrastructure details..."
db_endpoint=$(terraform output -raw db_endpoint 2>/dev/null || echo "localhost")
redis_endpoint=$(terraform output -raw redis_endpoint 2>/dev/null || echo "localhost")
artifact_bucket=$(terraform output -raw artifact_bucket_name 2>/dev/null || echo "mlops-artifacts")
aws_region=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")

# Configure kubectl to use the new cluster
echo "Configuring kubectl..."
aws eks update-kubeconfig --region "$aws_region" --name $(terraform output -raw cluster_name) || {
    echo "Failed to configure kubectl. Ensure the EKS cluster was created successfully."
    exit 1
}

# Return to root directory
cd ..

# Phase 1.2: Deploy Core Kubernetes Components
echo
echo "Deploying core Kubernetes components..."

# Apply namespaces
echo "Creating Kubernetes namespaces..."
kubectl apply -f kubernetes/namespaces.yaml || {
    echo "Failed to create Kubernetes namespaces. Check if kubectl is configured correctly."
    exit 1
}

# Deploy Kafka with Strimzi operator
echo "Deploying Kafka..."
kubectl apply -f kubernetes/kafka/strimzi-operator.yaml
sleep 30  # Wait for the operator to start
kubectl apply -f kubernetes/kafka/kafka-cluster.yaml
kubectl apply -f kubernetes/kafka/schema-registry.yaml

# Deploy Redis in Kubernetes (as a backup/complement to AWS ElastiCache)
echo "Deploying Redis in Kubernetes..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis-k8s bitnami/redis --namespace storage \
  --set architecture=standalone \
  --set auth.enabled=true \
  --set auth.password=mlops-redis-password

# Deploy PostgreSQL (as a backup/complement to RDS)
echo "Deploying PostgreSQL in Kubernetes..."
helm install postgresql-k8s bitnami/postgresql --namespace storage \
  --set auth.postgresPassword=mlops-postgres-password \
  --set auth.database=mlops

# Deploy MLflow
echo "Deploying MLflow..."
helm repo add larribas https://larribas.me/helm-charts
helm install mlflow larribas/mlflow --namespace mlflow \
  --set backendStore.postgres.enabled=true \
  --set backendStore.postgres.host="$db_endpoint" \
  --set backendStore.postgres.port=5432 \
  --set backendStore.postgres.database=mlops \
  --set backendStore.postgres.user=postgres \
  --set backendStore.postgres.password="mlops-postgres-password" \
  --set artifactRoot.s3.enabled=true \
  --set artifactRoot.s3.bucket="$artifact_bucket" \
  --set artifactRoot.s3.region="$aws_region"

# Deploy Spark (Spark Operator)
echo "Deploying Spark Operator..."
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm install spark-operator spark-operator/spark-operator --namespace spark \
  --set sparkJobNamespace=spark \
  --set webhook.enable=true

# Deploy Airflow (using Helm chart)
echo "Deploying Airflow..."
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow --namespace airflow \
  --set executor=KubernetesExecutor \
  --set postgresql.enabled=false \
  --set externalDatabase.host="$db_endpoint" \
  --set externalDatabase.port=5432 \
  --set externalDatabase.database=mlops \
  --set externalDatabase.user=postgres \
  --set externalDatabase.password="mlops-postgres-password"

# Wait for deployments to be ready
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available deployment -l app.kubernetes.io/name=mlflow --namespace mlflow --timeout=300s || echo "MLflow deployment not yet ready"
kubectl wait --for=condition=available deployment -l app.kubernetes.io/name=airflow-webserver --namespace airflow --timeout=300s || echo "Airflow deployment not yet ready"

echo
echo "MLOps Platform setup completed!"
echo "Use kubectl and Helm to manage your platform."
echo "See docs/ directory for usage instructions." 