# MLOps Platform

A comprehensive MLOps platform that manages the full lifecycle of machine learning operations, from data ingestion to model serving and monitoring.

## Overview

This MLOps platform provides a complete infrastructure for ML workflows, including:

- **Data ingestion and validation**
- **Feature engineering and storage**
- **Model training and hyperparameter tuning**
- **Model serving and monitoring**
- **ML Experiment tracking**

## Quick Links

- [Architecture Overview](docs/architecture.md)
- [Setup Guide](docs/setup-guide.md)
- [Development Environment](docs/development-environment.md)
- [Developer Onboarding](docs/developer-onboarding.md)
- [CI/CD Pipeline](docs/cicd-pipeline.md)
- [Git Workflow](docs/git-workflow.md)
- [Platform Management Script](docs/management-script.md)

## Component Documentation

- [Feature Engineering](src/feature_engineering/README.md)
- [Model Serving](src/model_serving/README.md)
- [Testing Guide](src/tests/README.md)

## Architecture

The platform consists of several pipelines:

- **Data Pipeline**: Handles data ingestion, validation, and transformation
- **Training Pipeline**: Manages model training, hyperparameter tuning, and experiment tracking
- **Serving Pipeline**: Provides real-time predictions and feature serving
- **Observability**: Monitors system health and model performance

For detailed architecture information, see [Architecture Documentation](docs/architecture.md).

## Infrastructure Components

Our MLOps platform uses the following infrastructure components:

### Cloud Resources (AWS)
- EKS (Kubernetes) for orchestration
- S3 for artifact storage
- ECR for container registry
- RDS (PostgreSQL) for metadata storage
- ElastiCache (Redis) for feature store and caching

### Core Platform Components
- **Kafka & Schema Registry**: For data streaming and schema validation
- **Spark (via Kubernetes Operator)**: For distributed data processing
- **MLflow**: For experiment tracking and model registry
- **Redis**: For online feature serving
- **PostgreSQL**: For offline storage and metadata
- **MinIO**: For local S3-compatible storage during development

## Implementation Phases

### Phase 1: Infrastructure Setup ✓
- Cloud environment provisioning (Kubernetes cluster, networking, IAM)
- Core platform components installation (Kafka, Schema Registry, Spark, databases, MLflow)

### Phase 2: Data Pipeline Implementation
- Data producers integration
- Schema validation setup
- Data transformation workflows
- Feature storage implementation

### Phase 3: Model Training Infrastructure
- Experiment tracking configuration
- Hyperparameter tuning setup
- Model registry implementation

### Phase 4: Model Serving
- Online prediction services
- Feature store integration
- API gateway configuration

### Phase 5: Observability
- Logging and monitoring infrastructure
- Performance dashboards
- Alerting system

## Getting Started

### Prerequisites

- Docker
- Docker Compose
- Git

### Local Development Environment

To run the platform locally for development:

1. Clone this repository
   ```bash
   git clone https://github.com/yourusername/MLOps-Platform.git
   cd MLOps-Platform
   ```

2. Make the management script executable:
   ```bash
   chmod +x mlops-platform.sh
   ```

3. Verify installation requirements:
   ```bash
   ./mlops-platform.sh verify
   ```

4. Start the platform:
   ```bash
   ./mlops-platform.sh start
   ```

5. Check service status:
   ```bash
   ./mlops-platform.sh status
   ```

For detailed setup instructions, see the [Setup Guide](docs/setup-guide.md).

## Platform Management

Our platform comes with a consolidated management script that supports the following commands:

```bash
./mlops-platform.sh [command]
```

Commands:
- `start` - Start the MLOps platform
- `stop` - Stop the MLOps platform 
- `restart` - Restart the MLOps platform
- `status` - Check status of all services
- `logs [service]` - Show logs for a specific service or all services
- `test` - Run tests against the platform
- `verify` - Verify platform installation
- `clean` - Remove all containers and volumes
- `help` - Show help message

## Component Access

After starting the platform, you can access the following components:

- **MLflow UI**: http://localhost:5001
- **Feature Registry API**: http://localhost:8000
- **Feature Store API**: http://localhost:8001
- **MinIO Console**: http://localhost:9001 (Username: minioadmin, Password: minioadmin)
- **Kafka**: localhost:9092
- **Schema Registry**: http://localhost:8081

## Development Workflow

For information on development workflow and contributing to this project, see:
- [Git Workflow](docs/git-workflow.md)
- [Developer Onboarding](docs/developer-onboarding.md)
- [CI/CD Pipeline](docs/cicd-pipeline.md)

## Project Structure

```
MLOps-Platform/
├── docker-compose.yml       # Consolidated Docker Compose configuration
├── mlops-platform.sh        # Management script for platform operations
├── src/                     # Source code for all platform components
│   ├── feature_registry/    # Feature metadata registry service
│   ├── feature_store/       # Feature storage and serving service
│   ├── feature_engineering/ # Feature transformation pipelines
│   ├── model_training/      # Model training pipelines
│   ├── model_serving/       # Model serving components
│   ├── processing/          # Data processing pipelines
│   ├── storage/             # Storage layer abstractions
│   ├── tests/               # Test suites
│   ├── clients/             # Client libraries for services
│   └── producers/           # Data production simulators
├── terraform/               # Infrastructure as Code
│   ├── modules/             # Terraform modules
│   └── ...                  # Environment-specific configurations
├── kubernetes/              # Kubernetes manifests
├── docs/                    # Documentation
└── .github/                 # GitHub Actions workflows
```

## License

[Add your license information here]

## Contact

[Add contact information or maintainer details here]
