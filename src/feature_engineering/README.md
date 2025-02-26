# Feature Engineering System

This directory contains the components for the Feature Engineering system of the MLOps platform. The Feature Engineering system enables data scientists and ML engineers to define, compute, store, and serve features for machine learning models.

## Components

The Feature Engineering system consists of the following components:

1. **Feature Registry**: Centralized metadata store for feature definitions
2. **Feature Store**: Online and offline storage for feature values
3. **Feature Pipeline**: Batch and streaming pipelines for computing features
4. **Feature API**: REST API for retrieving feature values for model training and inference

## Architecture

![Feature Engineering Architecture](../../docs/images/feature-engineering-architecture.png)

The Feature Engineering system uses a two-tier architecture:

- **Online Store**: Redis is used for low-latency access to feature values during model inference
- **Offline Store**: PostgreSQL is used for storing historical feature values for model training

## Getting Started

### Feature Registry API

The Feature Registry API allows you to define and discover features:

```bash
# Create a new feature
curl -X POST http://localhost/api/feature-registry/features \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer_total_purchases_30d",
    "description": "Total purchase amount by customer in last 30 days",
    "entity_type": "customer",
    "value_type": "FLOAT",
    "source": "BATCH",
    "category": "DERIVED",
    "frequency": "DAILY",
    "owner": "data-science-team",
    "tags": ["purchase", "monetary", "customer_360"],
    "source_config": {
      "table": "customer_purchases",
      "filter": "purchase_date >= NOW() - INTERVAL '\''30 days'\''"
    },
    "transformations": [
      {
        "type": "aggregation",
        "function": "sum",
        "column": "purchase_amount"
      }
    ]
  }'

# Get feature details
curl http://localhost/api/feature-registry/features/customer_total_purchases_30d

# List all features
curl http://localhost/api/feature-registry/features

# Create a feature group
curl -X POST http://localhost/api/feature-registry/feature-groups \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer_rfm_features",
    "description": "RFM (Recency, Frequency, Monetary) features for customer segmentation",
    "feature_names": [
      "customer_days_since_last_purchase",
      "customer_purchase_frequency_30d",
      "customer_total_purchases_30d"
    ],
    "entity_type": "customer",
    "owner": "data-science-team",
    "tags": ["rfm", "segmentation", "customer_360"]
  }'
```

### Feature Store API

The Feature Store API enables access to feature values:

```bash
# Get feature values for an entity
curl -X POST http://localhost/api/feature-store/features \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "customer123",
    "feature_names": [
      "customer_total_purchases_30d",
      "customer_days_since_last_purchase",
      "customer_purchase_frequency_30d"
    ],
    "entity_type": "customer"
  }'

# Get feature values for multiple entities
curl -X POST http://localhost/api/feature-store/batch-features \
  -H "Content-Type: application/json" \
  -d '{
    "entity_ids": ["customer123", "customer456", "customer789"],
    "feature_names": [
      "customer_total_purchases_30d",
      "customer_days_since_last_purchase",
      "customer_purchase_frequency_30d"
    ],
    "entity_type": "customer"
  }'

# Get historical feature values
curl -X POST http://localhost/api/feature-store/historical-features \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "customer123",
    "feature_names": [
      "customer_total_purchases_30d",
      "customer_days_since_last_purchase"
    ],
    "entity_type": "customer",
    "start_time": "2023-01-01T00:00:00Z",
    "end_time": "2023-04-01T00:00:00Z",
    "limit": 100
  }'
```

### Batch Feature Pipeline

The Batch Feature Pipeline computes features on a schedule:

```bash
# Run manually with specific feature types
python batch_pipeline.py --feature-types=customer,product --lookback-days=30

# Kubernetes job
kubectl apply -f ../../kubernetes/feature-engineering/batch-feature-engineering.yaml
```

## Adding a New Feature

To add a new feature to the system:

1. Define the feature in the Feature Registry
2. Add feature computation logic to the appropriate pipeline
3. Test the feature by running the pipeline
4. Update your model code to use the new feature

Example:

```python
import requests

# Register the feature
feature_data = {
    "name": "customer_average_purchase_amount",
    "description": "Average purchase amount by customer",
    "entity_type": "customer",
    "value_type": "FLOAT",
    "source": "BATCH",
    "category": "DERIVED",
    "frequency": "DAILY",
    "owner": "data-science-team",
    "tags": ["purchase", "monetary"],
    "source_config": {
        "table": "customer_purchases"
    },
    "transformations": [
        {
            "type": "aggregation",
            "function": "avg",
            "column": "purchase_amount"
        }
    ]
}

response = requests.post(
    "http://localhost/api/feature-registry/features",
    json=feature_data
)
print(response.json())
```

## Kubernetes Deployment

The Feature Engineering system is deployed as Kubernetes services:

```bash
# Deploy the Feature Registry
kubectl apply -f ../../kubernetes/feature-engineering/feature-registry.yaml

# Deploy the Feature Store
kubectl apply -f ../../kubernetes/feature-engineering/feature-store.yaml

# Deploy the Batch Feature Pipeline
kubectl apply -f ../../kubernetes/feature-engineering/batch-feature-engineering.yaml
```

## Dependencies

- PostgreSQL: Used for offline feature storage and metadata
- Redis: Used for online feature serving
- Apache Spark: Used for feature computation
- Kubernetes: Used for orchestration and scheduling

## Monitoring

The Feature Engineering system exposes metrics through the Prometheus endpoints:

- `/metrics` endpoint on each service
- Grafana dashboards for Feature Store and Registry monitoring
- Airflow DAGs for monitoring feature computation jobs

## Troubleshooting

Common issues:

1. **Missing features**: Ensure the feature has been registered and computed
2. **Slow feature retrieval**: Check Redis CPU and memory usage
3. **Failed batch jobs**: Check Kubernetes pod logs for errors
4. **Inconsistent feature values**: Verify the feature computation logic

For more information, see the [MLOps Platform Documentation](../../docs/README.md). 