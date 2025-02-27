#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   MLOps Platform Debugging Assistant    ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed.${NC}"
    echo "Please install kubectl first."
    exit 1
fi

# Function to check if a namespace exists
check_namespace() {
    kubectl get namespace "$1" &> /dev/null
    return $?
}

# Function to print section headers
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check component status
check_component() {
    local namespace="$1"
    local component="$2"
    local description="$3"
    
    if ! check_namespace "$namespace"; then
        echo -e "${RED}Namespace '$namespace' does not exist.${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Checking $description in namespace '$namespace'...${NC}"
    
    # Check if any pods exist for this component
    if ! kubectl get pods -n "$namespace" -l "app=$component" 2>/dev/null | grep -q .; then
        echo -e "${RED}No pods found for $description.${NC}"
        return 1
    fi
    
    # Check for pods in CrashLoopBackOff or Error state
    local problem_pods=$(kubectl get pods -n "$namespace" -l "app=$component" --no-headers 2>/dev/null | grep -E 'CrashLoopBackOff|Error|ImagePullBackOff|ErrImagePull' || true)
    if [ -n "$problem_pods" ]; then
        echo -e "${RED}Problems found with $description pods:${NC}"
        echo "$problem_pods"
        return 1
    fi
    
    # Check for pods not in Running state
    local not_running=$(kubectl get pods -n "$namespace" -l "app=$component" --no-headers 2>/dev/null | grep -v "Running" || true)
    if [ -n "$not_running" ]; then
        echo -e "${YELLOW}Some $description pods are not in Running state:${NC}"
        echo "$not_running"
        echo -e "${YELLOW}This might be normal if they're still starting up.${NC}"
    else
        echo -e "${GREEN}All $description pods are running.${NC}"
    fi
    
    return 0
}

# Function to check persistent volume claims status
check_pvcs() {
    local namespace="$1"
    
    if ! check_namespace "$namespace"; then
        echo -e "${RED}Namespace '$namespace' does not exist.${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Checking PVCs in namespace '$namespace'...${NC}"
    
    # Check for PVCs in Pending state
    local pending_pvcs=$(kubectl get pvc -n "$namespace" --no-headers 2>/dev/null | grep "Pending" || true)
    if [ -n "$pending_pvcs" ]; then
        echo -e "${RED}Found PVCs in Pending state in namespace '$namespace':${NC}"
        echo "$pending_pvcs"
        return 1
    fi
    
    local pvcs=$(kubectl get pvc -n "$namespace" --no-headers 2>/dev/null || true)
    if [ -z "$pvcs" ]; then
        echo -e "${YELLOW}No PVCs found in namespace '$namespace'.${NC}"
    else
        echo -e "${GREEN}All PVCs in namespace '$namespace' are bound.${NC}"
    fi
    
    return 0
}

# Function to display pod logs
display_logs() {
    local namespace="$1"
    local pod_label="$2"
    local tail_lines="$3"
    
    if [ -z "$tail_lines" ]; then
        tail_lines=50
    fi
    
    if ! check_namespace "$namespace"; then
        echo -e "${RED}Namespace '$namespace' does not exist.${NC}"
        return 1
    fi
    
    # Get the first pod matching the label
    local pod=$(kubectl get pods -n "$namespace" -l "app=$pod_label" --no-headers 2>/dev/null | head -1 | awk '{print $1}')
    
    if [ -z "$pod" ]; then
        echo -e "${RED}No pods found with label 'app=$pod_label' in namespace '$namespace'.${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Displaying logs for pod '$pod' in namespace '$namespace':${NC}"
    kubectl logs -n "$namespace" "$pod" --tail="$tail_lines"
}

