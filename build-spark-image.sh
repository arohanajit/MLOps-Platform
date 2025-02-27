#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   Build and Push Spark Docker Image   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed.${NC}"
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    exit 1
fi

# Configuration
ECR_REPO_NAME="mlops"
IMAGE_NAME="spark-driver"
IMAGE_TAG="latest"
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    echo -e "${YELLOW}AWS region not configured, defaulting to ${AWS_REGION}${NC}"
fi

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to get AWS account ID. Make sure you're authenticated with AWS.${NC}"
    exit 1
fi

# Build full ECR repository URI
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${YELLOW}AWS Account ID: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${YELLOW}AWS Region: ${AWS_REGION}${NC}"
echo -e "${YELLOW}ECR Repository: ${ECR_REPO}${NC}"
echo ""

# Create ECR repository if it doesn't exist
echo -e "${YELLOW}Checking if ECR repository exists...${NC}"
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} > /dev/null 2>&1 || {
    echo -e "${YELLOW}Creating ECR repository ${ECR_REPO_NAME}...${NC}"
    aws ecr create-repository --repository-name ${ECR_REPO_NAME} > /dev/null
    echo -e "${GREEN}ECR repository created.${NC}"
}
echo -e "${GREEN}ECR repository exists.${NC}"
echo ""

# Login to ECR
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO}
echo -e "${GREEN}Logged in to ECR successfully.${NC}"
echo ""

# Create validation directory if it doesn't exist
echo -e "${YELLOW}Checking if Spark validation directory exists...${NC}"
if [ ! -d "src/processing/spark/validation" ]; then
    echo -e "${YELLOW}Creating Spark validation directory...${NC}"
    mkdir -p src/processing/spark/validation
    echo -e "${GREEN}Spark validation directory created.${NC}"
else
    echo -e "${GREEN}Spark validation directory already exists.${NC}"
fi
echo ""

# Update the customer_events_processor.yaml file with ECR repository
echo -e "${YELLOW}Updating Spark application configurations with ECR repository...${NC}"
sed -i.bak "s|\$(ECR_REPO)/mlops|${ECR_REPO}|g" kubernetes/spark/customer-events-processor.yaml
sed -i.bak "s|\$(ECR_REPO)/mlops|${ECR_REPO}|g" kubernetes/spark/data-validator.yaml
echo -e "${GREEN}Spark application configurations updated.${NC}"
echo ""

# Build the Docker image
echo -e "${YELLOW}Building Spark Docker image...${NC}"
docker build -t ${ECR_REPO}/${IMAGE_NAME}:${IMAGE_TAG} -f src/processing/spark/Dockerfile src/processing/spark
echo -e "${GREEN}Spark Docker image built successfully.${NC}"
echo ""

# Push the Docker image
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push ${ECR_REPO}/${IMAGE_NAME}:${IMAGE_TAG}
echo -e "${GREEN}Image pushed to ECR successfully.${NC}"
echo ""

# Print completion message
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   Spark Docker Image Built and Pushed Successfully!   ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo ""
echo -e "Image: ${YELLOW}${ECR_REPO}/${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Make the script executable: ${YELLOW}chmod +x build-spark-image.sh${NC}"
echo -e "  2. Run the deploy script: ${YELLOW}./deploy-data-processing.sh${NC}"
echo -e "  3. Deploy your Spark applications using kubectl"
echo ""
echo -e "${GREEN}======================================================${NC}" 