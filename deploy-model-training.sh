#!/bin/bash
set -e

# Model Training Infrastructure Deployment Script
echo "===== Model Training Infrastructure Deployment ====="
echo "This script will deploy MLflow, Jupyter, and Ray for model training"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed. Please install it first."
    exit 1
fi

# Check if we can connect to Kubernetes cluster
if ! kubectl get nodes &> /dev/null; then
    echo "Error: Unable to connect to Kubernetes cluster. Please ensure k3s is running."
    exit 1
fi

# Create namespaces if they don't exist
echo "Setting up namespaces..."
kubectl apply -f kubernetes/namespaces.yaml

# Set up Postgres database for MLflow if not already done
echo "Checking PostgreSQL for MLflow..."
if ! kubectl get pod -n storage | grep -q postgres; then
    echo "PostgreSQL not found in storage namespace. Please run deploy-storage-layer.sh first"
    exit 1
fi

# Create MLflow database
echo "Creating MLflow database in PostgreSQL..."
kubectl exec -n storage deploy/postgres -- psql -U postgres -c "CREATE DATABASE mlflow;" 2>/dev/null || echo "Database mlflow already exists"

# Deploy MLflow
echo "Deploying MLflow tracking server..."
# Update S3 credentials with actual values
# echo "Please enter your AWS Access Key ID for S3 storage:"
# read -s aws_access_key_id
# echo "Please enter your AWS Secret Access Key for S3 storage:"
# read -s aws_secret_access_key

# For demo purposes, we'll use placeholder values - replace these in production!
aws_access_key_id="AKIAIOSFODNN7EXAMPLE"  
aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Create base64 encoded secrets
aws_access_key_id_base64=$(echo -n "$aws_access_key_id" | base64)
aws_secret_access_key_base64=$(echo -n "$aws_secret_access_key" | base64)

# Update secrets in MLflow YAML
sed -i.bak "s/aws_access_key_id: .*/aws_access_key_id: $aws_access_key_id_base64/g" kubernetes/mlflow/mlflow.yaml
sed -i.bak "s/aws_secret_access_key: .*/aws_secret_access_key: $aws_secret_access_key_base64/g" kubernetes/mlflow/mlflow.yaml

# Apply MLflow configuration
kubectl apply -f kubernetes/mlflow/mlflow.yaml

echo "Waiting for MLflow to start..."
kubectl rollout status deployment/mlflow -n mlflow --timeout=300s

# Deploy model registry
echo "Deploying model registry..."
kubectl apply -f kubernetes/model-training/model-registry.yaml

echo "Waiting for model registry to start..."
kubectl rollout status deployment/model-registry -n model-training --timeout=300s

# Optimize and deploy Ray cluster for t2.micro instances
echo "Optimizing Ray cluster configuration for t2.micro instances..."

# Create a temporary optimized Ray cluster configuration
cat << EOF > kubernetes/model-training/ray-cluster-optimized.yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: raycluster
  namespace: model-training
spec:
  headGroupSpec:
    rayStartParams:
      dashboard-host: "0.0.0.0"
      num-cpus: "1"
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.6.3-py310
          ports:
          - containerPort: 6379
            name: gcs
          - containerPort: 8265
            name: dashboard
          - containerPort: 10001
            name: client
          resources:
            limits:
              cpu: 1
              memory: 1Gi
            requests:
              cpu: 500m
              memory: 512Mi
          env:
          - name: MLFLOW_TRACKING_URI
            value: "http://mlflow.mlflow.svc.cluster.local:5000"
          volumeMounts:
          - name: ray-shared
            mountPath: /shared
        volumes:
        - name: ray-shared
          persistentVolumeClaim:
            claimName: ray-shared-pvc
  workerGroupSpecs:
    - replicas: 2
      minReplicas: 0
      maxReplicas: 3
      groupName: small-workers
      rayStartParams:
        num-cpus: "1"
      template:
        spec:
          containers:
          - name: ray-worker
            image: rayproject/ray:2.6.3-py310
            resources:
              limits:
                cpu: 1
                memory: 1Gi
              requests:
                cpu: 500m
                memory: 512Mi
            env:
            - name: MLFLOW_TRACKING_URI
              value: "http://mlflow.mlflow.svc.cluster.local:5000"
            volumeMounts:
            - name: ray-shared
              mountPath: /shared
          volumes:
          - name: ray-shared
            persistentVolumeClaim:
              claimName: ray-shared-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: ray-head
  namespace: model-training
