#!/bin/bash
#
# MLOps Platform Observability Deployment Script
# This script deploys the observability components for the MLOps Platform
#
set -e

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print section header
section() {
    echo -e "\n${GREEN}==== $1 ====${NC}\n"
}

# Print info message
info() {
    echo -e "${YELLOW}INFO:${NC} $1"
}

# Print error message
error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    error "kubectl is not installed. Please install it first."
    exit 1
fi

# Check if namespace exists, create if not
check_create_namespace() {
    if ! kubectl get namespace monitoring &> /dev/null; then
        info "Creating monitoring namespace..."
        kubectl create namespace monitoring
    else
        info "Monitoring namespace already exists."
    fi
}

# Deploy components
deploy_otel() {
    section "Deploying OpenTelemetry Collector"
    kubectl apply -f kubernetes/monitoring/otel/otel-collector-config.yaml
    kubectl apply -f kubernetes/monitoring/otel/otel-collector.yaml
    info "OpenTelemetry Collector deployed."
}

deploy_prometheus() {
    section "Deploying Prometheus"
    kubectl apply -f kubernetes/monitoring/prometheus/prometheus-config.yaml
    kubectl apply -f kubernetes/monitoring/prometheus/prometheus.yaml
    kubectl apply -f kubernetes/monitoring/prometheus/alert-rules.yaml
    info "Prometheus deployed."
}

deploy_grafana() {
    section "Deploying Grafana"
    kubectl apply -f kubernetes/monitoring/grafana/grafana.yaml
    kubectl apply -f kubernetes/monitoring/grafana/dashboards.yaml
    
    # Create the dashboard directory in the Grafana persistent volume
    info "Creating dashboard directory in Grafana..."
    kubectl wait --for=condition=Ready pod -l app=grafana -n monitoring --timeout=60s
    kubectl exec -n monitoring deploy/grafana -- mkdir -p /var/lib/grafana/dashboards
    
    # Add the dashboard provider to Grafana
    kubectl cp kubernetes/monitoring/grafana/dashboards.yaml monitoring/$(kubectl get pods -n monitoring -l app=grafana -o jsonpath='{.items[0].metadata.name}'):/var/lib/grafana/provisioning/dashboards/
    
    info "Grafana deployed."
}

deploy_model_monitoring() {
    section "Deploying Model Monitoring"
    # Create directory if it doesn't exist
    mkdir -p kubernetes/monitoring/model-monitoring
    
    # Deploy model monitoring components
    kubectl apply -f kubernetes/monitoring/model-monitoring/drift-detector.yaml
    
    info "Model Monitoring deployed."
}

setup_port_forwarding() {
    section "Setting up port forwarding for local access"
    
    # Kill existing port-forward processes
    pkill -f "kubectl port-forward" || true
    
    # Setup port forwarding in the background
    kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
    kubectl port-forward -n monitoring svc/grafana 3000:3000 &
    kubectl port-forward -n monitoring svc/otel-collector 4317:4317 &
    
    info "Port forwarding set up. You can access:"
    info "Prometheus: http://localhost:9090"
    info "Grafana: http://localhost:3000 (default credentials: admin/admin)"
    info "OpenTelemetry Collector: localhost:4317 (OTLP gRPC)"
}

deploy_all() {
    check_create_namespace
    deploy_otel
    deploy_prometheus
    deploy_grafana
    deploy_model_monitoring
    setup_port_forwarding
    
    section "Deployment Complete"
    info "All observability components have been deployed."
    info "Note: For a production deployment, consider setting up proper ingress with TLS."
}

# Handle command line arguments
case "$1" in
    --otel)
        check_create_namespace
        deploy_otel
        ;;
    --prometheus)
        check_create_namespace
        deploy_prometheus
        ;;
    --grafana)
        check_create_namespace
        deploy_grafana
        ;;
    --model-monitoring)
        check_create_namespace
        deploy_model_monitoring
        ;;
    --port-forward)
        setup_port_forwarding
        ;;
    --help)
        echo "Usage: $0 [OPTION]"
        echo "Deploy the observability stack for the MLOps platform."
        echo ""
        echo "Options:"
        echo "  --otel            Deploy only OpenTelemetry Collector"
        echo "  --prometheus      Deploy only Prometheus"
        echo "  --grafana         Deploy only Grafana"
        echo "  --model-monitoring Deploy only Model Monitoring components"
        echo "  --port-forward    Setup port forwarding for local access"
        echo "  --help            Display this help message"
        echo ""
        echo "If no option is provided, all components will be deployed."
        ;;
    *)
        deploy_all
        ;;
esac 