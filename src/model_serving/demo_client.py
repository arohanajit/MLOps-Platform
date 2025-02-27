#!/usr/bin/env python3
"""
Demo client for testing the model serving API.

This script sends sample prediction requests to the model serving API
and displays the results.
"""
import json
import sys
import time
import logging
import argparse
import random
from typing import Dict, Any, List
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ModelServingClient")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Model Serving Demo Client")
    parser.add_argument(
        "--host", 
        type=str, 
        default="localhost",
        help="API host"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=80, 
        help="API port"
    )
    parser.add_argument(
        "--endpoint", 
        type=str, 
        default="api/v1/predictions",
        choices=["api/v1/predictions", "api/v1/ab/predictions", 
                "api/v1/models/a/predictions", "api/v1/models/b/predictions"],
        help="API endpoint"
    )
    parser.add_argument(
        "--num-requests", 
        type=int, 
        default=10,
        help="Number of requests to send"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=0.5, 
        help="Delay between requests in seconds"
    )
    return parser.parse_args()

def generate_sample_features() -> Dict[str, Any]:
    """Generate random sample features for prediction."""
    # Generate random features - this should be adjusted based on your actual model
    return {
        "feature1": random.uniform(0, 1),
        "feature2": random.uniform(0, 10),
        "feature3": random.choice([0, 1]),
        "feature4": random.gauss(5, 2),
        "feature5": random.randint(1, 5),
    }

def send_prediction_request(
    host: str, 
    port: int, 
    endpoint: str, 
    features: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send a prediction request to the model serving API.
    
    Args:
        host: API host
        port: API port
        endpoint: API endpoint
        features: Feature dictionary
        
    Returns:
        API response as dictionary
    """
    url = f"http://{host}:{port}/{endpoint}"
    payload = {"features": features}
    
    try:
        start_time = time.time()
        response = requests.post(
            url, 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        latency = (time.time() - start_time) * 1000  # ms
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Request successful - Latency: {latency:.2f}ms")
            return result
        else:
            logger.error(f"Request failed with status {response.status_code}: {response.text}")
            return {"error": response.text}
    
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": str(e)}

def main():
    """Main function to run the demo client."""
    args = parse_args()
    logger.info(f"Starting demo client for {args.endpoint} on {args.host}:{args.port}")
    
    successful_requests = 0
    total_latency = 0
    
    # First try health check
    try:
        health_url = f"http://{args.host}:{args.port}/healthz"
        health_response = requests.get(health_url, timeout=5)
        logger.info(f"Health check: {health_response.status_code} - {health_response.text.strip()}")
    except requests.RequestException as e:
        logger.error(f"Health check failed: {str(e)}")
        logger.error("Make sure the API gateway is running before sending prediction requests")
        return 1
    
    # Send prediction requests
    for i in range(args.num_requests):
        logger.info(f"Sending request {i+1}/{args.num_requests}")
        
        # Generate random features
        features = generate_sample_features()
        
        # Send request
        result = send_prediction_request(args.host, args.port, args.endpoint, features)
        
        # Display result
        if "error" not in result:
            successful_requests += 1
            if "latency_ms" in result:
                total_latency += result["latency_ms"]
            
            logger.info(f"Prediction: {result.get('prediction')}")
            logger.info(f"Model info: {result.get('model_info')}")
        else:
            logger.error(f"Request failed: {result['error']}")
        
        # Add delay between requests
        if i < args.num_requests - 1:
            time.sleep(args.delay)
    
    # Summary
    logger.info("Demo client summary:")
    logger.info(f"Total requests: {args.num_requests}")
    logger.info(f"Successful requests: {successful_requests}")
    logger.info(f"Success rate: {(successful_requests/args.num_requests)*100:.1f}%")
    
    if successful_requests > 0 and "latency_ms" in result:
        avg_latency = total_latency / successful_requests
        logger.info(f"Average latency: {avg_latency:.2f}ms")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 