spec:
  selector:
    ray.io/node-type: head
    ray.io/cluster: raycluster
  ports:
  - port: 10001
    name: client
    targetPort: 10001
  - port: 8265
    name: dashboard
    targetPort: 8265
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ray-shared-pvc
  namespace: model-training
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 5Gi
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ray-dashboard-ingress
  namespace: model-training
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  rules:
  - host: ray.mlops.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ray-head
            port:
              number: 8265
EOF

# Deploy the optimized Ray cluster
echo "Deploying optimized Ray cluster..."
kubectl apply -f kubernetes/model-training/ray-cluster-optimized.yaml

# Deploy Jupyter notebook
echo "Deploying Jupyter notebook server..."
kubectl apply -f kubernetes/jupyter/jupyter.yaml

echo "Waiting for Jupyter to start..."
kubectl rollout status deployment/jupyter -n model-training --timeout=300s

# Create example notebook with training pipeline
echo "Creating example notebook with MLflow tracking and Ray integration..."
cat << EOF > src/model_training/notebooks/mlflow_ray_training_example.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# MLflow and Ray Training Example\n",
    "\n",
    "This notebook demonstrates how to use MLflow for experiment tracking and Ray for distributed training."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Install required packages\n",
    "!pip install mlflow ray[tune] pandas scikit-learn xgboost"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import mlflow\n",
    "import ray\n",
    "from ray import tune\n",
    "from ray.tune.integration.mlflow import MLflowLoggerCallback\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "from sklearn.datasets import load_diabetes\n",
    "from sklearn.model_selection import train_test_split\n",
    "from sklearn.metrics import mean_squared_error\n",
    "import xgboost as xgb\n",
    "import os"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Connect to MLflow tracking server\n",
    "# This is set automatically via MLFLOW_TRACKING_URI environment variable\n",
    "print(f\"MLflow tracking URI: {mlflow.get_tracking_uri()}\")\n",
    "\n",
    "# Set experiment\n",
    "mlflow.set_experiment(\"diabetes-regression\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Load and prepare data\n",
    "diabetes = load_diabetes()\n",
    "X = diabetes.data\n",
    "y = diabetes.target\n",
    "\n",
    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n",
    "\n",
    "# Convert to DMatrix\n",
    "dtrain = xgb.DMatrix(X_train, label=y_train)\n",
    "dtest = xgb.DMatrix(X_test, label=y_test)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Initialize Ray (connect to existing cluster)\n",
    "ray.init(address=\"ray://ray-head.model-training.svc.cluster.local:10001\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Define training function\n",
    "def train_xgboost(config):\n",
    "    # XGBoost parameters\n",
    "    params = {\n",
    "        \"objective\": \"reg:squarederror\",\n",
    "        \"eval_metric\": \"rmse\",\n",
    "        \"max_depth\": config[\"max_depth\"],\n",
    "        \"eta\": config[\"eta\"],\n",
    "        \"subsample\": config[\"subsample\"],\n",
    "        \"colsample_bytree\": config[\"colsample_bytree\"]\n",
    "    }\n",
    "    \n",
    "    # Train model\n",
    "    results = {}\n",
    "    model = xgb.train(\n",
    "        params,\n",
    "        dtrain,\n",
    "        num_boost_round=config[\"num_boost_round\"],\n",
    "        evals=[(dtrain, \"train\"), (dtest, \"test\")],\n",
    "        evals_result=results,\n",
    "        verbose_eval=False\n",
    "    )\n",
    "    \n",
    "    # Evaluate\n",
    "    y_pred = model.predict(dtest)\n",
    "    rmse = np.sqrt(mean_squared_error(y_test, y_pred))\n",
    "    \n",
    "    # Log metrics to Tune\n",
    "    tune.report(rmse=rmse)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Configure hyperparameter search space (reduced for t2.micro instances)\n",
    "search_space = {\n",
    "    \"max_depth\": tune.randint(3, 8),\n",
    "    \"eta\": tune.loguniform(1e-4, 1e-1),\n",
    "    \"subsample\": tune.uniform(0.5, 1.0),\n",
    "    \"colsample_bytree\": tune.uniform(0.5, 1.0),\n",
    "    \"num_boost_round\": tune.randint(50, 100)\n",
    "}"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Configure tuning with MLflow logging\n",
    "analysis = tune.run(\n",
    "    train_xgboost,\n",
    "    config=search_space,\n",
    "    num_samples=4,  # Reduced for t2.micro\n",
    "    callbacks=[MLflowLoggerCallback(\n",
    "        experiment_name=\"diabetes-regression\",\n",
    "        tracking_uri=mlflow.get_tracking_uri()\n",
    "    )],\n",
    "    resources_per_trial={\"cpu\": 1, \"memory\": 512 * 1024 * 1024}  # Resource constraints\n",
    ")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Get best hyperparameters\n",
    "best_config = analysis.get_best_config(metric=\"rmse\", mode=\"min\")\n",
    "print(\"Best hyperparameters:\", best_config)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Train final model with best hyperparameters\n",
    "with mlflow.start_run(run_name=\"best_model\"):\n",
    "    # Log hyperparameters\n",
    "    for param, value in best_config.items():\n",
    "        mlflow.log_param(param, value)\n",
    "    \n",
    "    # XGBoost parameters\n",
    "    params = {\n",
    "        \"objective\": \"reg:squarederror\",\n",
    "        \"eval_metric\": \"rmse\",\n",
    "        \"max_depth\": best_config[\"max_depth\"],\n",
    "        \"eta\": best_config[\"eta\"],\n",
    "        \"subsample\": best_config[\"subsample\"],\n",
    "        \"colsample_bytree\": best_config[\"colsample_bytree\"]\n",
    "    }\n",
    "    \n",
    "    # Train model\n",
    "    results = {}\n",
    "    model = xgb.train(\n",
    "        params,\n",
    "        dtrain,\n",
    "        num_boost_round=best_config[\"num_boost_round\"],\n",
    "        evals=[(dtrain, \"train\"), (dtest, \"test\")],\n",
    "        evals_result=results,\n",
    "        verbose_eval=False\n",
    "    )\n",
    "    \n",
    "    # Evaluate\n",
    "    y_pred = model.predict(dtest)\n",
    "    rmse = np.sqrt(mean_squared_error(y_test, y_pred))\n",
    "    \n",
    "    # Log metrics\n",
    "    mlflow.log_metric(\"rmse\", rmse)\n",
    "    \n",
    "    # Log model\n",
    "    mlflow.xgboost.log_model(model, \"model\")\n",
    "    \n",
    "    # Register model\n",
    "    model_uri = f\"runs:/{mlflow.active_run().info.run_id}/model\"\n",
    "    model_details = mlflow.register_model(model_uri, \"diabetes-predictor\")\n",
    "    \n",
    "    print(f\"Model registered: {model_details.name} version {model_details.version}\")\n",
    "    print(f\"RMSE: {rmse}\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.12"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

