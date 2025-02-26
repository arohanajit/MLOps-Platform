"""
Batch Feature Engineering Pipeline

This module implements batch feature engineering jobs for computing
feature values and storing them in the feature store.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, udf, datediff, current_timestamp, count, sum, avg, max, min, expr
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, TimestampType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchFeatureEngineer:
    """
    Batch Feature Engineering Pipeline.
    
    This class implements batch processing for feature engineering,
    calculating features based on historical data and storing them
    in the feature store.
    """
    
    def __init__(
        self,
        postgres_config: Optional[Dict[str, Any]] = None,
        feature_store_url: Optional[str] = None
    ):
        """
        Initialize the batch feature engineering pipeline.
        
        Args:
            postgres_config: PostgreSQL connection parameters
            feature_store_url: URL of the feature store API
        """
        self.postgres_config = postgres_config or {
            'host': os.environ.get('POSTGRES_HOST', 'postgresql.storage.svc.cluster.local'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'user': os.environ.get('POSTGRES_USER', 'mlops'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'password'),
            'dbname': os.environ.get('POSTGRES_DB', 'mlops')
        }
        
        self.feature_store_url = feature_store_url or os.environ.get(
            'FEATURE_STORE_URL', 
            'http://feature-store.feature-engineering.svc.cluster.local'
        )
        
        # Initialize Spark session
        self.spark = None
    
    def initialize_spark(self):
        """Initialize the Spark session."""
        if self.spark is None:
            self.spark = (
                SparkSession.builder
                .appName("BatchFeatureEngineer")
                .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
                .config("spark.sql.session.timeZone", "UTC")
                .getOrCreate()
            )
            logger.info("Spark session initialized")
    
    def get_postgres_connection(self):
        """Get a PostgreSQL connection."""
        return psycopg2.connect(**self.postgres_config)
    
    def get_batch_data(self, query: str) -> pd.DataFrame:
        """
        Retrieve batch data from PostgreSQL.
        
        Args:
            query: SQL query to retrieve data
            
        Returns:
            DataFrame with the retrieved data
        """
        conn = self.get_postgres_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info(f"Executing query: {query}")
            cursor.execute(query)
            records = cursor.fetchall()
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            logger.info(f"Retrieved {len(df)} records from PostgreSQL")
            
            return df
            
        except Exception as e:
            logger.error(f"Error retrieving batch data: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def compute_customer_features(self, lookback_days: int = 30):
        """
        Compute customer features based on purchase data.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        self.initialize_spark()
        
        # Get customer purchase data
        query = f"""
        SELECT 
            c.customer_id,
            c.email,
            c.created_at as customer_created_at,
            p.purchase_id,
            p.amount,
            p.created_at as purchase_date
        FROM 
            customers c
        LEFT JOIN 
            purchases p ON c.customer_id = p.customer_id
        WHERE 
            p.created_at >= NOW() - INTERVAL '{lookback_days} days'
            OR p.created_at IS NULL
        """
        
        df = self.get_batch_data(query)
        
        if df.empty:
            logger.warning("No customer data found for feature computation")
            return
        
        # Convert to Spark DataFrame
        spark_df = self.spark.createDataFrame(df)
        
        # Register as temporary view
        spark_df.createOrReplaceTempView("customer_purchases")
        
        # Compute features using SQL
        features_df = self.spark.sql(f"""
        WITH customer_stats AS (
            SELECT
                customer_id,
                COUNT(purchase_id) as purchase_count,
                SUM(amount) as total_purchase_amount,
                AVG(amount) as avg_purchase_amount,
                MAX(purchase_date) as last_purchase_date,
                MIN(customer_created_at) as created_at
            FROM
                customer_purchases
            GROUP BY
                customer_id
        )
        SELECT
            cs.customer_id,
            'customer' as entity_type,
            cs.purchase_count as customer_purchase_count_{lookback_days}d,
            cs.total_purchase_amount as customer_total_purchases_{lookback_days}d,
            cs.avg_purchase_amount as customer_avg_purchase_{lookback_days}d,
            DATEDIFF(CURRENT_TIMESTAMP(), cs.last_purchase_date) as customer_days_since_last_purchase,
            DATEDIFF(CURRENT_TIMESTAMP(), cs.created_at) as customer_account_age_days
        FROM
            customer_stats cs
        """)
        
        # Convert to pandas for easier processing
        pandas_features = features_df.toPandas()
        
        # Store features in feature store
        self.store_features_batch(pandas_features, "customer")
        
        logger.info(f"Computed and stored features for {len(pandas_features)} customers")
    
    def compute_product_features(self, lookback_days: int = 30):
        """
        Compute product features based on purchase data.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        self.initialize_spark()
        
        # Get product purchase data
        query = f"""
        SELECT 
            p.product_id,
            p.name as product_name,
            p.price,
            p.created_at as product_created_at,
            pi.purchase_id,
            pi.quantity,
            pu.created_at as purchase_date
        FROM 
            products p
        LEFT JOIN 
            purchase_items pi ON p.product_id = pi.product_id
        LEFT JOIN 
            purchases pu ON pi.purchase_id = pu.purchase_id
        WHERE 
            pu.created_at >= NOW() - INTERVAL '{lookback_days} days'
            OR pu.created_at IS NULL
        """
        
        df = self.get_batch_data(query)
        
        if df.empty:
            logger.warning("No product data found for feature computation")
            return
        
        # Convert to Spark DataFrame
        spark_df = self.spark.createDataFrame(df)
        
        # Register as temporary view
        spark_df.createOrReplaceTempView("product_purchases")
        
        # Compute features using SQL
        features_df = self.spark.sql(f"""
        WITH product_stats AS (
            SELECT
                product_id,
                COUNT(purchase_id) as purchase_count,
                SUM(quantity) as total_quantity,
                SUM(quantity * price) as total_revenue,
                MAX(purchase_date) as last_purchase_date,
                MIN(product_created_at) as created_at
            FROM
                product_purchases
            GROUP BY
                product_id, price
        )
        SELECT
            ps.product_id,
            'product' as entity_type,
            ps.purchase_count as product_purchase_count_{lookback_days}d,
            ps.total_quantity as product_quantity_sold_{lookback_days}d,
            ps.total_revenue as product_revenue_{lookback_days}d,
            DATEDIFF(CURRENT_TIMESTAMP(), ps.last_purchase_date) as product_days_since_last_purchase,
            DATEDIFF(CURRENT_TIMESTAMP(), ps.created_at) as product_age_days
        FROM
            product_stats ps
        """)
        
        # Convert to pandas for easier processing
        pandas_features = features_df.toPandas()
        
        # Store features in feature store
        self.store_features_batch(pandas_features, "product")
        
        logger.info(f"Computed and stored features for {len(pandas_features)} products")
    
    def compute_customer_product_features(self, lookback_days: int = 90):
        """
        Compute customer-product interaction features.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        self.initialize_spark()
        
        # Get customer-product interaction data
        query = f"""
        SELECT 
            c.customer_id,
            p.product_id,
            pi.quantity,
            pi.purchase_id,
            pu.amount,
            pu.created_at as purchase_date
        FROM 
            customers c
        JOIN 
            purchases pu ON c.customer_id = pu.customer_id
        JOIN 
            purchase_items pi ON pu.purchase_id = pi.purchase_id
        JOIN 
            products p ON pi.product_id = p.product_id
        WHERE 
            pu.created_at >= NOW() - INTERVAL '{lookback_days} days'
        """
        
        df = self.get_batch_data(query)
        
        if df.empty:
            logger.warning("No customer-product data found for feature computation")
            return
        
        # Convert to Spark DataFrame
        spark_df = self.spark.createDataFrame(df)
        
        # Register as temporary view
        spark_df.createOrReplaceTempView("customer_product_interactions")
        
        # Compute features using SQL
        features_df = self.spark.sql(f"""
        WITH interaction_stats AS (
            SELECT
                customer_id,
                product_id,
                COUNT(purchase_id) as purchase_count,
                SUM(quantity) as total_quantity,
                MAX(purchase_date) as last_purchase_date
            FROM
                customer_product_interactions
            GROUP BY
                customer_id, product_id
        )
        SELECT
            CONCAT(is.customer_id, ':', is.product_id) as entity_id,
            'customer_product' as entity_type,
            is.purchase_count as customer_product_purchase_count_{lookback_days}d,
            is.total_quantity as customer_product_quantity_{lookback_days}d,
            DATEDIFF(CURRENT_TIMESTAMP(), is.last_purchase_date) as customer_product_days_since_last_purchase
        FROM
            interaction_stats is
        """)
        
        # Convert to pandas for easier processing
        pandas_features = features_df.toPandas()
        
        # Store features in feature store
        self.store_features_batch(pandas_features, "customer_product")
        
        logger.info(f"Computed and stored features for {len(pandas_features)} customer-product interactions")
    
    def store_features_batch(self, features_df: pd.DataFrame, entity_type: str):
        """
        Store batch features in the feature store.
        
        Args:
            features_df: DataFrame with feature values
            entity_type: Type of entity (e.g., 'customer', 'product')
        """
        if features_df.empty:
            logger.warning(f"No features to store for entity type: {entity_type}")
            return
        
        # Prepare batch request
        entity_feature_values = {}
        
        # Group by entity ID
        id_column = f"{entity_type}_id" if entity_type in ["customer", "product"] else "entity_id"
        
        for _, row in features_df.iterrows():
            entity_id = str(row[id_column])
            
            # Skip rows without entity ID
            if not entity_id or pd.isna(entity_id):
                continue
            
            # Initialize feature values dict for this entity
            entity_feature_values[entity_id] = {}
            
            # Add all features except ID and entity_type
            for col_name in features_df.columns:
                if col_name not in [id_column, "entity_type"]:
                    # Skip NaN values
                    if not pd.isna(row[col_name]):
                        entity_feature_values[entity_id][col_name] = row[col_name]
        
        # Prepare request payload
        payload = {
            "entity_feature_values": entity_feature_values,
            "entity_type": entity_type,
            "ttl": 86400 * 7  # 7 days TTL
        }
        
        # Send request to feature store
        try:
            url = f"{self.feature_store_url}/batch-store-features"
            response = requests.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Error storing features: {response.text}")
            else:
                logger.info(f"Successfully stored {len(entity_feature_values)} {entity_type} feature sets")
                
        except Exception as e:
            logger.error(f"Error sending features to feature store: {str(e)}")
    
    def run_feature_computation(self, feature_types: List[str] = None, lookback_days: int = 30):
        """
        Run feature computation for specified feature types.
        
        Args:
            feature_types: List of feature types to compute ('customer', 'product', 'customer_product')
            lookback_days: Number of days to look back for feature computation
        """
        if feature_types is None:
            feature_types = ["customer", "product", "customer_product"]
        
        start_time = time.time()
        logger.info(f"Starting feature computation for types: {feature_types}")
        
        try:
            if "customer" in feature_types:
                self.compute_customer_features(lookback_days)
            
            if "product" in feature_types:
                self.compute_product_features(lookback_days)
            
            if "customer_product" in feature_types:
                self.compute_customer_product_features(lookback_days)
            
            elapsed = time.time() - start_time
            logger.info(f"Feature computation completed in {elapsed:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error during feature computation: {str(e)}")
            raise
        finally:
            if self.spark:
                self.spark.stop()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Batch Feature Engineering Pipeline")
    
    parser.add_argument(
        "--feature-types",
        type=str,
        default="customer,product,customer_product",
        help="Comma-separated list of feature types to compute"
    )
    
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Number of days to look back for feature computation"
    )
    
    parser.add_argument(
        "--feature-store-url",
        type=str,
        default=None,
        help="URL of the feature store API"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Parse feature types
    feature_types = [ft.strip() for ft in args.feature_types.split(",")]
    
    # Initialize and run the pipeline
    pipeline = BatchFeatureEngineer(feature_store_url=args.feature_store_url)
    pipeline.run_feature_computation(feature_types, args.lookback_days)


if __name__ == "__main__":
    main() 