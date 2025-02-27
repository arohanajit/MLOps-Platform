# MLOps Platform Architecture

## Overview

The MLOps platform is designed to support the entire machine learning lifecycle, from data ingestion to model deployment and monitoring. It consists of several interconnected components deployed on Kubernetes in production and Docker Compose for local development.

## Architecture Diagram (Production)

```
                                    ┌─────────────────────────────────────────────────────────────┐
                                    │                  MLOps Platform (EKS)                       │
                                    │                                                             │
┌───────────────┐                   │  ┌───────────┐    ┌─────────────┐    ┌──────────────┐      │
│  Data Sources │                   │  │           │    │             │    │              │      │
│   (External)  │───┬───────────────┼─▶│   Kafka   │───▶│ Schema      │───▶│ Data         │      │
└───────────────┘   │               │  │  Cluster  │    │ Registry    │    │ Validation   │      │
                    │               │  │           │    │             │    │              │      │
                    │               │  └───────────┘    └─────────────┘    └──────┬───────┘      │
                    │               │                                             │              │
                    │               │                                             ▼              │
┌───────────────┐   │               │  ┌───────────┐    ┌─────────────┐    ┌──────────────┐      │
│   API/UI      │   │               │  │           │    │             │    │              │      │
│  (External)   │───┘               │  │  Airflow  │◀───│   MLflow    │◀───│ Feature      │      │
└───────────────┘                   │  │(Workflow) │    │(Experiment  │    │ Engineering  │      │
                                    │  │           │    │ Tracking)   │    │              │      │
                                    │  └─────┬─────┘    └─────────────┘    └──────┬───────┘      │
                                    │        │                                    │              │
                                    │        ▼                                    ▼              │
                                    │  ┌───────────┐    ┌─────────────┐    ┌──────────────┐      │
                                    │  │           │    │             │    │              │      │
                                    │  │   Spark   │───▶│  Model      │───▶│ Model        │      │
                                    │  │(Training) │    │  Registry   │    │ Serving      │      │
                                    │  │           │    │             │    │              │      │
                                    │  └───────────┘    └─────────────┘    └──────────────┘      │
                                    │                                                             │
                                    └─────────────────────────────────────────────────────────────┘
                                                           │
                                                           │
                                    ┌─────────────────────────────────────────────────────────────┐
                                    │                                                             │
                                    │               Storage Layer                                 │
                                    │                                                             │
                                    │   ┌───────────┐    ┌─────────────┐    ┌──────────────┐      │
                                    │   │           │    │             │    │              │      │
                                    │   │    S3     │    │ PostgreSQL  │    │    Redis     │      │
                                    │   │(Artifacts)│    │ (Metadata)  │    │ (Feature     │      │
                                    │   │           │    │             │    │  Store)      │      │
                                    │   └───────────┘    └─────────────┘    └──────────────┘      │
                                    │                                                             │
                                    └─────────────────────────────────────────────────────────────┘
```

## Local Development Architecture

For local development and testing, we use a streamlined Docker Compose setup that includes all core components. This allows developers to work with the platform without requiring a full Kubernetes deployment.

### Local Components

The local development environment includes:

1. **Data Storage**
   - PostgreSQL: For metadata and offline feature storage
   - Redis: For online feature store
   - MinIO: S3-compatible storage for artifacts

2. **Messaging**
   - Kafka: For data streaming
   - Schema Registry: For data schema validation

3. **ML Components**
   - MLflow: For experiment tracking and model registry
   - Feature Registry API: For feature metadata management
   - Feature Store API: For feature storage and serving

### Local Architecture Diagram

```
┌───────────────────────────────────────────────────────┐
│                Docker Compose Environment              │
│                                                       │
│  ┌─────────────┐      ┌─────────────┐                 │
│  │             │      │             │                 │
│  │    Kafka    │─────▶│   Schema    │                 │
│  │             │      │   Registry  │                 │
│  └─────────────┘      └─────────────┘                 │
│                                                       │
│  ┌─────────────┐      ┌─────────────┐                 │
│  │             │      │             │                 │
│  │   MLflow    │◀────▶│    MinIO    │                 │
│  │             │      │             │                 │
│  └─────────────┘      └─────────────┘                 │
│                                                       │
│  ┌─────────────┐      ┌─────────────┐                 │
│  │  Feature    │      │   Feature   │                 │
│  │  Registry   │◀────▶│   Store     │                 │
│  │             │      │             │                 │
│  └─────────────┘      └─────────────┘                 │
│         ▲                    ▲                        │
│         │                    │                        │
│         ▼                    ▼                        │
│  ┌─────────────┐      ┌─────────────┐                 │
│  │             │      │             │                 │
│  │ PostgreSQL  │      │    Redis    │                 │
│  │             │      │             │                 │
│  └─────────────┘      └─────────────┘                 │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Management Tools

The local development environment is managed via a consolidated script (`mlops-platform.sh`) that provides commands for:

- Starting and stopping the platform
- Checking component status
- Viewing logs
- Running tests
- Cleaning up resources

For details on using this script, see the [Setup Guide](setup-guide.md#local-development-setup).

## Component Descriptions

### Data Infrastructure
- **Kafka**: Message broker for handling data streaming
- **Schema Registry**: Maintains and validates data schemas
- **Data Validation**: Ensures data quality and integrity

### Processing Infrastructure
- **Spark**: Distributed processing for data transformations and model training
- **Feature Engineering**: Creates and transforms features for ML models

### ML Infrastructure
- **MLflow**: Tracks experiments, parameters, and metrics
- **Model Registry**: Stores trained models with versioning
- **Model Serving**: Serves models for online prediction

### Orchestration
- **Airflow**: Orchestrates workflows and pipelines

### Storage
- **S3**: Stores ML artifacts, datasets, and models
- **PostgreSQL**: Stores metadata, experiment results
- **Redis**: In-memory store for feature serving

## Data Flow

1. External data sources send data to Kafka
2. Data is validated against schemas in Schema Registry
3. Feature engineering pipelines process the data
4. Training pipelines use Spark for distributed processing
5. Models are tracked with MLflow and stored in the Model Registry
6. Serving infrastructure exposes models for prediction
7. Airflow orchestrates the entire workflow

## Deployment Architecture

The platform is deployed on Kubernetes (EKS) with dedicated node groups:
- General: For control plane components
- Compute: For CPU/memory intensive workloads (Spark)
- Storage: For data-intensive components 