# Create training pipeline utilities
echo "Creating training pipeline utilities..."
mkdir -p src/model_training/training/utils

cat << EOF > src/model_training/training/utils/mlflow_utils.py
"""
MLflow utilities for model training.
"""
import os
import mlflow
from mlflow.tracking import MlflowClient
from typing import Dict, Any, Optional, List, Tuple

def setup_mlflow_experiment(experiment_name: str) -> str:
    """
    Set up an MLflow experiment.
    
    Args:
        experiment_name: Name of the experiment
        
    Returns:
        experiment_id: ID of the experiment
    """
    # Get MLflow tracking URI from environment or use default
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000")
    mlflow.set_tracking_uri(tracking_uri)
    
    # Set or create experiment
    experiment = mlflow.set_experiment(experiment_name)
    
    return experiment.experiment_id

def log_model_to_registry(
    model_name: str, 
    run_id: str, 
    model_path: str = "model", 
    stage: str = "None"
) -> Tuple[str, int]:
    """
    Register a model in the MLflow model registry.
    
    Args:
        model_name: Name of the model in registry
        run_id: MLflow run ID where model is logged
        model_path: Path to model in the artifacts
        stage: Stage to assign to the model version (None, Staging, Production, Archived)
        
    Returns:
        tuple: (model name, model version)
    """
    client = MlflowClient()
    
    # Register model
    model_uri = f"runs:/{run_id}/{model_path}"
    model_version = mlflow.register_model(model_uri, model_name)
    
    # Set stage if specified
    if stage != "None":
        client.transition_model_version_stage(
            name=model_name,
            version=model_version.version,
            stage=stage
        )
    
    return model_name, model_version.version

