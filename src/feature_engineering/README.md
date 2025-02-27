# Feature Engineering & Management Module

This module implements the Feature Engineering & Management layer for the MLOps platform, optimized for AWS Free Tier usage.

## Components

1. **Feature Registry**: Metadata registry for feature definitions stored in PostgreSQL
2. **Feature Store**: Service for storing and retrieving feature values with online (Redis) and offline (PostgreSQL) stores
3. **Batch Feature Engineering**: Spark-based feature computation pipelines
4. **Feature Validation**: Quality validation framework with configurable validation rules
5. **Feature Materialization**: Synchronization between online and offline stores

## Architecture

The feature engineering architecture consists of the following components:

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│                 │   │                 │   │                 │
│  ML Training    │   │  ML Serving     │   │  Feature        │
│  Pipeline       │   │  API            │   │  Engineering    │
│                 │   │                 │   │  Pipelines      │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                      Feature Store API                      │
│                                                             │
└──────────────────┬───────────────────────┬─────────────────┘
                   │                       │
                   │                       │
         ┌─────────▼────────┐    ┌─────────▼────────┐
         │                  │    │                  │
         │  Online Store    │    │  Offline Store   │
         │  (Redis)         │    │  (PostgreSQL)    │
         │                  │    │                  │
         └──────────────────┘    └─────────┬────────┘
                                           │
                                           │
                                 ┌─────────▼────────┐
                                 │                  │
                                 │ Feature Registry │
                                 │ (PostgreSQL)     │
                                 │                  │
                                 └──────────────────┘
```

## Deployment

The components are deployed to Kubernetes using the scripts in the `kubernetes/feature-engineering` directory:

1. **Feature Registry**: Defined in `feature-registry.yaml`
2. **Feature Store**: Defined in `feature-store.yaml`
3. **Batch Feature Engineering**: Defined in `batch-feature-engineering.yaml`
4. **Feature Materialization**: Defined in `feature-materialization-job.yaml`

To deploy all components, run:

```bash
./deploy-feature-engineering.sh
```

## Local Development

To set up a local development environment, use Docker Compose:

```bash
docker-compose -f docker-compose-feature-eng.yml up -d
```

This will start PostgreSQL, Redis, Feature Registry API, and Feature Store API.

## Usage Examples

### Registering a Feature

```python
import requests

feature = {
    "name": "customer_purchase_count_30d",
    "description": "Number of purchases in the last 30 days",
    "entity_type": "customer",
    "value_type": "INTEGER",
    "source": "DERIVED",
    "category": "BEHAVIORAL",
    "frequency": "DAILY",
    "owner": "data_science_team",
    "tags": ["purchases", "engagement", "core"]
}

response = requests.post(
    "http://localhost:8000/features",
    json=feature
)
print(response.json())
```

### Storing Feature Values

```python
import requests

# Store a customer feature
feature_values = {
    "purchase_count_30d": 12,
    "avg_order_value": 49.99,
    "last_purchase_date": "2023-06-15T10:30:00Z"
}

response = requests.post(
    "http://localhost:8001/store/customer/12345",
    json=feature_values
)
print(response.json())
```

### Retrieving Feature Values

```python
import requests

# Get a customer feature
response = requests.get(
    "http://localhost:8001/get/customer/12345/purchase_count_30d"
)
print(response.json())

# Get multiple features
response = requests.get(
    "http://localhost:8001/get/customer/12345",
    params={"features": "purchase_count_30d,avg_order_value"}
)
print(response.json())
```

### Running Batch Feature Engineering

```bash
# Run Spark-based feature computation
kubectl create -f kubernetes/feature-engineering/batch-feature-engineering-job.yaml
```

## Feature Management Best Practices

1. **Feature Versioning**: Each feature has a version history tracked in the Feature Registry
2. **Feature Validation**: Use the validation framework to ensure data quality
3. **Documentation**: Thoroughly document all features with descriptions and metadata
4. **Feature Reuse**: Organize related features into feature groups for better reusability
5. **Monitoring**: Set up alerts for feature drift and data quality issues

## AWS Free Tier Considerations

This implementation is optimized for AWS Free Tier with the following considerations:

1. **Resource Usage**: Spark jobs are configured with minimal resource requirements
2. **Storage Optimization**: Features are stored efficiently with TTL for online storage
3. **Scheduled Jobs**: Batch processing is scheduled to minimize compute costs

## Limitations and Future Improvements

1. **Scaling**: For production use beyond AWS Free Tier, consider using AWS Feature Store
2. **Real-time Features**: Add support for real-time feature transformations
3. **Feature Selection**: Implement automated feature selection based on importance
4. **Model Integration**: Tighter integration with model training and serving 