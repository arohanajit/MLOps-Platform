#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}      MLOps Platform Integration       ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Function to check if a script exists and is executable
check_script() {
    if [ ! -f "$1" ] || [ ! -x "$1" ]; then
        echo -e "${RED}Error: $1 is not available or not executable.${NC}"
        exit 1
    fi
}

# Function to run a deployment step
run_step() {
    echo -e "${YELLOW}Running: $1${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}(Dry run) Would execute: $1${NC}"
    else
        check_script "$1"
        if ! "$1"; then
            echo -e "${RED}Step failed: $1${NC}"
            if [ "$FAIL_FAST" = true ]; then
                exit 1
            fi
        fi
    fi
    echo ""
}

# Parse command line arguments
DRY_RUN=false
FAIL_FAST=true
VERIFY_ONLY=false
SPECIFIC_STEP=""

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --dry-run       Show what would be done without executing anything"
    echo "  --continue-on-error  Continue to the next step even if a step fails"
    echo "  --verify-only   Only run the verification step"
    echo "  --only STEP     Run only the specified step (one of: infrastructure, data, feature, training, serving, observability)"
    echo "  --help          Show this help message"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --continue-on-error)
            FAIL_FAST=false
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --only)
            SPECIFIC_STEP="$2"
            shift 2
            ;;
        --help)
            print_usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            ;;
    esac
done

# Validate the specific step if provided
if [ -n "$SPECIFIC_STEP" ]; then
    case "$SPECIFIC_STEP" in
        infrastructure|data|feature|training|serving|observability)
            echo -e "${YELLOW}Will only run the $SPECIFIC_STEP step${NC}"
            ;;
        *)
            echo -e "${RED}Invalid step: $SPECIFIC_STEP${NC}"
            print_usage
            ;;
    esac
fi

# Check if all required scripts exist
echo "Checking required scripts..."
SCRIPTS=(
    "./setup-mlops-platform.sh"
    "./deploy-data-processing.sh"
    "./deploy-feature-engineering.sh"
    "./deploy-model-training.sh"
    "./deploy-model-serving.sh"
    "./deploy-observability.sh"
    "./verify-installation.sh"
)

if [ "$DRY_RUN" = false ]; then
    for script in "${SCRIPTS[@]}"; do
        if [ ! -f "$script" ] || [ ! -x "$script" ]; then
            echo -e "${YELLOW}Warning: $script is not available or not executable.${NC}"
        fi
    done
fi

# Main integration process
if [ "$VERIFY_ONLY" = true ]; then
    run_step "./verify-installation.sh"
    exit 0
fi

# Phase 1: Infrastructure Setup
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "infrastructure" ]; then
    echo -e "${GREEN}=== Phase 1: Infrastructure Setup ===${NC}"
    run_step "./setup-mlops-platform.sh"
fi

# Phase 2: Data Pipeline Implementation
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "data" ]; then
    echo -e "${GREEN}=== Phase 2: Data Pipeline Implementation ===${NC}"
    run_step "./deploy-data-processing.sh"
fi

# Phase 3: Feature Engineering
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "feature" ]; then
    echo -e "${GREEN}=== Phase 3: Feature Engineering Implementation ===${NC}"
    run_step "./deploy-feature-engineering.sh"
    
    # Populate the feature registry if the script exists
    if [ -f "./populate-feature-registry.py" ]; then
        echo -e "${YELLOW}Populating feature registry...${NC}"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}(Dry run) Would execute: python ./populate-feature-registry.py${NC}"
        else
            python ./populate-feature-registry.py || {
                echo -e "${RED}Failed to populate feature registry${NC}"
                if [ "$FAIL_FAST" = true ]; then exit 1; fi
            }
        fi
    fi
fi

# Phase 4: Model Training Infrastructure
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "training" ]; then
    echo -e "${GREEN}=== Phase 4: Model Training Infrastructure ===${NC}"
    run_step "./deploy-model-training.sh"
fi

# Phase 5: Model Serving
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "serving" ]; then
    echo -e "${GREEN}=== Phase 5: Model Serving ===${NC}"
    run_step "./deploy-model-serving.sh"
fi

# Phase 6: Observability
if [ -z "$SPECIFIC_STEP" ] || [ "$SPECIFIC_STEP" = "observability" ]; then
    echo -e "${GREEN}=== Phase 6: Observability ===${NC}"
    run_step "./deploy-observability.sh"
fi

# Verify the installation
echo -e "${GREEN}=== Verifying Installation ===${NC}"
run_step "./verify-installation.sh"

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   MLOps Platform Integration Complete   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "You can use the following commands to access the different components:"
echo -e "${YELLOW}MLflow:${NC} kubectl port-forward -n mlflow svc/mlflow 5000:5000"
echo -e "${YELLOW}Airflow:${NC} kubectl port-forward -n airflow svc/airflow-webserver 8080:8080"
echo ""
echo "For debugging, you can check logs with: kubectl logs -n <namespace> <pod-name>" 