def compare_runs(
    experiment_name: str, 
    metric_name: str, 
    max_results: int = 5,
    ascending: bool = True
) -> List[Dict[str, Any]]:
    """
    Compare runs in an experiment based on a metric.
    
    Args:
        experiment_name: Name of the experiment
        metric_name: Name of the metric to compare
        max_results: Maximum number of results to return
        ascending: Sort in ascending order if True
        
    Returns:
        list: List of runs with their metrics
    """
    client = MlflowClient()
    
    # Get experiment ID
    experiment = client.get_experiment_by_name(experiment_name)
    if not experiment:
        raise ValueError(f"Experiment '{experiment_name}' not found")
    
    # Get all runs
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="",
        max_results=max_results
    )
    
    # Sort runs by metric
    runs = sorted(
        runs,
        key=lambda run: run.data.metrics.get(metric_name, float('inf' if ascending else '-inf')),
        reverse=not ascending
    )
    
    # Format results
    results = []
    for run in runs:
        result = {
            "run_id": run.info.run_id,
            "run_name": run.info.run_name,
            f"{metric_name}": run.data.metrics.get(metric_name, None),
            "parameters": run.data.params
        }
        results.append(result)
    
    return results
EOF

cat << EOF > src/model_training/training/utils/ray_utils.py
"""
Ray utilities for distributed training.
"""
import os
import ray
from typing import Dict, Any, Optional, Callable, List, Tuple

def connect_to_ray_cluster(address: Optional[str] = None) -> None:
    """
    Connect to a Ray cluster.
    
    Args:
        address: Ray cluster address (defaults to ray head service)
    """
    if address is None:
        address = "ray://ray-head.model-training.svc.cluster.local:10001"
    
    ray.init(address=address, ignore_reinit_error=True)
    
def resource_constrained_config(cpu_per_trial: float = 1.0, memory_mb_per_trial: int = 512) -> Dict[str, Any]:
    """
    Create a resource-constrained configuration for Ray Tune.
    
    Args:
        cpu_per_trial: CPU cores per trial
        memory_mb_per_trial: Memory in MB per trial
        
    Returns:
        dict: Configuration dictionary
    """
    return {
        "resources_per_trial": {
            "cpu": cpu_per_trial,
            "memory": memory_mb_per_trial * 1024 * 1024  # Convert to bytes
        },
        "num_samples": 4,  # Reduced number of samples
        "max_concurrent_trials": 2,  # Limit concurrent trials
        "checkpoint_freq": 0,  # Disable checkpointing to save storage
        "verbose": 1
    }
EOF

