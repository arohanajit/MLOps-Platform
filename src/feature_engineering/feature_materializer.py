#!/usr/bin/env python3
"""
Feature Materialization Script

This script handles the synchronization of features between online (Redis)
and offline (PostgreSQL) stores. It ensures that the latest feature values
are available in both stores for serving and batch processing.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import psycopg2
import redis
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FeatureMaterializer")

# Environment Variables with defaults for local development
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "mlops")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_DB = os.environ.get("REDIS_DB", "0")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

FEATURE_REGISTRY_URL = os.environ.get("FEATURE_REGISTRY_URL", "http://localhost:8000")


class FeatureMaterializer:
    """
    Feature Materialization Manager.
    
    Handles the synchronization of features between online (Redis)
    and offline (PostgreSQL) stores.
    """
    
    def __init__(
        self,
        postgres_config: Optional[Dict[str, Any]] = None,
        redis_config: Optional[Dict[str, Any]] = None,
        feature_registry_url: Optional[str] = None
    ):
        """
        Initialize the Feature Materializer.
        
        Args:
            postgres_config: Configuration for PostgreSQL connection
            redis_config: Configuration for Redis connection
            feature_registry_url: URL for the Feature Registry API
        """
        # PostgreSQL configuration
        self.postgres_config = postgres_config or {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "dbname": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD
        }
        
        # Redis configuration
        self.redis_config = redis_config or {
            "host": REDIS_HOST,
            "port": int(REDIS_PORT),
            "db": int(REDIS_DB),
            "password": REDIS_PASSWORD if REDIS_PASSWORD else None
        }
        
        # Feature Registry URL
        self.feature_registry_url = feature_registry_url or FEATURE_REGISTRY_URL
        
        # Connections
        self.pg_conn = None
        self.redis_client = None
        
        # Initialize connections
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize database connections."""
        try:
            # PostgreSQL connection
            self.pg_conn = psycopg2.connect(**self.postgres_config)
            logger.info("PostgreSQL connection established")
            
            # Redis connection
            self.redis_client = redis.Redis(**self.redis_config)
            self.redis_client.ping()  # Check connection
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Error initializing connections: {str(e)}")
            self.close_connections()
            raise
    
    def close_connections(self):
        """Close database connections."""
        if self.pg_conn:
            self.pg_conn.close()
            self.pg_conn = None
            logger.info("PostgreSQL connection closed")
        
        if self.redis_client:
            self.redis_client.close()
            self.redis_client = None
            logger.info("Redis connection closed")
    
    def get_features_for_entity_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get all features for a specific entity type from the Feature Registry.
        
        Args:
            entity_type: Type of entity (customer, product, customer_product)
            
        Returns:
            List of feature dictionaries
        """
        try:
            response = requests.get(
                f"{self.feature_registry_url}/features/entity/{entity_type}"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get features for entity type {entity_type}: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting features for entity type {entity_type}: {str(e)}")
            return []
    
    def materialize_to_online(
        self,
        entity_type: str,
        since_hours: int = 24,
        batch_size: int = 1000
    ):
        """
        Materialize features from offline store (PostgreSQL) to online store (Redis).
        
        Args:
            entity_type: Type of entity (customer, product, customer_product)
            since_hours: Only materialize features updated in the past N hours
            batch_size: Number of records to process in each batch
        """
        logger.info(f"Starting materialization to online store for entity type: {entity_type}")
        
        try:
            # Get features for entity type
            features = self.get_features_for_entity_type(entity_type)
            feature_names = [feature["name"] for feature in features]
            
            if not feature_names:
                logger.warning(f"No features found for entity type {entity_type}")
                return
            
            # Get timestamp for filtering
            since_timestamp = datetime.now() - timedelta(hours=since_hours)
            
            # Create cursor
            cursor = self.pg_conn.cursor()
            
            # Define the query based on entity type
            if entity_type == "customer":
                id_column = "customer_id"
                table_name = "customer_features"
            elif entity_type == "product":
                id_column = "product_id"
                table_name = "product_features"
            elif entity_type == "customer_product":
                id_column = "customer_id, product_id"
                table_name = "customer_product_features"
            else:
                logger.error(f"Unsupported entity type: {entity_type}")
                return
            
            # Query to get the latest feature values
            query = f"""
                WITH latest_features AS (
                    SELECT 
                        {id_column},
                        feature_name,
                        feature_value,
                        timestamp,
                        ROW_NUMBER() OVER (
                            PARTITION BY {id_column}, feature_name 
                            ORDER BY timestamp DESC
                        ) as row_num
                    FROM {table_name}
                    WHERE timestamp >= %s
                )
                SELECT {id_column}, feature_name, feature_value
                FROM latest_features
                WHERE row_num = 1
                ORDER BY {id_column}
                LIMIT %s OFFSET %s
            """
            
            # Process in batches
            offset = 0
            total_materialized = 0
            
            while True:
                cursor.execute(query, (since_timestamp, batch_size, offset))
                rows = cursor.fetchall()
                
                if not rows:
                    break
                
                # Process each row
                for row in rows:
                    if entity_type == "customer_product":
                        # Customer-Product features
                        customer_id, product_id, feature_name, feature_value = row
                        redis_key = f"{entity_type}:{customer_id}:{product_id}:{feature_name}"
                    else:
                        # Customer or Product features
                        entity_id, feature_name, feature_value = row
                        redis_key = f"{entity_type}:{entity_id}:{feature_name}"
                    
                    # Store in Redis (with 7-day TTL)
                    self.redis_client.set(
                        redis_key,
                        json.dumps(feature_value),
                        ex=7*24*60*60  # 7 days TTL
                    )
                
                total_materialized += len(rows)
                offset += batch_size
                logger.info(f"Materialized {len(rows)} {entity_type} features to online store")
            
            cursor.close()
            logger.info(f"Completed materialization of {total_materialized} {entity_type} features to online store")
        
        except Exception as e:
            logger.error(f"Error materializing {entity_type} features to online store: {str(e)}")
    
    def materialize_to_offline(
        self,
        entity_type: str,
        batch_size: int = 1000
    ):
        """
        Materialize features from online store (Redis) to offline store (PostgreSQL).
        
        Args:
            entity_type: Type of entity (customer, product, customer_product)
            batch_size: Number of records to process in each batch
        """
        logger.info(f"Starting materialization to offline store for entity type: {entity_type}")
        
        try:
            # Get features for entity type
            features = self.get_features_for_entity_type(entity_type)
            feature_names = [feature["name"] for feature in features]
            
            if not feature_names:
                logger.warning(f"No features found for entity type {entity_type}")
                return
            
            # Define the Redis key pattern based on entity type
            redis_key_pattern = f"{entity_type}:*"
            
            # Define the insert query based on entity type
            if entity_type == "customer":
                table_name = "customer_features"
                insert_query = f"""
                    INSERT INTO {table_name} (customer_id, feature_name, feature_value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (customer_id, feature_name, timestamp)
                    DO UPDATE SET feature_value = EXCLUDED.feature_value
                """
            elif entity_type == "product":
                table_name = "product_features"
                insert_query = f"""
                    INSERT INTO {table_name} (product_id, feature_name, feature_value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (product_id, feature_name, timestamp)
                    DO UPDATE SET feature_value = EXCLUDED.feature_value
                """
            elif entity_type == "customer_product":
                table_name = "customer_product_features"
                insert_query = f"""
                    INSERT INTO {table_name} (customer_id, product_id, feature_name, feature_value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (customer_id, product_id, feature_name, timestamp)
                    DO UPDATE SET feature_value = EXCLUDED.feature_value
                """
            else:
                logger.error(f"Unsupported entity type: {entity_type}")
                return
            
            # Get all keys matching the pattern
            cursor = 0
            total_materialized = 0
            
            while True:
                # Scan Redis keys in batches
                cursor, keys = self.redis_client.scan(cursor=cursor, match=redis_key_pattern, count=batch_size)
                
                if not keys:
                    if cursor == 0:
                        # No more keys and scan completed
                        break
                    continue
                
                # Process each key
                pg_cursor = self.pg_conn.cursor()
                
                for key in keys:
                    key = key.decode('utf-8')
                    parts = key.split(':')
                    
                    # Skip keys that don't match expected pattern
                    if len(parts) < 3:
                        continue
                    
                    # Get feature value from Redis
                    value_str = self.redis_client.get(key)
                    if not value_str:
                        continue
                    
                    try:
                        feature_value = json.loads(value_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON value for key {key}")
                        continue
                    
                    # Parse key parts
                    if entity_type == "customer_product":
                        # Format: customer_product:customer_id:product_id:feature_name
                        if len(parts) != 4:
                            continue
                        
                        _, customer_id, product_id, feature_name = parts
                        
                        # Insert into PostgreSQL
                        pg_cursor.execute(
                            insert_query,
                            (customer_id, product_id, feature_name, json.dumps(feature_value))
                        )
                    else:
                        # Format: {entity_type}:{entity_id}:{feature_name}
                        if len(parts) != 3:
                            continue
                        
                        _, entity_id, feature_name = parts
                        
                        # Insert into PostgreSQL
                        pg_cursor.execute(
                            insert_query,
                            (entity_id, feature_name, json.dumps(feature_value))
                        )
                
                self.pg_conn.commit()
                pg_cursor.close()
                
                total_materialized += len(keys)
                logger.info(f"Materialized {len(keys)} {entity_type} features to offline store")
                
                if cursor == 0:
                    # Scan completed
                    break
            
            logger.info(f"Completed materialization of {total_materialized} {entity_type} features to offline store")
        
        except Exception as e:
            logger.error(f"Error materializing {entity_type} features to offline store: {str(e)}")
    
    def run_materialization(
        self,
        direction: str = "both",
        entity_types: Optional[List[str]] = None,
        since_hours: int = 24,
        batch_size: int = 1000
    ):
        """
        Run feature materialization in the specified direction.
        
        Args:
            direction: Direction of materialization (online, offline, both)
            entity_types: List of entity types to materialize (default: all)
            since_hours: Only materialize features updated in the past N hours
            batch_size: Number of records to process in each batch
        """
        if entity_types is None:
            entity_types = ["customer", "product", "customer_product"]
        
        for entity_type in entity_types:
            if direction in ("online", "both"):
                self.materialize_to_online(entity_type, since_hours, batch_size)
            
            if direction in ("offline", "both"):
                self.materialize_to_offline(entity_type, batch_size)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Feature Materialization Tool")
    
    parser.add_argument(
        "--direction",
        type=str,
        choices=["online", "offline", "both"],
        default="both",
        help="Direction of materialization (online, offline, both)"
    )
    
    parser.add_argument(
        "--entity-types",
        type=str,
        help="Comma-separated list of entity types to materialize (customer,product,customer_product)"
    )
    
    parser.add_argument(
        "--since-hours",
        type=int,
        default=24,
        help="Only materialize features updated in the past N hours"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of records to process in each batch"
    )
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()
    
    # Parse entity types
    entity_types = None
    if args.entity_types:
        entity_types = [et.strip() for et in args.entity_types.split(",")]
    
    try:
        # Initialize Feature Materializer
        materializer = FeatureMaterializer()
        
        # Run materialization
        materializer.run_materialization(
            direction=args.direction,
            entity_types=entity_types,
            since_hours=args.since_hours,
            batch_size=args.batch_size
        )
        
        logger.info("Feature materialization completed successfully")
    except Exception as e:
        logger.error(f"Error in feature materialization: {str(e)}")
        sys.exit(1)
    finally:
        # Close connections
        try:
            materializer.close_connections()
        except:
            pass


if __name__ == "__main__":
    main() 