#!/bin/bash
set -e

# MLOps Platform Installation Verification Script
echo "===== MLOps Platform Verification ====="
echo "This script will check the status of all MLOps platform components."

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo "kubectl is required but not installed. Aborting."
    exit 1
fi

# Check if AWS CLI is available for checking AWS resources
if command -v aws &> /dev/null; then
    AWS_CLI_AVAILABLE=true
    echo "AWS CLI available, will check AWS resources too."
else
    AWS_CLI_AVAILABLE=false
    echo "AWS CLI not available, will only check Kubernetes resources."
fi

# Get Terraform output if available
if [ -d "terraform" ]; then
    echo "Reading Terraform outputs..."
    cd terraform
    REDIS_ENDPOINT=$(terraform output -raw redis_endpoint 2>/dev/null || echo "not-available")
    DB_ENDPOINT=$(terraform output -raw db_endpoint 2>/dev/null || echo "not-available")
    AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")
    cd ..
    
    echo "Redis Endpoint from Terraform: $REDIS_ENDPOINT"
    echo "Database Endpoint from Terraform: $DB_ENDPOINT"
else
    REDIS_ENDPOINT="not-available"
    DB_ENDPOINT="not-available"
    AWS_REGION="us-east-1"
    echo "Terraform directory not found, cannot get endpoints from Terraform."
fi

echo -e "\nChecking Kubernetes components..."

# Check namespaces
echo -e "\n=== Namespaces ==="
kubectl get namespaces | grep -E 'kafka|storage|mlflow|spark|airflow|model-serving|monitoring' || echo "No matching namespaces found"

# Check Kafka components
echo -e "\n=== Kafka Components ==="
kubectl get pods -n kafka 2>/dev/null || echo "No Kafka pods found"

# Check if Kafka cluster is running
if kubectl get kafkas -n kafka &> /dev/null; then
    echo -e "\n=== Kafka Clusters ==="
    kubectl get kafkas -n kafka
else
    echo "Kafka custom resource not found. Strimzi operator may not be installed."
fi

# Check Schema Registry
echo -e "\n=== Schema Registry ==="
kubectl get pods -n kafka -l app=schema-registry 2>/dev/null || echo "No Schema Registry pods found"

# Check Redis in Kubernetes
echo -e "\n=== Redis in Kubernetes ==="
kubectl get pods -n storage -l app.kubernetes.io/name=redis-k8s 2>/dev/null || \
kubectl get pods -n storage -l app.kubernetes.io/instance=redis-k8s 2>/dev/null || \
echo "No Redis pods found"

# Get Redis password from Secret if it exists
REDIS_K8S_PASSWORD=$(kubectl get secret -n storage redis-k8s -o jsonpath="{.data.redis-password}" 2>/dev/null | base64 --decode || echo "not-available")
if [ "$REDIS_K8S_PASSWORD" != "not-available" ]; then
    echo "Redis K8s Password is available (not shown for security)"
else
    echo "Redis K8s Password not available"
fi

# Check PostgreSQL in Kubernetes
echo -e "\n=== PostgreSQL in Kubernetes ==="
kubectl get pods -n storage -l app.kubernetes.io/name=postgresql-k8s 2>/dev/null || \
kubectl get pods -n storage -l app.kubernetes.io/instance=postgresql-k8s 2>/dev/null || \
echo "No PostgreSQL pods found"

# Get PostgreSQL password from Secret if it exists
PG_K8S_PASSWORD=$(kubectl get secret -n storage postgresql-k8s -o jsonpath="{.data.postgres-password}" 2>/dev/null | base64 --decode || echo "not-available")
if [ "$PG_K8S_PASSWORD" != "not-available" ]; then
    echo "PostgreSQL K8s Password is available (not shown for security)"
else
    echo "PostgreSQL K8s Password not available"
fi

# Check MLflow
echo -e "\n=== MLflow ==="
kubectl get pods -n mlflow 2>/dev/null || echo "No MLflow pods found"

# Check Spark Operator
echo -e "\n=== Spark Operator ==="
kubectl get pods -n spark -l app.kubernetes.io/name=spark-operator 2>/dev/null || echo "No Spark Operator pods found"

# Check Airflow
echo -e "\n=== Airflow ==="
kubectl get pods -n airflow 2>/dev/null || echo "No Airflow pods found"