# Create a training pipeline example
cat << EOF > src/model_training/training/train_model.py
"""
Example of a training pipeline using MLflow and Ray.
"""
import os
import argparse
import mlflow
import ray
from ray import tune
from ray.tune.integration.mlflow import MLflowLoggerCallback
import pandas as pd
import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import xgboost as xgb

from src.model_training.training.utils.mlflow_utils import setup_mlflow_experiment, log_model_to_registry
from src.model_training.training.utils.ray_utils import connect_to_ray_cluster, resource_constrained_config

def load_data():
    """Load and prepare diabetes dataset."""
    diabetes = load_diabetes()
    X = diabetes.data
    y = diabetes.target
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Convert to DMatrix for XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)
    
    return dtrain, dtest, X_test, y_test

def train_xgboost(config, dtrain, dtest, y_test):
    """Train an XGBoost model with given configuration."""
    # XGBoost parameters
    params = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "max_depth": config["max_depth"],
        "eta": config["eta"],
        "subsample": config["subsample"],
        "colsample_bytree": config["colsample_bytree"]
    }
    
    # Train model
    results = {}
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=config["num_boost_round"],
        evals=[(dtrain, "train"), (dtest, "test")],
        evals_result=results,
        verbose_eval=False
    )
    
    # Evaluate
    y_pred = model.predict(dtest)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    # Log metrics to Tune
    tune.report(rmse=rmse)

def main(args):
    # Setup MLflow
    experiment_id = setup_mlflow_experiment(args.experiment_name)
    print(f"MLflow experiment: {args.experiment_name} (ID: {experiment_id})")
    
    # Connect to Ray cluster
    if args.use_ray:
        connect_to_ray_cluster()
        print("Connected to Ray cluster")
    
    # Load data
    dtrain, dtest, X_test, y_test = load_data()
    print("Data loaded")
    
    if args.use_ray:
        # Configure hyperparameter search space
        search_space = {
            "max_depth": tune.randint(3, 8),
            "eta": tune.loguniform(1e-4, 1e-1),
            "subsample": tune.uniform(0.5, 1.0),
            "colsample_bytree": tune.uniform(0.5, 1.0),
            "num_boost_round": tune.randint(50, 100)
        }
        
        # Get resource-constrained configuration
        tune_config = resource_constrained_config(
            cpu_per_trial=args.cpu_per_trial,
            memory_mb_per_trial=args.memory_per_trial
        )
        
        # Configure tuning with MLflow logging
        print("Starting hyperparameter tuning...")
        
        # Function to train with fixed data
        def train_wrapper(config):
            train_xgboost(config, dtrain, dtest, y_test)
        
        analysis = tune.run(
            train_wrapper,
            config=search_space,
            **tune_config,
            callbacks=[MLflowLoggerCallback(
                experiment_name=args.experiment_name,
                tracking_uri=mlflow.get_tracking_uri()
            )]
        )
        
        # Get best hyperparameters
        best_config = analysis.get_best_config(metric="rmse", mode="min")
        print("Best hyperparameters:", best_config)
        
        # Train final model with best hyperparameters
        with mlflow.start_run(run_name="best_model") as run:
            # Log hyperparameters
            for param, value in best_config.items():
                mlflow.log_param(param, value)
            
            # XGBoost parameters
            params = {
                "objective": "reg:squarederror",
                "eval_metric": "rmse",
                "max_depth": best_config["max_depth"],
                "eta": best_config["eta"],
                "subsample": best_config["subsample"],
                "colsample_bytree": best_config["colsample_bytree"]
            }
            
            # Train model
            results = {}
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=best_config["num_boost_round"],
                evals=[(dtrain, "train"), (dtest, "test")],
                evals_result=results,
                verbose_eval=False
            )
            
            # Evaluate
            y_pred = model.predict(dtest)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            
            # Log metrics
            mlflow.log_metric("rmse", rmse)
            
            # Log model
            mlflow.xgboost.log_model(model, "model")
            
            if args.register_model:
                # Register model
                model_name, model_version = log_model_to_registry(
                    model_name=args.model_name,
                    run_id=run.info.run_id,
                    model_path="model",
                    stage="Staging"
                )
                print(f"Model registered: {model_name} version {model_version}")
            
            print(f"RMSE: {rmse}")
    else:
        # Train a simple model without Ray
        with mlflow.start_run(run_name="simple_model") as run:
            # Simple hyperparameters
            params = {
                "objective": "reg:squarederror",
                "eval_metric": "rmse",
                "max_depth": 5,
                "eta": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8
            }
            
            # Log hyperparameters
            for param, value in params.items():
                mlflow.log_param(param, value)
            
            # Also log num_boost_round
            num_boost_round = 100
            mlflow.log_param("num_boost_round", num_boost_round)
            
            # Train model
            results = {}
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=num_boost_round,
                evals=[(dtrain, "train"), (dtest, "test")],
                evals_result=results,
                verbose_eval=False
            )
            
            # Evaluate
            y_pred = model.predict(dtest)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            
            # Log metrics
            mlflow.log_metric("rmse", rmse)
            
            # Log model
            mlflow.xgboost.log_model(model, "model")
            
            if args.register_model:
                # Register model
                model_name, model_version = log_model_to_registry(
                    model_name=args.model_name,
                    run_id=run.info.run_id,
                    model_path="model",
                    stage="Staging"
                )
                print(f"Model registered: {model_name} version {model_version}")
            
            print(f"RMSE: {rmse}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a model with MLflow tracking and Ray tuning")
    parser.add_argument("--experiment-name", type=str, default="diabetes-regression", help="MLflow experiment name")
    parser.add_argument("--model-name", type=str, default="diabetes-predictor", help="Model name for registry")
    parser.add_argument("--use-ray", action="store_true", help="Use Ray for hyperparameter tuning")
    parser.add_argument("--register-model", action="store_true", help="Register model in MLflow registry")
    parser.add_argument("--cpu-per-trial", type=float, default=1.0, help="CPU cores per trial")
    parser.add_argument("--memory-per-trial", type=int, default=512, help="Memory in MB per trial")
    
    args = parser.parse_args()
    main(args)
