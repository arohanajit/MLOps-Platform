#!/usr/bin/env python
"""
Feature Engineering Test Script

This script tests the functionality of the Feature Engineering components:
- Feature Registry
- Feature Store
- Batch Feature Engineering Pipeline

It can run in both actual and mock modes. In mock mode, it uses mock data
instead of requiring actual infrastructure components.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd
import psycopg2
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default URLs
FEATURE_REGISTRY_URL = os.environ.get("FEATURE_REGISTRY_URL", "http://localhost:8000")
FEATURE_STORE_URL = os.environ.get("FEATURE_STORE_URL", "http://localhost:8001")

# Sample feature definitions
SAMPLE_FEATURES = [
    {
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
            "filter": "purchase_date >= NOW() - INTERVAL '30 days'"
        },
        "transformations": [
            {
                "type": "aggregation",
                "function": "sum",
                "column": "purchase_amount"
            }
        ]
    },
    {
        "name": "customer_days_since_last_purchase",
        "description": "Number of days since customer's last purchase",
        "entity_type": "customer",
        "value_type": "INT",
        "source": "BATCH",
        "category": "DERIVED",
        "frequency": "DAILY",
        "owner": "data-science-team",
        "tags": ["recency", "customer_360"],
        "source_config": {
            "table": "customer_purchases",
        },
        "transformations": [
            {
                "type": "date_diff",
                "from": "NOW()",
                "to": "MAX(purchase_date)"
            }
        ]
    },
    {
        "name": "product_purchase_count_30d",
        "description": "Number of times a product was purchased in the last 30 days",
        "entity_type": "product",
        "value_type": "INT",
        "source": "BATCH",
        "category": "DERIVED",
        "frequency": "DAILY",
        "owner": "data-science-team",
        "tags": ["popularity", "product_analytics"],
        "source_config": {
            "table": "purchase_items",
            "filter": "purchase_date >= NOW() - INTERVAL '30 days'"
        },
        "transformations": [
            {
                "type": "aggregation",
                "function": "count",
                "column": "purchase_id"
            }
        ]
    }
]

# Sample feature group
SAMPLE_FEATURE_GROUP = {
    "name": "customer_rfm_features",
    "description": "RFM (Recency, Frequency, Monetary) features for customer segmentation",
    "feature_names": [
        "customer_days_since_last_purchase",
        "customer_total_purchases_30d"
    ],
    "entity_type": "customer",
    "owner": "data-science-team",
    "tags": ["rfm", "segmentation", "customer_360"]
}

# Sample feature values
SAMPLE_FEATURE_VALUES = {
    "customer": {
        "customer123": {
            "customer_total_purchases_30d": 1250.75,
            "customer_days_since_last_purchase": 3,
            "customer_purchase_count_30d": 5
        },
        "customer456": {
            "customer_total_purchases_30d": 753.25,
            "customer_days_since_last_purchase": 7,
            "customer_purchase_count_30d": 3
        }
    },
    "product": {
        "product123": {
            "product_purchase_count_30d": 42,
            "product_revenue_30d": 8750.50
        },
        "product456": {
            "product_purchase_count_30d": 28,
            "product_revenue_30d": 4200.25
        }
    }
}


class FeatureEngineeringTester:
    """Test the Feature Engineering components."""
    
    def __init__(self, registry_url: str, store_url: str, mock_mode: bool = False):
        """
        Initialize the tester.
        
        Args:
            registry_url: URL of the Feature Registry API
            store_url: URL of the Feature Store API
            mock_mode: Whether to use mock data instead of actual infrastructure
        """
        self.registry_url = registry_url
        self.store_url = store_url
        self.mock_mode = mock_mode
        
        logger.info(f"Registry URL: {registry_url}")
        logger.info(f"Store URL: {store_url}")
        logger.info(f"Mock mode: {mock_mode}")
    
    def test_feature_registry(self):
        """Test the Feature Registry API."""
        logger.info("Testing Feature Registry API...")
        
        # If we're in mock mode, just simulate
        if self.mock_mode:
            logger.info("Mock mode: Simulating Feature Registry interactions")
            for feature in SAMPLE_FEATURES:
                logger.info(f"Mock: Created feature '{feature['name']}'")
            logger.info(f"Mock: Created feature group '{SAMPLE_FEATURE_GROUP['name']}'")
            return True
        
        try:
            # Check health
            response = requests.get(f"{self.registry_url}/health")
            if response.status_code != 200:
                logger.error(f"Health check failed: {response.text}")
                return False
            logger.info("Health check passed")
            
            # Register features
            for feature in SAMPLE_FEATURES:
                try:
                    response = requests.post(
                        f"{self.registry_url}/features",
                        json=feature
                    )
                    if response.status_code in [201, 409]:  # Created or already exists
                        logger.info(f"Feature '{feature['name']}' registered successfully")
                    else:
                        logger.error(f"Failed to register feature '{feature['name']}': {response.text}")
                except Exception as e:
                    logger.error(f"Error registering feature '{feature['name']}': {str(e)}")
            
            # Create feature group
            try:
                response = requests.post(
                    f"{self.registry_url}/feature-groups",
                    json=SAMPLE_FEATURE_GROUP
                )
                if response.status_code in [201, 409]:  # Created or already exists
                    logger.info(f"Feature group '{SAMPLE_FEATURE_GROUP['name']}' created successfully")
                else:
                    logger.error(f"Failed to create feature group: {response.text}")
            except Exception as e:
                logger.error(f"Error creating feature group: {str(e)}")
            
            # List features
            try:
                response = requests.get(f"{self.registry_url}/features")
                if response.status_code == 200:
                    features = response.json()
                    logger.info(f"Retrieved {features['count']} features")
                else:
                    logger.error(f"Failed to list features: {response.text}")
            except Exception as e:
                logger.error(f"Error listing features: {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"Error testing Feature Registry: {str(e)}")
            return False
    
    def test_feature_store(self):
        """Test the Feature Store API."""
        logger.info("Testing Feature Store API...")
        
        # If we're in mock mode, just simulate
        if self.mock_mode:
            logger.info("Mock mode: Simulating Feature Store interactions")
            for entity_type, entities in SAMPLE_FEATURE_VALUES.items():
                for entity_id, features in entities.items():
                    logger.info(f"Mock: Stored {len(features)} features for {entity_type}:{entity_id}")
                    logger.info(f"Mock: Retrieved features for {entity_type}:{entity_id}")
            return True
        
        try:
            # Check health
            response = requests.get(f"{self.store_url}/health")
            if response.status_code != 200:
                logger.error(f"Health check failed: {response.text}")
                return False
            logger.info("Health check passed")
            
            # Store features
            for entity_type, entities in SAMPLE_FEATURE_VALUES.items():
                for entity_id, features in entities.items():
                    try:
                        payload = {
                            "entity_id": entity_id,
                            "entity_type": entity_type,
                            "feature_values": features,
                            "ttl": 86400  # 1 day
                        }
                        response = requests.post(
                            f"{self.store_url}/store-features",
                            json=payload
                        )
                        if response.status_code == 201:
                            logger.info(f"Stored features for {entity_type}:{entity_id}")
                        else:
                            logger.error(f"Failed to store features: {response.text}")
                    except Exception as e:
                        logger.error(f"Error storing features: {str(e)}")
            
            # Retrieve features
            for entity_type, entities in SAMPLE_FEATURE_VALUES.items():
                for entity_id, features in entities.items():
                    try:
                        payload = {
                            "entity_id": entity_id,
                            "feature_names": list(features.keys()),
                            "entity_type": entity_type
                        }
                        response = requests.post(
                            f"{self.store_url}/features",
                            json=payload
                        )
                        if response.status_code == 200:
                            result = response.json()
                            logger.info(f"Retrieved features for {entity_type}:{entity_id}")
                            if result["missing_features"]:
                                logger.warning(f"Missing features: {result['missing_features']}")
                        else:
                            logger.error(f"Failed to retrieve features: {response.text}")
                    except Exception as e:
                        logger.error(f"Error retrieving features: {str(e)}")
            
            # Test batch feature retrieval
            for entity_type, entities in SAMPLE_FEATURE_VALUES.items():
                try:
                    payload = {
                        "entity_ids": list(entities.keys()),
                        "feature_names": list(next(iter(entities.values())).keys()),
                        "entity_type": entity_type
                    }
                    response = requests.post(
                        f"{self.store_url}/batch-features",
                        json=payload
                    )
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"Retrieved batch features for {len(result['entities'])} {entity_type} entities")
                    else:
                        logger.error(f"Failed to retrieve batch features: {response.text}")
                except Exception as e:
                    logger.error(f"Error retrieving batch features: {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"Error testing Feature Store: {str(e)}")
            return False
    
    def test_batch_feature_engineering(self):
        """Test the Batch Feature Engineering pipeline."""
        logger.info("Testing Batch Feature Engineering...")
        
        # If we're in mock mode, just simulate
        if self.mock_mode:
            logger.info("Mock mode: Simulating Batch Feature Engineering")
            logger.info("Mock: Computed customer features")
            logger.info("Mock: Computed product features")
            logger.info("Mock: Computed customer-product features")
            return True
        
        try:
            # Import the BatchFeatureEngineer class
            sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
            from feature_engineering.batch_pipeline import BatchFeatureEngineer
            
            # Initialize the pipeline with our feature store URL
            pipeline = BatchFeatureEngineer(
                feature_store_url=self.store_url
            )
            
            # Since we can't access the actual database in this test,
            # we'll mock the data retrieval and just test the feature storage
            
            # Create a sample DataFrame for customer features
            customer_data = []
            for entity_id, features in SAMPLE_FEATURE_VALUES["customer"].items():
                customer_data.append({
                    "customer_id": entity_id,
                    "entity_type": "customer",
                    **features
                })
            customer_df = pd.DataFrame(customer_data)
            
            # Create a sample DataFrame for product features
            product_data = []
            for entity_id, features in SAMPLE_FEATURE_VALUES["product"].items():
                product_data.append({
                    "product_id": entity_id,
                    "entity_type": "product",
                    **features
                })
            product_df = pd.DataFrame(product_data)
            
            # Test storing features
            pipeline.store_features_batch(customer_df, "customer")
            pipeline.store_features_batch(product_df, "product")
            
            logger.info("Batch Feature Engineering tested successfully")
            return True
        except Exception as e:
            logger.error(f"Error testing Batch Feature Engineering: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        start_time = time.time()
        
        logger.info("Starting Feature Engineering tests")
        
        # Run tests
        registry_result = self.test_feature_registry()
        store_result = self.test_feature_store()
        batch_result = self.test_batch_feature_engineering()
        
        # Summarize results
        elapsed = time.time() - start_time
        logger.info(f"Tests completed in {elapsed:.2f} seconds")
        
        success = registry_result and store_result and batch_result
        logger.info(f"Overall test result: {'SUCCESS' if success else 'FAILURE'}")
        
        return success


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Feature Engineering Test Script")
    
    parser.add_argument(
        "--registry-url",
        type=str,
        default=FEATURE_REGISTRY_URL,
        help="URL of the Feature Registry API"
    )
    
    parser.add_argument(
        "--store-url",
        type=str,
        default=FEATURE_STORE_URL,
        help="URL of the Feature Store API"
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no actual infrastructure needed)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    tester = FeatureEngineeringTester(
        registry_url=args.registry_url,
        store_url=args.store_url,
        mock_mode=args.mock
    )
    
    success = tester.run_all_tests()
    
    # Return appropriate exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 