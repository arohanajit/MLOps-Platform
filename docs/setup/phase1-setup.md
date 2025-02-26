# Phase 1: Infrastructure and Core Components Setup

This guide walks through setting up the cloud infrastructure and core platform components for the MLOps platform.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- kubectl
- Helm
- Docker

## Step 1: Deploy Cloud Infrastructure

1. Initialize the Terraform configuration:

```bash
cd terraform
terraform init
```

2. Review and update configuration variables if needed:

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your specific values
```

3. Preview the infrastructure changes:

```bash
terraform plan
```

4. Deploy the infrastructure:

```bash
terraform apply
```

5. Configure kubectl to connect to the EKS cluster:

```bash
aws eks update-kubeconfig --region <your-region> --name mlops-platform
```

## Step 2: Install Core Components

### Create Namespaces

```bash
kubectl apply -f kubernetes/namespaces.yaml
```

### Deploy Kafka and Schema Registry

1. Deploy Strimzi Kafka Operator:

```bash
kubectl apply -f kubernetes/kafka/strimzi-operator.yaml
```

2. Deploy Kafka cluster:

```bash
kubectl apply -f kubernetes/kafka/kafka-cluster.yaml
```

3. Deploy Schema Registry:

```bash
kubectl apply -f kubernetes/kafka/schema-registry.yaml
```

4. Verify the deployment:

```bash
kubectl get pods -n kafka
```

### Deploy Storage Services (PostgreSQL and Redis)

1. Deploy PostgreSQL:

```bash
kubectl apply -f kubernetes/storage/postgres.yaml
```

2. Deploy Redis:

```bash
kubectl apply -f kubernetes/storage/redis.yaml
```

3. Verify the storage services:

```bash
kubectl get pods -n storage
```

### Deploy MLflow

1. Update MLflow secrets (replace placeholders with actual values):

```bash
# Edit kubernetes/mlflow/mlflow.yaml
```

2. Deploy MLflow:

```bash
kubectl apply -f kubernetes/mlflow/mlflow.yaml
```

3. Verify MLflow deployment:

```bash
kubectl get pods -n mlflow
```

### Deploy Spark Operator

1. Deploy Spark Operator:

```bash
kubectl apply -f kubernetes/spark/spark-operator.yaml
```

2. Verify Spark operator:

```bash
kubectl get pods -n spark
```

### Deploy Airflow

1. Update Airflow configuration (if needed):

```bash
# Edit kubernetes/airflow/values.yaml
```

2. Deploy Airflow using Helm:

```bash
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm install airflow apache-airflow/airflow -n airflow -f kubernetes/airflow/values.yaml
```

3. Verify Airflow deployment:

```bash
kubectl get pods -n airflow
```

## Step 3: Test The Setup

### Verify Kafka

1. Create a test topic:

```bash
kubectl -n kafka run kafka-producer -ti --image=quay.io/strimzi/kafka:0.35.0-kafka-3.4.0 --rm=true --restart=Never -- bin/kafka-console-producer.sh --bootstrap-server mlops-kafka-kafka-bootstrap:9092 --topic test
```

2. Send a test message in the producer terminal.

3. Start a consumer in a new terminal:

```bash
kubectl -n kafka run kafka-consumer -ti --image=quay.io/strimzi/kafka:0.35.0-kafka-3.4.0 --rm=true --restart=Never -- bin/kafka-console-consumer.sh --bootstrap-server mlops-kafka-kafka-bootstrap:9092 --topic test --from-beginning
```

### Verify PostgreSQL

```bash
kubectl -n storage exec -it postgres-0 -- psql -U postgres -c "SELECT 1;"
```

### Verify Redis

```bash
kubectl -n storage exec -it redis-0 -- redis-cli ping
```

### Verify MLflow

```bash
kubectl port-forward -n mlflow svc/mlflow 5000:5000
```

Visit http://localhost:5000 in your browser.

### Verify Airflow

```bash
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080
```

Visit http://localhost:8080 in your browser (default credentials: admin/admin).

## Next Steps

After successfully setting up the infrastructure and core components, proceed to Phase 2: Data Pipeline Implementation. 