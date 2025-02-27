#!/usr/bin/env python3
"""
Model serving script using Ray Serve.

This script loads a model from MLflow registry and deploys it using Ray Serve.
It is optimized for lightweight deployment on t2.micro instances.
"""
import os
import sys
import time
import argparse
import logging
import json
from typing import Dict, Any, Optional, List, Union
import uuid

import numpy as np
import pandas as pd
import mlflow
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import ray
from ray import serve

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import local modules
from src.model_serving.utils.mlflow_utils import load_model_from_registry, get_model_info
from src.model_serving.utils.metrics_logger import MetricsLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/model_serving.log')
    ]
)
logger = logging.getLogger("ModelServing")

# Create the FastAPI app
app = FastAPI(title="MLOps Platform Model Serving")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class ModelPredictor:
    """Model predictor class for serving ML models."""
    
    def __init__(self, model_name: str, version: str, serving_name: str = "default"):
        """
        Initialize the model predictor.
        
        Args:
            model_name: Name of the model in MLflow registry
            version: Version or stage of the model
            serving_name: Name for the serving deployment
        """
        self.model_name = model_name
        self.version = version
        self.serving_name = serving_name
        self.model = None
        self.model_info = None
        self.metrics_logger = MetricsLogger(
            model_name=model_name,
            version=version,
            log_file="/tmp/model_serving_metrics.log"
        )
        
        # Load the model
        self.load_model()
        
    def load_model(self) -> None:
        """Load the model from MLflow model registry."""
        try:
            logger.info(f"Loading model {self.model_name} version {self.version}")
            self.model = load_model_from_registry(self.model_name, self.version)
            self.model_info = get_model_info(self.model_name, self.version)
            logger.info(f"Model {self.model_name} version {self.version} loaded successfully")
            self.metrics_logger.log_model_loaded()
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            self.metrics_logger.log_model_load_failed(e)
            raise
    
    async def predict(self, request: Request) -> Dict[str, Any]:
        """
        Handle prediction requests.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Prediction response dictionary
        """
        # Generate a request ID
        request_id = str(uuid.uuid4())
        
        # Parse request body
        try:
            body = await request.json()
            features = body.get("features", {})
            
            # Log request start
            self.metrics_logger.start_request(request_id, features)
            
            # Convert features to DataFrame for prediction
            # This assumes the model expects a DataFrame, adjust as needed
            if isinstance(features, dict):
                # Single row prediction
                df = pd.DataFrame([features])
            elif isinstance(features, list) and all(isinstance(item, dict) for item in features):
                # Batch prediction
                df = pd.DataFrame(features)
            else:
                raise ValueError("Invalid features format. Expected a dictionary or list of dictionaries.")
            
            # Make prediction
            prediction = self.model.predict(df)
            
            # Convert numpy arrays to lists for JSON serialization
            if isinstance(prediction, np.ndarray):
                prediction_result = prediction.tolist()
            else:
                prediction_result = prediction
            
            # Log request end and get latency
            latency_ms = self.metrics_logger.end_request(prediction_result)
            
            # Prepare response
            response = {
                "prediction": prediction_result,
                "model_info": {
                    "name": self.model_name,
                    "version": self.version,
                    "timestamp": time.time()
                },
                "request_id": request_id,
                "latency_ms": latency_ms
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            self.metrics_logger.log_error(e, request_id)
            return {
                "error": str(e),
                "model_info": {
                    "name": self.model_name,
                    "version": self.version,
                    "timestamp": time.time()
                },
                "request_id": request_id
            }

def create_predictor_deployment(
    model_name: str,
    version: str,
    serving_name: str = "default",
    num_replicas: int = 1
) -> serve.Deployment:
    """
    Create a Ray Serve deployment for model prediction.
    
    Args:
        model_name: Name of the model in MLflow registry
        version: Version or stage of the model
        serving_name: Name for the serving deployment
        num_replicas: Number of replicas to deploy
        
    Returns:
        Ray Serve deployment
    """
    # Define the deployment
    deployment = serve.deployment(
        name=f"predictor-{serving_name}",
        route_prefix="/predictions",
        num_replicas=num_replicas,
        ray_actor_options={
            "num_cpus": 1,  # Limit to 1 CPU for t2.micro
            "num_gpus": 0,  # No GPU
            "memory": 512 * 1024 * 1024,  # 512 MB memory limit
        }
    )(ModelPredictor)
    
    # Deploy with the specified model
    handle = deployment.deploy(model_name, version, serving_name)
    
    logger.info(f"Deployment {serving_name} created with model {model_name} version {version}")
    return deployment

@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "MLOps Platform Model Serving API",
        "version": "1.0.0",
        "endpoints": {
            "predictions": "POST /predictions - Make a prediction",
            "health": "GET /healthz - Health check"
        }
    }

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Model Serving Script")
    parser.add_argument("--model-name", type=str, required=True, 
                        help="Name of the model in MLflow registry")
    parser.add_argument("--version", type=str, required=True, 
                        help="Version or stage of the model")
    parser.add_argument("--serving-name", type=str, default="default",
                        help="Name for the serving deployment")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to run the server on")
    parser.add_argument("--replicas", type=int, default=1,
                        help="Number of replicas")
    parser.add_argument("--mlflow-uri", type=str, 
                        default=os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service:5000"),
                        help="MLflow tracking URI")
    
    args = parser.parse_args()
    
    # Initialize Ray
    ray.init(num_cpus=2, ignore_reinit_error=True)
    
    # Set MLflow tracking URI
    mlflow.set_tracking_uri(args.mlflow_uri)
    
    # Start Ray Serve
    serve.start(detached=True, http_options={"host": "0.0.0.0", "port": args.port})
    
    # Deploy the model
    create_predictor_deployment(
        model_name=args.model_name,
        version=args.version,
        serving_name=args.serving_name,
        num_replicas=args.replicas
    )
    
    logger.info(f"Model serving API running at http://localhost:{args.port}/predictions")
    
    # Keep the script running
    while True:
        time.sleep(3600)  # Sleep for an hour

if __name__ == "__main__":
    main()