# Function to fix common issues
fix_issue() {
    local issue="$1"
    local namespace="$2"
    local component="$3"
    
    case "$issue" in
        "pending_pvcs")
            echo -e "${YELLOW}Attempting to fix pending PVCs in namespace '$namespace'...${NC}"
            # List the pending PVCs
            kubectl get pvc -n "$namespace" | grep "Pending"
            echo -e "${YELLOW}This is usually a storage class issue or insufficient resources.${NC}"
            echo "Options:"
            echo "1. Check if the storage class exists:"
            kubectl get storageclass
            echo "2. Check if you have proper permissions to provision volumes"
            echo "3. If using local development, you might need to create a storage class that uses local storage"
            ;;
            
        "image_pull")
            echo -e "${YELLOW}Attempting to fix image pull issues for '$component' in namespace '$namespace'...${NC}"
            # Get the pod with image pull issues
            local pod=$(kubectl get pods -n "$namespace" -l "app=$component" --no-headers | grep -E 'ImagePullBackOff|ErrImagePull' | awk '{print $1}' | head -1)
            if [ -n "$pod" ]; then
                # Show the detailed pod status
                kubectl describe pod -n "$namespace" "$pod"
                echo -e "${YELLOW}Common causes:${NC}"
                echo "1. Image doesn't exist or tag is incorrect"
                echo "2. No access to private repository"
                echo "3. Rate limiting on Docker Hub (consider adding imagePullSecrets or using a different registry)"
            else
                echo -e "${RED}No pods with image pull issues found.${NC}"
            fi
            ;;
            
        "crash_loop")
            echo -e "${YELLOW}Attempting to diagnose crash loop issues for '$component' in namespace '$namespace'...${NC}"
            # Get the pod with crash loop issues
            local pod=$(kubectl get pods -n "$namespace" -l "app=$component" --no-headers | grep "CrashLoopBackOff" | awk '{print $1}' | head -1)
            if [ -n "$pod" ]; then
                # Show the logs
                echo -e "${YELLOW}Pod logs:${NC}"
                kubectl logs -n "$namespace" "$pod" --tail=50
                echo -e "\n${YELLOW}Pod details:${NC}"
                kubectl describe pod -n "$namespace" "$pod"
                echo -e "${YELLOW}Common causes:${NC}"
                echo "1. Application error in container startup"
                echo "2. Insufficient resources (memory/CPU)"
                echo "3. Configuration issues with environment variables or volumes"
            else
                echo -e "${RED}No pods in CrashLoopBackOff state found.${NC}"
            fi
            ;;
            
        "network")
            echo -e "${YELLOW}Checking network connectivity issues in namespace '$namespace'...${NC}"
            # Check services
            echo -e "${YELLOW}Services in namespace '$namespace':${NC}"
            kubectl get svc -n "$namespace"
            
            # Check network policies
            echo -e "\n${YELLOW}Network policies in namespace '$namespace':${NC}"
            kubectl get networkpolicies -n "$namespace" 2>/dev/null || echo "No network policies found"
            
            echo -e "${YELLOW}Common network issues:${NC}"
            echo "1. Services not exposing the correct ports"
            echo "2. Restrictive network policies"
            echo "3. Using wrong service names for DNS resolution"
            echo "4. Service targeting wrong pods (selector labels mismatch)"
            ;;
            
        "resources")
            echo -e "${YELLOW}Checking resource constraints in namespace '$namespace'...${NC}"
            # Check node resources
            echo -e "${YELLOW}Node resource usage:${NC}"
            kubectl top nodes 2>/dev/null || echo "kubectl top nodes not available. Metrics server might not be installed."
            
            # Check pod resources
            echo -e "\n${YELLOW}Pod resource usage in namespace '$namespace':${NC}"
            kubectl top pods -n "$namespace" 2>/dev/null || echo "kubectl top pods not available. Metrics server might not be installed."
            
            # Check resource quotas
            echo -e "\n${YELLOW}Resource quotas in namespace '$namespace':${NC}"
            kubectl get resourcequotas -n "$namespace" 2>/dev/null || echo "No resource quotas found"
            
            echo -e "${YELLOW}Common resource issues:${NC}"
            echo "1. Insufficient CPU or memory on nodes"
            echo "2. Resource quotas preventing pod creation"
            echo "3. Pods requesting more resources than available"
            ;;
            
        "config")
            echo -e "${YELLOW}Checking configuration for '$component' in namespace '$namespace'...${NC}"
            # Check configmaps
            echo -e "${YELLOW}ConfigMaps used by '$component':${NC}"
            kubectl get configmaps -n "$namespace" -l "app=$component" 2>/dev/null || echo "No ConfigMaps found with label app=$component"
            
            # Check secrets
            echo -e "\n${YELLOW}Secrets used by '$component':${NC}"
            kubectl get secrets -n "$namespace" -l "app=$component" 2>/dev/null || echo "No Secrets found with label app=$component"
            
            echo -e "${YELLOW}Common configuration issues:${NC}"
            echo "1. Missing required ConfigMaps or Secrets"
            echo "2. Typos in environment variable references"
            echo "3. Incorrect configuration values"
            ;;
            
        *)
            echo -e "${RED}Unknown issue type: $issue${NC}"
            return 1
            ;;
    esac
}