EOF

# Create requirements.txt for the model training environment
cat << EOF > src/model_training/requirements.txt
# Ray and MLflow
ray[tune]==2.6.3
mlflow==2.8.0
hyperopt==0.2.7

# Data processing and ML
pandas==2.0.3
numpy==1.24.3
scikit-learn==1.3.0
xgboost==1.7.6

# AWS and database support
boto3==1.26.146
psycopg2-binary==2.9.6

# Jupyter integration
ipykernel==6.25.0
matplotlib==3.7.2
seaborn==0.12.2
EOF

# Display information about accessing components
echo "===== Model Training Infrastructure Deployment Complete ====="
echo ""
echo "To access the services locally, run the following port-forwarding commands:"
echo ""
echo "MLflow Tracking Server:"
echo "kubectl port-forward -n mlflow svc/mlflow 5000:5000"
echo "Then visit: http://localhost:5000"
echo ""
echo "Model Registry:"
echo "kubectl port-forward -n model-training svc/model-registry 8080:8080"
echo "Then visit: http://localhost:8080"
echo ""
echo "Jupyter Notebook Server:"
echo "kubectl port-forward -n model-training svc/jupyter 8888:8888"
echo "Then visit: http://localhost:8888"
echo ""
echo "Ray Dashboard:"
echo "kubectl port-forward -n model-training svc/ray-head 8265:8265"
echo "Then visit: http://localhost:8265"
echo ""
echo "To run a training pipeline:"
echo "1. Forward the necessary ports"
echo "2. Run the following command:"
echo "   python -m src.model_training.training.train_model --use-ray --register-model"
echo ""
echo "For on-demand scaling of Ray workers, update the Ray cluster configuration:"
echo "kubectl edit rayCluster/raycluster -n model-training" 