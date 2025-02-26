"""
Feature Store

This module implements the Feature Store for serving and storing features 
for machine learning models.
"""

import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union, Tuple

import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureStore:
    """
    Feature Store for managing and serving ML features.
    
    Supports both online (Redis) and offline (PostgreSQL) storage,
    with automated synchronization between the two.
    """
    
    def __init__(
        self,
        redis_config: Optional[Dict[str, Any]] = None,
        postgres_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Feature Store with connection parameters.
        
        Args:
            redis_config: Redis connection parameters
            postgres_config: PostgreSQL connection parameters
        """
        self.redis_config = redis_config or {
            'host': os.environ.get('REDIS_HOST', 'redis-master.storage.svc.cluster.local'),
            'port': int(os.environ.get('REDIS_PORT', '6379')),
            'db': int(os.environ.get('REDIS_DB', '0')),
            'password': os.environ.get('REDIS_PASSWORD', None),
            'decode_responses': True
        }
        
        self.postgres_config = postgres_config or {
            'host': os.environ.get('POSTGRES_HOST', 'postgresql.storage.svc.cluster.local'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'user': os.environ.get('POSTGRES_USER', 'mlops'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'password'),
            'dbname': os.environ.get('POSTGRES_DB', 'mlops')
        }
        
        # Connect to Redis
        self._redis = None
        
        # Connect to PostgreSQL
        self._postgres = None
    
    @property
    def redis(self):
        """Lazy initialize Redis connection."""
        if self._redis is None:
            logger.info(f"Connecting to Redis at {self.redis_config['host']}:{self.redis_config['port']}")
            self._redis = redis.Redis(**self.redis_config)
        return self._redis
    
    @property
    def postgres(self):
        """Lazy initialize PostgreSQL connection."""
        if self._postgres is None:
            logger.info(f"Connecting to PostgreSQL at {self.postgres_config['host']}:{self.postgres_config['port']}")
            self._postgres = psycopg2.connect(**self.postgres_config)
        return self._postgres
    
    def _get_postgres_cursor(self):
        """Get a PostgreSQL cursor."""
        try:
            return self.postgres.cursor(cursor_factory=RealDictCursor)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # Connection expired, reconnect
            self._postgres = None
            return self.postgres.cursor(cursor_factory=RealDictCursor)
    
    def get_feature_values(
        self, 
        entity_id: str, 
        feature_names: List[str], 
        entity_type: str
    ) -> Dict[str, Any]:
        """
        Get feature values for an entity from the online store.
        
        Args:
            entity_id: The entity identifier
            feature_names: List of feature names to retrieve
            entity_type: Type of entity (e.g., 'customer', 'product')
            
        Returns:
            Dictionary of feature values
        """
        result = {}
        missing_features = []
        
        # Format the Redis key for each feature
        redis_keys = [f"{entity_type}:{entity_id}:{feature}" for feature in feature_names]
        
        # Get all values in a single request (pipeline)
        pipeline = self.redis.pipeline()
        for key in redis_keys:
            pipeline.get(key)
        
        values = pipeline.execute()
        
        # Process the results
        for i, feature in enumerate(feature_names):
            if values[i] is not None:
                try:
                    # Try to parse as JSON
                    result[feature] = json.loads(values[i])
                except (json.JSONDecodeError, TypeError):
                    # If not JSON, store as is
                    result[feature] = values[i]
            else:
                missing_features.append(feature)
        
        # Log any missing features
        if missing_features:
            logger.warning(f"Missing features for {entity_type}:{entity_id}: {missing_features}")
        
        return result
    
    def get_batch_feature_values(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        entity_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get feature values for multiple entities from the online store.
        
        Args:
            entity_ids: List of entity identifiers
            feature_names: List of feature names to retrieve
            entity_type: Type of entity (e.g., 'customer', 'product')
            
        Returns:
            Dictionary mapping entity_ids to their feature values
        """
        result = {entity_id: {} for entity_id in entity_ids}
        
        # Use Redis pipeline for batch operations
        pipeline = self.redis.pipeline()
        
        # Queue up all the GET commands
        for entity_id in entity_ids:
            for feature in feature_names:
                key = f"{entity_type}:{entity_id}:{feature}"
                pipeline.get(key)
        
        # Execute the pipeline
        values = pipeline.execute()
        
        # Process the results
        idx = 0
        for entity_id in entity_ids:
            for feature in feature_names:
                value = values[idx]
                idx += 1
                
                if value is not None:
                    try:
                        # Try to parse as JSON
                        result[entity_id][feature] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # If not JSON, store as is
                        result[entity_id][feature] = value
        
        return result
    
    def store_feature_values(
        self,
        entity_id: str,
        feature_values: Dict[str, Any],
        entity_type: str,
        ttl: Optional[int] = None
    ):
        """
        Store feature values for an entity in the online store.
        
        Args:
            entity_id: The entity identifier
            feature_values: Dictionary of feature values
            entity_type: Type of entity (e.g., 'customer', 'product')
            ttl: Optional time-to-live in seconds
        """
        pipeline = self.redis.pipeline()
        
        # Set each feature value
        for feature, value in feature_values.items():
            key = f"{entity_type}:{entity_id}:{feature}"
            
            # Convert non-string values to JSON
            if not isinstance(value, str):
                value = json.dumps(value)
            
            pipeline.set(key, value)
            
            # Set TTL if provided
            if ttl:
                pipeline.expire(key, ttl)
        
        # Execute the pipeline
        pipeline.execute()
        logger.debug(f"Stored {len(feature_values)} features for {entity_type}:{entity_id}")
    
    def store_batch_feature_values(
        self,
        entity_feature_values: Dict[str, Dict[str, Any]],
        entity_type: str,
        ttl: Optional[int] = None
    ):
        """
        Store feature values for multiple entities in the online store.
        
        Args:
            entity_feature_values: Dictionary mapping entity_ids to their feature values
            entity_type: Type of entity (e.g., 'customer', 'product')
            ttl: Optional time-to-live in seconds
        """
        pipeline = self.redis.pipeline()
        
        # Set each feature value for each entity
        for entity_id, feature_values in entity_feature_values.items():
            for feature, value in feature_values.items():
                key = f"{entity_type}:{entity_id}:{feature}"
                
                # Convert non-string values to JSON
                if not isinstance(value, str):
                    value = json.dumps(value)
                
                pipeline.set(key, value)
                
                # Set TTL if provided
                if ttl:
                    pipeline.expire(key, ttl)
        
        # Execute the pipeline
        pipeline.execute()
        logger.debug(f"Stored features for {len(entity_feature_values)} entities of type {entity_type}")
    
    def get_historical_feature_values(
        self,
        entity_id: str,
        feature_names: List[str],
        entity_type: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get historical feature values from the offline store.
        
        Args:
            entity_id: The entity identifier
            feature_names: List of feature names to retrieve
            entity_type: Type of entity (e.g., 'customer', 'product')
            start_time: Optional start time (ISO format)
            end_time: Optional end time (ISO format)
            limit: Maximum number of records to return
            
        Returns:
            DataFrame with historical feature values
        """
        cursor = self._get_postgres_cursor()
        
        # Build the query
        feature_columns = ", ".join([f"data->'{feature}' as {feature}" for feature in feature_names])
        query = f"""
        SELECT 
            timestamp,
            {feature_columns}
        FROM feature_store_history
        WHERE entity_id = %s AND entity_type = %s
        """
        
        params = [entity_id, entity_type]
        
        # Add time constraints if provided
        if start_time:
            query += " AND timestamp >= %s"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= %s"
            params.append(end_time)
        
        # Add ordering and limit
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        try:
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            
            if not df.empty:
                # Convert timestamp to datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Set timestamp as index
                df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error retrieving historical features: {str(e)}")
            self.postgres.rollback()
            raise
        finally:
            cursor.close()
    
    def materialize_features(self, query: str, batch_size: int = 1000):
        """
        Materialize features from offline to online store.
        
        Args:
            query: SQL query that produces entity_id, entity_type, and feature columns
            batch_size: Number of entities to process in a batch
        """
        cursor = self._get_postgres_cursor()
        
        try:
            logger.info(f"Starting feature materialization with query: {query}")
            cursor.execute(query)
            
            start_time = time.time()
            total_count = 0
            
            while True:
                # Fetch a batch of records
                records = cursor.fetchmany(batch_size)
                if not records:
                    break
                
                # Process the batch
                for record in records:
                    entity_id = str(record.pop('entity_id'))
                    entity_type = record.pop('entity_type')
                    
                    # Store in Redis
                    self.store_feature_values(entity_id, record, entity_type)
                
                total_count += len(records)
                
                # Log progress
                if total_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = total_count / elapsed if elapsed > 0 else 0
                    logger.info(f"Materialized {total_count} entities at {rate:.2f} entities/second")
            
            logger.info(f"Completed feature materialization: {total_count} entities processed")
            
        except Exception as e:
            logger.error(f"Error during feature materialization: {str(e)}")
            self.postgres.rollback()
            raise
        finally:
            cursor.close()
    
    def store_historical_features(
        self,
        entity_id: str,
        feature_values: Dict[str, Any],
        entity_type: str,
        timestamp: Optional[str] = None
    ):
        """
        Store historical feature values in the offline store.
        
        Args:
            entity_id: The entity identifier
            feature_values: Dictionary of feature values
            entity_type: Type of entity (e.g., 'customer', 'product')
            timestamp: Optional timestamp (ISO format), defaults to current time
        """
        cursor = self._get_postgres_cursor()
        
        try:
            # Insert the record
            cursor.execute("""
            INSERT INTO feature_store_history (entity_id, entity_type, data, timestamp)
            VALUES (%s, %s, %s, COALESCE(%s, NOW()))
            """, (entity_id, entity_type, psycopg2.extras.Json(feature_values), timestamp))
            
            self.postgres.commit()
            logger.debug(f"Stored historical features for {entity_type}:{entity_id}")
            
        except Exception as e:
            logger.error(f"Error storing historical features: {str(e)}")
            self.postgres.rollback()
            raise
        finally:
            cursor.close()
    
    def create_feature_vector(
        self,
        entity_id: str,
        feature_names: List[str],
        entity_type: str
    ) -> Dict[str, Any]:
        """
        Create a feature vector for model inference.
        
        Args:
            entity_id: The entity identifier
            feature_names: List of feature names to include in the vector
            entity_type: Type of entity (e.g., 'customer', 'product')
            
        Returns:
            Dictionary with feature values suitable for model input
        """
        # Get the feature values
        feature_values = self.get_feature_values(entity_id, feature_names, entity_type)
        
        # Convert numerical values to float
        for feature, value in feature_values.items():
            try:
                if isinstance(value, (str, int)):
                    feature_values[feature] = float(value)
            except (ValueError, TypeError):
                # Not a numerical value, leave as is
                pass
        
        return feature_values
    
    def initialize_schema(self):
        """Create the necessary tables if they don't exist."""
        cursor = self._get_postgres_cursor()
        
        try:
            # Create history table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_store_history (
                id SERIAL PRIMARY KEY,
                entity_id VARCHAR(255) NOT NULL,
                entity_type VARCHAR(255) NOT NULL,
                data JSONB NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """)
            
            # Create indexes
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_store_history_entity
            ON feature_store_history (entity_id, entity_type)
            """)
            
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_store_history_timestamp
            ON feature_store_history (timestamp)
            """)
            
            self.postgres.commit()
            logger.info("Feature store schema initialized successfully")
            
        except Exception as e:
            self.postgres.rollback()
            logger.error(f"Error initializing feature store schema: {str(e)}")
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close all connections."""
        if self._redis:
            self._redis.close()
            self._redis = None
        
        if self._postgres:
            self._postgres.close()
            self._postgres = None 