# Function to print diagnostic information
print_diagnostics() {
    print_header "System Information"
    echo "Date: $(date)"
    echo "Kubernetes Client Version:"
    kubectl version --client
    echo "Kubernetes Server Version:"
    kubectl version --short 2>/dev/null || echo "Unable to get server version. Cluster might not be accessible."
    
    print_header "Namespace Status"
    kubectl get namespaces
    
    print_header "Nodes Status"
    kubectl get nodes
    
    print_header "Persistent Volumes"
    kubectl get pv
    
    print_header "Storage Classes"
    kubectl get storageclass
    
    print_header "Custom Resource Definitions"
    kubectl get crd | grep -E 'kafka|mlflow|spark|airflow'
}

# Function to check component health and connectivity
check_end_to_end() {
    print_header "End-to-End Component Check"
    
    # Check Kafka
    if check_namespace "kafka"; then
        echo -e "${YELLOW}Checking Kafka...${NC}"
        kubectl get pods -n kafka
    else
        echo -e "${RED}Kafka namespace does not exist.${NC}"
    fi
    
    # Check Redis
    if check_namespace "storage"; then
        echo -e "\n${YELLOW}Checking Redis...${NC}"
        kubectl get pods -n storage -l "app.kubernetes.io/name=redis"
    else
        echo -e "${RED}Storage namespace does not exist.${NC}"
    fi
    
    # Check MLflow
    if check_namespace "mlflow"; then
        echo -e "\n${YELLOW}Checking MLflow...${NC}"
        kubectl get pods -n mlflow
    else
        echo -e "${RED}MLflow namespace does not exist.${NC}"
    fi
    
    # Check Airflow
    if check_namespace "airflow"; then
        echo -e "\n${YELLOW}Checking Airflow...${NC}"
        kubectl get pods -n airflow
    else
        echo -e "${RED}Airflow namespace does not exist.${NC}"
    fi
}

