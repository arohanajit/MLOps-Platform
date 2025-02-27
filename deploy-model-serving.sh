#!/bin/bash
# Model Serving Infrastructure Deployment Script
# This script deploys the model serving components to a Kubernetes cluster

set -e

echo "========================================================"
echo "MLOps Platform - Model Serving Infrastructure Deployment"
echo "========================================================"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed. Please install kubectl and try again."
    exit 1
fi

# Check if connected to a cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "Error: Not connected to a Kubernetes cluster. Please configure kubectl to connect to your cluster and try again."
    exit 1
fi

# Create namespaces if they don't exist
echo "Creating namespaces..."
kubectl apply -f kubernetes/namespaces.yaml

# Create model-serving directory if it doesn't exist
if [ ! -d "kubernetes/model-serving" ]; then
    echo "Creating kubernetes/model-serving directory..."
    mkdir -p kubernetes/model-serving
fi

# Deploy NGINX API Gateway
echo "Deploying NGINX API Gateway..."
kubectl apply -f kubernetes/model-serving/nginx-deployment.yaml

# Deploy RayServe Model Serving
echo "Deploying Model Serving Configuration..."
kubectl apply -f kubernetes/model-serving/model-serving-config.yaml

echo "Deploying RayServe Default Model..."
kubectl apply -f kubernetes/model-serving/rayserve-deployment.yaml

# Optional: Deploy Model B for A/B testing if it exists
if [ -f "kubernetes/model-serving/rayserve-model-b-deployment.yaml" ]; then
    echo "Deploying RayServe Model B for A/B testing..."
    kubectl apply -f kubernetes/model-serving/rayserve-model-b-deployment.yaml
fi

# Wait for deployments to be ready
echo "Waiting for NGINX deployment to be ready..."
kubectl -n model-serving rollout status deployment/nginx

echo "Waiting for RayServe deployment to be ready..."
kubectl -n model-serving rollout status deployment/rayserve

# Check if Model B is deployed
if kubectl -n model-serving get deployment rayserve-model-b &> /dev/null; then
    echo "Waiting for RayServe Model B deployment to be ready..."
    kubectl -n model-serving rollout status deployment/rayserve-model-b
fi

# Get service information
echo ""
echo "Model Serving Infrastructure deployed successfully!"
echo ""
echo "Service Information:"
kubectl -n model-serving get services

# Check if LoadBalancer has an external IP
EXTERNAL_IP=$(kubectl -n model-serving get service nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [ -z "$EXTERNAL_IP" ]; then
    EXTERNAL_IP=$(kubectl -n model-serving get service nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
fi

if [ -n "$EXTERNAL_IP" ]; then
    echo ""
    echo "Model Serving API is accessible at: http://$EXTERNAL_IP"
    echo "API Documentation: http://$EXTERNAL_IP/"
    echo "Prediction Endpoint: http://$EXTERNAL_IP/api/v1/predictions"
else
    echo ""
    echo "No external IP assigned yet. For local access, you can use port-forwarding:"
    echo "kubectl -n model-serving port-forward svc/nginx 8080:80"
    echo "Then access the API at: http://localhost:8080"
fi

echo ""
echo "To test the API with the demo client, run:"
echo "cd src/model_serving && python demo_client.py"
echo ""
echo "For production deployment, consider using AWS Lambda for serverless model serving."
echo "========================================================" 