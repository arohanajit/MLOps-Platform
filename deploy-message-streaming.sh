#!/bin/bash
set -e

# Message Streaming Infrastructure Deployment Script
echo "===== Message Streaming Infrastructure Setup ====="
echo "This script will deploy Kafka, Schema Registry, and Debezium CDC connectors."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in the PATH"
    exit 1
fi

# Check if we can connect to Kubernetes
if ! kubectl get nodes &> /dev/null; then
    echo "Error: Cannot connect to Kubernetes cluster. Make sure your kubeconfig is set up correctly."
    exit 1
fi

# Deploy Strimzi Kafka Operator
echo "Deploying Strimzi Kafka Operator..."
kubectl apply -f kubernetes/kafka/strimzi-operator.yaml
echo "Waiting for Strimzi Operator to be ready..."
kubectl -n kafka wait --for=condition=ready pod -l name=strimzi-cluster-operator --timeout=300s || {
    echo "Strimzi Operator did not become ready in time. Check the logs for more information."
    kubectl -n kafka logs -l name=strimzi-cluster-operator
    exit 1
}

# Deploy Kafka cluster (single-broker, resource-constrained configuration)
echo "Deploying Kafka cluster (single-broker configuration)..."
kubectl apply -f kubernetes/kafka/kafka-cluster.yaml
echo "Waiting for Kafka to be ready... (this may take a few minutes)"
kubectl -n kafka wait --for=condition=ready pod -l strimzi.io/name=mlops-kafka-kafka --timeout=600s || {
    echo "Kafka did not become ready in time. Check the logs for more information."
    kubectl -n kafka logs -l strimzi.io/name=mlops-kafka-kafka
    echo "Continuing anyway, as some pods might still be initializing..."
}

# Deploy Schema Registry
echo "Deploying Schema Registry..."
kubectl apply -f kubernetes/kafka/schema-registry.yaml
echo "Waiting for Schema Registry to be ready..."
kubectl -n kafka wait --for=condition=ready pod -l app=schema-registry --timeout=300s || {
    echo "Schema Registry did not become ready in time. Check the logs for more information."
    kubectl -n kafka logs -l app=schema-registry
    exit 1
}

# Create environment variables configmap
echo "Creating environment configuration..."
kubectl apply -f kubernetes/kafka/env-config.yaml

# Create PostgreSQL credentials secret
echo "Creating PostgreSQL credentials secret..."
kubectl apply -f kubernetes/kafka/postgres-credentials.yaml

# Deploy Kafka Connect
echo "Deploying Kafka Connect..."
kubectl apply -f kubernetes/kafka/kafka-connect.yaml
echo "Waiting for Kafka Connect to be ready..."
kubectl -n kafka wait --for=condition=ready pod -l strimzi.io/name=kafka-connect --timeout=300s || {
    echo "Kafka Connect did not become ready in time. Check the logs for more information."
    kubectl -n kafka logs -l strimzi.io/name=kafka-connect
    exit 1
}

# Deploy Debezium connector
echo "Deploying Debezium PostgreSQL connector..."
kubectl apply -f kubernetes/kafka/debezium-connector.yaml

echo
echo "Message streaming infrastructure has been successfully deployed!"
echo
echo "To check the status of the Kafka cluster:"
echo "  kubectl -n kafka get pods -l strimzi.io/cluster=mlops-kafka"
echo
echo "To check the status of the Schema Registry:"
echo "  kubectl -n kafka get pods -l app=schema-registry"
echo
echo "To check the status of Kafka Connect and the Debezium connector:"
echo "  kubectl -n kafka get pods -l strimzi.io/name=kafka-connect"
echo "  kubectl -n kafka get kafkaconnector -l strimzi.io/cluster=kafka-connect"
echo
echo "NOTE: You may need to modify the PostgreSQL hostname in env-config.yaml with your actual RDS endpoint" 