# Main menu
while true; do
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}   MLOps Platform Debugging Menu        ${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo "1. Show diagnostic information"
    echo "2. Check component health"
    echo "3. Check persistent volume claims"
    echo "4. Show component logs"
    echo "5. Fix common issues"
    echo "6. Check end-to-end connectivity"
    echo "7. Exit"
    echo ""
    read -p "Enter your choice (1-7): " choice
    
    case $choice in
        1)
            print_diagnostics
            ;;
        2)
            echo ""
            echo "Available components:"
            echo "1. Kafka (namespace: kafka)"
            echo "2. Redis (namespace: storage)"
            echo "3. PostgreSQL (namespace: storage)"
            echo "4. MLflow (namespace: mlflow)"
            echo "5. Spark Operator (namespace: spark)"
            echo "6. Airflow (namespace: airflow)"
            echo "7. Model Serving (namespace: model-serving)"
            echo "8. Return to main menu"
            echo ""
            read -p "Enter component to check (1-8): " component_choice
            
            case $component_choice in
                1) check_component "kafka" "kafka" "Kafka" ;;
                2) check_component "storage" "redis" "Redis" ;;
                3) check_component "storage" "postgresql" "PostgreSQL" ;;
                4) check_component "mlflow" "mlflow" "MLflow" ;;
                5) check_component "spark" "spark-operator" "Spark Operator" ;;
                6) check_component "airflow" "airflow" "Airflow" ;;
                7) check_component "model-serving" "model-serving" "Model Serving" ;;
                8) echo "Returning to main menu" ;;
                *) echo -e "${RED}Invalid choice.${NC}" ;;
            esac
            ;;
        3)
            echo ""
            echo "Available namespaces for PVC check:"
            echo "1. kafka"
            echo "2. storage"
            echo "3. mlflow"
            echo "4. spark"
            echo "5. airflow"
            echo "6. model-serving"
            echo "7. Return to main menu"
            echo ""
            read -p "Enter namespace to check (1-7): " pvc_choice
            
            case $pvc_choice in
                1) check_pvcs "kafka" ;;
                2) check_pvcs "storage" ;;
                3) check_pvcs "mlflow" ;;
                4) check_pvcs "spark" ;;
                5) check_pvcs "airflow" ;;
                6) check_pvcs "model-serving" ;;
                7) echo "Returning to main menu" ;;
                *) echo -e "${RED}Invalid choice.${NC}" ;;
            esac
            ;;
        4)
            echo ""
            echo "Select component to view logs:"
            echo "1. Kafka (namespace: kafka)"
            echo "2. Schema Registry (namespace: kafka)"
            echo "3. Redis (namespace: storage)"
            echo "4. PostgreSQL (namespace: storage)"
            echo "5. MLflow (namespace: mlflow)"
            echo "6. Spark Operator (namespace: spark)"
            echo "7. Airflow (namespace: airflow)"
            echo "8. Return to main menu"
            echo ""
            read -p "Enter component for logs (1-8): " logs_choice
            
            case $logs_choice in
                1) display_logs "kafka" "kafka" 50 ;;
                2) display_logs "kafka" "schema-registry" 50 ;;
                3) display_logs "storage" "redis" 50 ;;
                4) display_logs "storage" "postgresql" 50 ;;
                5) display_logs "mlflow" "mlflow" 50 ;;
                6) display_logs "spark" "spark-operator" 50 ;;
                7) display_logs "airflow" "airflow" 50 ;;
                8) echo "Returning to main menu" ;;
                *) echo -e "${RED}Invalid choice.${NC}" ;;
            esac
            ;;
        5)
            echo ""
            echo "Select issue to fix:"
            echo "1. Pending PVCs"
            echo "2. Image pull failures"
            echo "3. Pods in CrashLoopBackOff"
            echo "4. Network connectivity issues"
            echo "5. Resource constraints"
            echo "6. Configuration issues"
            echo "7. Return to main menu"
            echo ""
            read -p "Enter issue to fix (1-7): " fix_choice
            
            # Prompt for namespace and component when appropriate
            case $fix_choice in
                1)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace to fix PVCs: " fix_namespace
                    fix_issue "pending_pvcs" "$fix_namespace" ""
                    ;;
                2)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace: " fix_namespace
                    read -p "Enter component label: " fix_component
                    fix_issue "image_pull" "$fix_namespace" "$fix_component"
                    ;;
                3)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace: " fix_namespace
                    read -p "Enter component label: " fix_component
                    fix_issue "crash_loop" "$fix_namespace" "$fix_component"
                    ;;
                4)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace to check for network issues: " fix_namespace
                    fix_issue "network" "$fix_namespace" ""
                    ;;
                5)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace to check for resource issues: " fix_namespace
                    fix_issue "resources" "$fix_namespace" ""
                    ;;
                6)
                    echo "Available namespaces:"
                    kubectl get namespaces --no-headers | awk '{print $1}'
                    read -p "Enter namespace: " fix_namespace
                    read -p "Enter component label: " fix_component
                    fix_issue "config" "$fix_namespace" "$fix_component"
                    ;;
                7) echo "Returning to main menu" ;;
                *) echo -e "${RED}Invalid choice.${NC}" ;;
            esac
            ;;
        6)
            check_end_to_end
            ;;
        7)
            echo -e "${GREEN}Exiting MLOps Platform Debugging Assistant.${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter a number between 1 and 7.${NC}"
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
    clear
done 