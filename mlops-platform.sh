#!/bin/bash

set -e

# Color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print a message with a timestamp
log() {
  echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Print a success message
success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Print a warning message
warn() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Print an error message
error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage information
usage() {
  echo "MLOps Platform Management Script"
  echo ""
  echo "Usage: $0 [command]"
  echo ""
  echo "Commands:"
  echo "  start             - Start the MLOps platform"
  echo "  stop              - Stop the MLOps platform"
  echo "  restart           - Restart the MLOps platform"
  echo "  status            - Check status of all services"
  echo "  logs [service]    - Show logs for a specific service or all services"
  echo "  test              - Run tests against the platform"
  echo "  verify            - Verify platform installation"
  echo "  clean             - Remove all containers and volumes"
  echo "  help              - Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 start          - Start all services"
  echo "  $0 logs mlflow    - Show logs for MLflow service"
  echo ""
}

# Start the platform
start_platform() {
  log "Starting MLOps platform..."
  docker-compose -f docker-compose.yml up -d
  success "MLOps platform started successfully."
}

# Stop the platform
stop_platform() {
  log "Stopping MLOps platform..."
  docker-compose -f docker-compose.yml down
  success "MLOps platform stopped successfully."
}

# Restart the platform
restart_platform() {
  log "Restarting MLOps platform..."
  docker-compose -f docker-compose.yml down
  docker-compose -f docker-compose.yml up -d
  success "MLOps platform restarted successfully."
}

# Check platform status
check_status() {
  log "Checking status of MLOps platform services..."
  docker-compose -f docker-compose.yml ps
}

# Show logs
show_logs() {
  if [ -z "$1" ]; then
    log "Showing logs for all services..."
    docker-compose -f docker-compose.yml logs --tail=100 -f
  else
    log "Showing logs for $1 service..."
    docker-compose -f docker-compose.yml logs --tail=100 -f "$1"
  fi
}

# Test the platform
test_platform() {
  log "Running platform tests..."
  
  # Check if services are running
  if ! docker-compose -f docker-compose.yml ps | grep -q "Up"; then
    error "MLOps platform is not running. Please start it first with '$0 start'"
    exit 1
  fi
  
  # Check if feature registry is accessible
  log "Testing Feature Registry API..."
  if curl -s http://localhost:8000/health | grep -q "status"; then
    success "Feature Registry API is accessible."
  else
    error "Feature Registry API is not accessible."
    exit 1
  fi
  
  # Check if feature store is accessible
  log "Testing Feature Store API..."
  if curl -s http://localhost:8001/health | grep -q "status"; then
    success "Feature Store API is accessible."
  else
    error "Feature Store API is not accessible."
    exit 1
  fi
  
  # Check if MLflow is accessible
  log "Testing MLflow UI..."
  if curl -s -I http://localhost:5001 | grep -q "200 OK"; then
    success "MLflow UI is accessible."
  else
    error "MLflow UI is not accessible."
    exit 1
  fi
  
  # Check if Minio is accessible
  log "Testing MinIO API..."
  if curl -s -I http://localhost:9000 | grep -q "Server: MinIO"; then
    success "MinIO API is accessible."
  else
    error "MinIO API is not accessible."
  fi

  success "All tests passed successfully!"
}

# Verify installation
verify_installation() {
  log "Verifying MLOps platform installation..."
  
  # Check Docker
  if ! command -v docker >/dev/null 2>&1; then
    error "Docker is not installed. Please install Docker first."
    exit 1
  else
    success "Docker is installed."
  fi
  
  # Check Docker Compose
  if ! command -v docker-compose >/dev/null 2>&1; then
    error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
  else
    success "Docker Compose is installed."
  fi
  
  # Check if docker-compose.yml exists
  if [ ! -f "docker-compose.yml" ]; then
    error "docker-compose.yml not found in the current directory."
    exit 1
  else
    success "docker-compose.yml exists."
  fi
  
  success "Installation verification completed successfully."
}

# Clean up resources
clean_platform() {
  log "Cleaning up MLOps platform resources..."
  
  # Ask for confirmation
  read -p "This will remove all containers and volumes. Are you sure? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Operation cancelled."
    exit 0
  fi
  
  docker-compose -f docker-compose.yml down -v
  success "MLOps platform resources cleaned up successfully."
}

# Main script execution
case "$1" in
  start)
    start_platform
    ;;
  stop)
    stop_platform
    ;;
  restart)
    restart_platform
    ;;
  status)
    check_status
    ;;
  logs)
    show_logs "$2"
    ;;
  test)
    test_platform
    ;;
  verify)
    verify_installation
    ;;
  clean)
    clean_platform
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    error "Unknown command: $1"
    usage
    exit 1
    ;;
esac

exit 0 