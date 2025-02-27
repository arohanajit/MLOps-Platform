# Model Serving Component

This component provides model serving capabilities for the MLOps Platform using Ray Serve and NGINX.

## Features

- Lightweight model serving optimized for t2.micro instances
- A/B testing support with traffic splitting
- Model versioning and deployment management
- API Gateway with NGINX for routing and load balancing
- Metrics logging and monitoring
- Health checks and readiness probes
- AWS Lambda compatibility considerations

## Architecture

The model serving infrastructure consists of the following components:

1. **NGINX API Gateway**: Routes requests to the appropriate model serving instances
2. **RayServe**: Serves ML models with efficient resource utilization
3. **MLflow Integration**: Loads models from the MLflow model registry
4. **Metrics Logger**: Logs request/response data and performance metrics

## Deployment

To deploy the model serving infrastructure:

```bash
# Deploy the entire infrastructure
./deploy-model-serving.sh

# For local testing with port forwarding
kubectl -n model-serving port-forward svc/nginx 8080:80
```

## API Usage

### Making Predictions

```python
import requests
import json

# Define the features for prediction
features = {
    "feature1": 0.5,
    "feature2": 1.2,
    "feature3": 0,
    "feature4": 3.7,
    "feature5": 2
}

# Send prediction request
response = requests.post(
    "http://localhost:8080/api/v1/predictions",
    json={"features": features},
    headers={"Content-Type": "application/json"}
)

# Print the prediction result
print(json.dumps(response.json(), indent=2))
```

### A/B Testing

To use the A/B testing endpoint:

```python
response = requests.post(
    "http://localhost:8080/api/v1/ab/predictions",
    json={"features": features},
    headers={"Content-Type": "application/json"}
)
```

### Direct Model Access

To access a specific model directly:

```python
# Model A
response = requests.post(
    "http://localhost:8080/api/v1/models/a/predictions",
    json={"features": features},
    headers={"Content-Type": "application/json"}
)

# Model B
response = requests.post(
    "http://localhost:8080/api/v1/models/b/predictions",
    json={"features": features},
    headers={"Content-Type": "application/json"}
)
```

## Demo Client

A demo client is provided for testing the model serving API:

```bash
# Run the demo client
python demo_client.py --host localhost --port 8080 --endpoint api/v1/predictions

# Test A/B endpoint
python demo_client.py --host localhost --port 8080 --endpoint api/v1/ab/predictions

# Run a benchmark
python demo_client.py --host localhost --port 8080 --num-requests 100 --delay 0.1
```

## AWS Lambda Compatibility

The model serving code is designed to be lightweight and can be adapted for AWS Lambda:

1. Package the serving code with dependencies using tools like `serverless-python-requirements`
2. Set up API Gateway in AWS to route requests to Lambda functions
3. Use Lambda layers for larger dependencies like XGBoost
4. Configure appropriate memory and timeout settings for your model

## Monitoring and Scaling

For production deployments:

1. Set up CloudWatch metrics and alarms for Lambda invocations
2. Use Lambda concurrency settings to control scaling
3. Consider using AWS SageMaker for managed model hosting in production
4. Implement proper logging and monitoring for model performance

## Requirements

- Kubernetes cluster
- kubectl configured to access the cluster
- MLflow tracking server
- Python 3.8+
- Dependencies: ray[serve], mlflow, fastapi, numpy, pandas, requests 