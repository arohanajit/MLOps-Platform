# Data Pipeline Test Suite

This test suite allows you to validate all components of the MLOps platform data pipeline:

1. **Event Logger Client Tests**: Validates the Kafka event logging client.
2. **CDC Tests**: Tests the change data capture process from PostgreSQL to Kafka using Debezium.
3. **Spark Tests**: Validates the Spark streaming job that processes events from Kafka.
4. **Storage Tests**: Tests the data storage and materialization between PostgreSQL and Redis.

## Prerequisites

Before running the tests, ensure you have the following:

1. A running Kubernetes cluster with access via `kubectl`
2. The MLOps platform infrastructure deployed via Terraform
3. Required Python dependencies installed (see below)

## Installation

Install the required dependencies:

```bash
pip install -r src/tests/requirements.txt
```

## Running Tests

You can run all tests at once or target specific components.

### Run All Tests

```bash
python src/tests/run_all_tests.py
```

### Test a Specific Component

```bash
# Test only the event logger client
python src/tests/run_all_tests.py --component client

# Test only the CDC component
python src/tests/run_all_tests.py --component cdc

# Test only the Spark processing
python src/tests/run_all_tests.py --component spark

# Test only the storage layer
python src/tests/run_all_tests.py --component storage
```

### Verbose Mode

Add the `--verbose` flag for more detailed logs:

```bash
python src/tests/run_all_tests.py --verbose
```

## Test Descriptions

### Event Logger Client Tests

Tests the `KafkaEventLogger` client with:
- Mock Kafka for offline testing
- Real Kafka connections if available
- Different event types and payload formats
- Error handling and edge cases

### CDC Tests

Tests the Debezium CDC process:
- Validates connector deployment and status
- Creates test data in PostgreSQL
- Verifies that data changes are captured in Kafka
- Monitors CDC events for completeness

### Spark Tests

Tests the Spark streaming job:
- Validates Spark job deployment
- Produces test events to Kafka
- Verifies event processing and transformation
- Checks if processed data appears in both PostgreSQL and Redis

### Storage Tests

Tests the storage layer:
- Validates PostgreSQL and Redis connections
- Tests the materialization job that syncs data between stores
- Inserts test data and verifies correct synchronization
- Tests features for different user profiles

## Log Files

Test results are logged to:
- Console output
- `data_pipeline_test_results.log` in the current directory

## Troubleshooting

- **Connection Issues**: Ensure all services are running in the Kubernetes cluster
- **Authentication Errors**: Check environment variables for database and Kafka credentials
- **Deployment Problems**: Verify Kubernetes resources and configurations
- **Data Sync Issues**: Check for schema mismatches and connectivity between services

## Environment Variables

The tests use the following environment variables (with defaults):

```
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka-bootstrap.kafka.svc.cluster.local:9092
SCHEMA_REGISTRY_URL=http://schema-registry.kafka.svc.cluster.local:8081
KAFKA_CONNECT_URL=http://connect.kafka.svc.cluster.local:8083

# PostgreSQL
POSTGRES_HOST=postgresql.storage.svc.cluster.local
POSTGRES_PORT=5432
POSTGRES_USER=mlops
POSTGRES_PASSWORD=password
POSTGRES_DB=mlops

# Redis
REDIS_HOST=redis.storage.svc.cluster.local
REDIS_PORT=6379
```

You can override these by setting the corresponding environment variables. 