# Get services
echo -e "\n=== Services ==="
echo "MLflow:"
kubectl get svc -n mlflow 2>/dev/null || echo "No MLflow services found"
echo -e "\nAirflow:"
kubectl get svc -n airflow 2>/dev/null || echo "No Airflow services found"
echo -e "\nKafka:"
kubectl get svc -n kafka 2>/dev/null || echo "No Kafka services found"

# Check AWS resources if AWS CLI is available
if [ "$AWS_CLI_AVAILABLE" = true ]; then
    echo -e "\n===== AWS Resources ====="
    
    # Check RDS instances
    echo -e "\n=== RDS Instances ==="
    aws rds describe-db-instances --query "DBInstances[?contains(DBInstanceIdentifier, 'mlops')].{ID:DBInstanceIdentifier,Status:DBInstanceStatus,Endpoint:Endpoint.Address}" --output table --region $AWS_REGION 2>/dev/null || echo "No RDS instances found or error accessing them."
    
    # Check ElastiCache clusters
    echo -e "\n=== ElastiCache Clusters ==="
    aws elasticache describe-cache-clusters --query "CacheClusters[?contains(CacheClusterId, 'mlops')].{ID:CacheClusterId,Status:CacheClusterStatus,Endpoint:CacheNodes[0].Endpoint.Address}" --output table --region $AWS_REGION 2>/dev/null || echo "No ElastiCache clusters found or error accessing them."
    
    # Check EKS clusters
    echo -e "\n=== EKS Clusters ==="
    aws eks list-clusters --query "clusters[?contains(@, 'mlops')]" --output table --region $AWS_REGION 2>/dev/null || echo "No EKS clusters found or error accessing them."
    
    # Check S3 buckets
    echo -e "\n=== S3 Buckets ==="
    aws s3 ls 2>/dev/null | grep "mlops" || echo "No S3 buckets found with 'mlops' in the name."
fi

# Verify connectivity to Redis
echo -e "\n===== Connectivity Tests ====="
if [ "$REDIS_ENDPOINT" != "not-available" ]; then
    echo -e "\n=== Testing Redis Connection ==="
    # Extract host and port from endpoint
    REDIS_HOST=$(echo $REDIS_ENDPOINT | cut -d':' -f1)
    REDIS_PORT=$(echo $REDIS_ENDPOINT | cut -d':' -f2)
    
    # Try to connect to Redis using nc command if available
    if command -v nc &> /dev/null; then
        echo "Testing TCP connectivity to Redis at $REDIS_HOST:$REDIS_PORT"
        nc -zv $REDIS_HOST $REDIS_PORT -w 5 2>&1 || echo "Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
    else
        echo "nc command not available, skipping Redis connectivity test"
    fi
fi

# Verify connectivity to PostgreSQL
if [ "$DB_ENDPOINT" != "not-available" ]; then
    echo -e "\n=== Testing PostgreSQL Connection ==="
    # Extract host and port from endpoint
    DB_HOST=$(echo $DB_ENDPOINT | cut -d':' -f1)
    DB_PORT=$(echo $DB_ENDPOINT | cut -d':' -f2)
    
    # Try to connect to PostgreSQL using nc command if available
    if command -v nc &> /dev/null; then
        echo "Testing TCP connectivity to PostgreSQL at $DB_HOST:$DB_PORT"
        nc -zv $DB_HOST $DB_PORT -w 5 2>&1 || echo "Cannot connect to PostgreSQL at $DB_HOST:$DB_PORT"
    else
        echo "nc command not available, skipping PostgreSQL connectivity test"
    fi
fi

# Display access information
echo -e "\n===== Access Information ====="
echo "To access MLflow UI:"
echo "kubectl port-forward -n mlflow svc/mlflow 5000:5000"
echo "Then open http://localhost:5000"
echo
echo "To access Airflow UI:"
echo "kubectl port-forward -n airflow svc/airflow-webserver 8080:8080"
echo "Then open http://localhost:8080"
echo

# Overall status
echo -e "\n===== Verification Complete ====="
echo "If all components are in the 'Running' state, your MLOps platform is correctly installed."
echo "If any components are missing or in a non-Running state, please check the logs for errors:"
echo "kubectl logs -n <namespace> <pod-name>" 