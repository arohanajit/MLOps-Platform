#!/bin/bash
set -e

# Storage Layer Deployment Script
echo "===== Storage Layer Infrastructure Setup ====="
echo "This script will deploy Redis, configure PostgreSQL schemas, and set up materialization between stores."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in the PATH"
    exit 1
fi

# Check AWS CLI for S3 access
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed or not in the PATH"
    exit 1
fi

# Check if we can connect to Kubernetes
if ! kubectl get nodes &> /dev/null; then
    echo "Error: Cannot connect to Kubernetes cluster. Make sure your kubeconfig is set up correctly."
    exit 1
fi

# Create storage namespace if it doesn't exist
echo "Creating storage namespace..."
kubectl create namespace storage --dry-run=client -o yaml | kubectl apply -f -

# Copy initialize_schemas.sql to the correct location for configmap
echo "Preparing database initialization scripts..."
mkdir -p tmp
cp src/storage/initialize_schemas.sql tmp/

# Apply storage configurations
echo "Deploying Redis (Online Store)..."
kubectl apply -f kubernetes/storage/redis.yaml
echo "Waiting for Redis to be ready..."
kubectl -n storage wait --for=condition=ready pod -l app=redis --timeout=300s || {
    echo "Redis did not become ready in time. Check the logs for more information."
    kubectl -n storage logs -l app=redis
    exit 1
}

# Create a configmap for the schema initialization script
echo "Creating ConfigMap for PostgreSQL schema initialization..."
kubectl -n storage create configmap postgres-schemas --from-file=initialize_schemas.sql=tmp/initialize_schemas.sql --dry-run=client -o yaml | kubectl apply -f -

# Prompt for RDS endpoint
echo
echo "Enter your AWS RDS PostgreSQL endpoint (e.g., mlops-postgres-dev.abc123.us-east-1.rds.amazonaws.com):"
read -r POSTGRES_ENDPOINT

# Create or update storage-config configmap
echo "Updating configuration with RDS endpoint..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: storage-config
  namespace: storage
data:
  postgres_host: "${POSTGRES_ENDPOINT}"
  s3_bucket: "$(cd terraform && terraform output -raw artifact_bucket_name 2>/dev/null || echo 'mlops-artifacts-dev')"
  region: "$(cd terraform && terraform output -raw aws_region 2>/dev/null || echo 'us-east-1')"
EOF

# Execute the schema initialization script on RDS
echo "Initializing PostgreSQL schemas on RDS..."
kubectl -n storage create job --from=cronjob/data-retention-cleanup schema-init-job --dry-run=client -o yaml | 
  sed 's|SELECT cleanup_old_feature_values();|\\i /tmp/initialize_schemas.sql|' |
  kubectl apply -f -

# Wait for schema initialization job
echo "Waiting for schema initialization to complete..."
kubectl -n storage wait --for=condition=complete job/schema-init-job --timeout=60s || {
    echo "Schema initialization did not complete in time. Check the logs for more information."
    kubectl -n storage logs job/schema-init-job
    exit 1
}

# Deploy materialization job
echo "Deploying materialization job..."
kubectl apply -f kubernetes/storage/materialization-job.yaml

# Deploy data retention cronjob
echo "Setting up data retention policies..."
kubectl apply -f kubernetes/storage/materialization-job.yaml

# Clean up temporary files
rm -rf tmp

echo
echo "Storage layer has been successfully deployed!"
echo
echo "To check the status of Redis:"
echo "  kubectl -n storage get pods -l app=redis"
echo
echo "To check the materialization job:"
echo "  kubectl -n storage get pods -l app=materialization-job"
echo
echo "To check the data retention cronjob:"
echo "  kubectl -n storage get cronjobs"
echo
echo "Your PostgreSQL offline store is available at: ${POSTGRES_ENDPOINT}"
echo "Your Redis online store is available at: redis.storage.svc.cluster.local:6379"
echo
echo "NOTE: If you're not using an AWS RDS instance, you need to adjust the scripts accordingly." 