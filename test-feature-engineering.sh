#!/bin/bash

# Test Feature Engineering Components
# This script helps you test the Feature Engineering components locally

set -e

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Feature Engineering Test Script${NC}"
echo "This script will help you test the Feature Engineering components locally."
echo 

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  --up             Start the services (default)"
    echo "  --down           Stop the services"
    echo "  --test           Run the tests"
    echo "  --test-mock      Run the tests in mock mode (no actual infrastructure needed)"
    echo "  --help           Display this help message"
    echo
}

# Parse command line arguments
ACTION="up"
if [[ $# -gt 0 ]]; then
    case "$1" in
        --up)
            ACTION="up"
            ;;
        --down)
            ACTION="down"
            ;;
        --test)
            ACTION="test"
            ;;
        --test-mock)
            ACTION="test-mock"
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
fi

# Start the services
if [[ "$ACTION" == "up" ]]; then
    echo -e "${YELLOW}Starting services...${NC}"
    docker-compose -f docker-compose-feature-eng.yml up -d
    
    echo 
    echo -e "${GREEN}Services started successfully!${NC}"
    echo "Feature Registry API: http://localhost:8000"
    echo "Feature Store API: http://localhost:8001"
    echo
    echo "To test the services, run:"
    echo "  $0 --test"
    echo
    echo "To stop the services, run:"
    echo "  $0 --down"
    
# Stop the services
elif [[ "$ACTION" == "down" ]]; then
    echo -e "${YELLOW}Stopping services...${NC}"
    docker-compose -f docker-compose-feature-eng.yml down
    
    echo
    echo -e "${GREEN}Services stopped successfully!${NC}"
    
# Run the tests
elif [[ "$ACTION" == "test" ]]; then
    echo -e "${YELLOW}Running tests...${NC}"
    
    # Check if services are running
    if ! curl -s http://localhost:8000/health &> /dev/null; then
        echo -e "${RED}Feature Registry API is not running. Start the services first:${NC}"
        echo "  $0 --up"
        exit 1
    fi
    
    if ! curl -s http://localhost:8001/health &> /dev/null; then
        echo -e "${RED}Feature Store API is not running. Start the services first:${NC}"
        echo "  $0 --up"
        exit 1
    fi
    
    # Install test dependencies if needed
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed. Please install Python 3 first.${NC}"
        exit 1
    fi
    
    # Check if the required packages are installed
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -r src/tests/requirements.txt
    
    # Run the test script
    echo -e "${YELLOW}Running Feature Engineering tests...${NC}"
    python3 src/tests/test_feature_engineering.py --registry-url http://localhost:8000 --store-url http://localhost:8001 --verbose
    
    if [[ $? -eq 0 ]]; then
        echo
        echo -e "${GREEN}Tests completed successfully!${NC}"
    else
        echo
        echo -e "${RED}Tests failed. Check the logs for details.${NC}"
        exit 1
    fi
    
# Run the tests in mock mode
elif [[ "$ACTION" == "test-mock" ]]; then
    echo -e "${YELLOW}Running tests in mock mode...${NC}"
    
    # Install test dependencies if needed
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed. Please install Python 3 first.${NC}"
        exit 1
    fi
    
    # Check if the required packages are installed
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -r src/tests/requirements.txt
    
    # Run the test script in mock mode
    echo -e "${YELLOW}Running Feature Engineering tests in mock mode...${NC}"
    python3 src/tests/test_feature_engineering.py --mock --verbose
    
    if [[ $? -eq 0 ]]; then
        echo
        echo -e "${GREEN}Tests completed successfully!${NC}"
    else
        echo
        echo -e "${RED}Tests failed. Check the logs for details.${NC}"
        exit 1
    fi
fi

exit 0 