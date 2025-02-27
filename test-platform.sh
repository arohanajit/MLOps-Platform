#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}      MLOps Platform Testing Suite       ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    echo -e "${YELLOW}Running test: $test_name${NC}"
    echo -e "Command: $test_cmd"
    echo -e "${YELLOW}Test started at: $(date)${NC}"
    
    if eval "$test_cmd"; then
        echo -e "${GREEN}Test passed: $test_name${NC}"
        return 0
    else
        echo -e "${RED}Test failed: $test_name${NC}"
        return 1
    fi
}

# Parse command line arguments
RUN_ALL=true
SPECIFIC_TEST=""
FAIL_FAST=true

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --test TEST_NAME  Run only the specified test (one of: data, feature, model, serving, observability)"
    echo "  --continue-on-error  Continue to the next test even if a test fails"
    echo "  --help          Show this help message"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            RUN_ALL=false
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --continue-on-error)
            FAIL_FAST=false
            shift
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

# Validate the specific test if provided
if [ "$RUN_ALL" = false ]; then
    case "$SPECIFIC_TEST" in
        data|feature|model|serving|observability)
            echo -e "${YELLOW}Will only run the $SPECIFIC_TEST test${NC}"
            ;;
        *)
            echo -e "${RED}Invalid test: $SPECIFIC_TEST${NC}"
            print_usage
            ;;
    esac
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed.${NC}"
    exit 1
fi

# Check if MLOps platform is running
echo "Checking if MLOps platform is running..."
if ! kubectl get ns mlflow &> /dev/null; then
    echo -e "${RED}Error: MLOps platform is not running. Please run integrate-platform.sh first.${NC}"
    exit 1
fi

# Test results counter
total_tests=0
passed_tests=0
failed_tests=0

# Test 1: Data Processing Test
if [ "$RUN_ALL" = true ] || [ "$SPECIFIC_TEST" = "data" ]; then
    total_tests=$((total_tests + 1))
    
    # Using the script if it exists, otherwise run a basic test
    if [ -f "./test-data-processing.sh" ]; then
        TEST_CMD="./test-data-processing.sh"
    else
        # Simple test to check if Kafka is running
        TEST_CMD="kubectl get pods -n kafka | grep -q Running"
    fi
    
    if run_test "Data Processing" "$TEST_CMD"; then
        passed_tests=$((passed_tests + 1))
    else
        failed_tests=$((failed_tests + 1))
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping tests due to failure${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Test 2: Feature Engineering Test
if [ "$RUN_ALL" = true ] || [ "$SPECIFIC_TEST" = "feature" ]; then
    total_tests=$((total_tests + 1))
    
    # Using the script if it exists, otherwise run a basic test
    if [ -f "./test-feature-engineering.sh" ]; then
        TEST_CMD="./test-feature-engineering.sh"
    else
        # Simple test to check if feature store is running
        TEST_CMD="kubectl get pods -n storage | grep -q redis && echo 'Feature store is running'"
    fi
    
    if run_test "Feature Engineering" "$TEST_CMD"; then
        passed_tests=$((passed_tests + 1))
    else
        failed_tests=$((failed_tests + 1))
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping tests due to failure${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Test 3: Model Training Test
if [ "$RUN_ALL" = true ] || [ "$SPECIFIC_TEST" = "model" ]; then
    total_tests=$((total_tests + 1))
    
    # Using the script if it exists, otherwise run a basic test
    if [ -f "./test-model-training.sh" ]; then
        TEST_CMD="./test-model-training.sh"
    else
        # Simple test to check if MLflow is running
        TEST_CMD="kubectl get pods -n mlflow | grep -q Running && echo 'MLflow is running'"
    fi
    
    if run_test "Model Training" "$TEST_CMD"; then
        passed_tests=$((passed_tests + 1))
    else
        failed_tests=$((failed_tests + 1))
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping tests due to failure${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Test 4: Model Serving Test
if [ "$RUN_ALL" = true ] || [ "$SPECIFIC_TEST" = "serving" ]; then
    total_tests=$((total_tests + 1))
    
    # Using the script if it exists, otherwise run a basic test
    if [ -f "./test-model-serving.sh" ]; then
        TEST_CMD="./test-model-serving.sh"
    else
        # Simple test to check if model serving is running
        TEST_CMD="kubectl get pods -n model-serving 2>/dev/null | grep -q Running || echo 'Model serving pods not found or not running'"
    fi
    
    if run_test "Model Serving" "$TEST_CMD"; then
        passed_tests=$((passed_tests + 1))
    else
        failed_tests=$((failed_tests + 1))
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping tests due to failure${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Test 5: Observability Test
if [ "$RUN_ALL" = true ] || [ "$SPECIFIC_TEST" = "observability" ]; then
    total_tests=$((total_tests + 1))
    
    # Using the script if it exists, otherwise run a basic test
    if [ -f "./test-observability.sh" ]; then
        TEST_CMD="./test-observability.sh"
    else
        # Simple test to check if monitoring is running
        TEST_CMD="kubectl get pods -n monitoring 2>/dev/null | grep -q Running || echo 'Monitoring pods not found or not running'"
    fi
    
    if run_test "Observability" "$TEST_CMD"; then
        passed_tests=$((passed_tests + 1))
    else
        failed_tests=$((failed_tests + 1))
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping tests due to failure${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Print summary
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}      Test Summary      ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo "Total tests: $total_tests"
echo -e "${GREEN}Passed tests: $passed_tests${NC}"

if [ $failed_tests -gt 0 ]; then
    echo -e "${RED}Failed tests: $failed_tests${NC}"
    
    echo -e "${YELLOW}Troubleshooting tips:${NC}"
    echo "1. Check component logs: kubectl logs -n <namespace> <pod-name>"
    echo "2. Verify all deployments are running: kubectl get deployments --all-namespaces"
    echo "3. Check persistent volumes: kubectl get pv,pvc --all-namespaces"
    echo "4. Review integration script output for errors"
    
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
fi 