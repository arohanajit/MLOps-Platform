#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   MLOps Platform - Feature Engineering   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed.${NC}"
    exit 1
fi

# Create the Feature Registry database schema
echo -e "${YELLOW}Creating Feature Registry database schema...${NC}"
cat <<EOF > kubernetes/feature-engineering/initialize-feature-schemas.sql
-- Feature Registry Schema

-- Create sequence for feature versions
CREATE SEQUENCE IF NOT EXISTS feature_version_seq START 1;

-- Feature metadata table
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    entity_type VARCHAR(100) NOT NULL,
    value_type VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    frequency VARCHAR(50) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    tags JSONB DEFAULT '[]',
    source_config JSONB DEFAULT '{}',
    transformations JSONB DEFAULT '[]',
    stats JSONB DEFAULT NULL,
    current_version INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Feature versions table
CREATE TABLE IF NOT EXISTS feature_versions (
    id SERIAL PRIMARY KEY,
    feature_id INT NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    version INT NOT NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feature_id, version)
);

-- Feature groups table
CREATE TABLE IF NOT EXISTS feature_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    entity_type VARCHAR(100) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Feature group membership table
CREATE TABLE IF NOT EXISTS feature_group_members (
    group_id INT NOT NULL REFERENCES feature_groups(id) ON DELETE CASCADE,
    feature_id INT NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, feature_id)
);

-- Feature Store Schema

-- Create table for each entity type with feature values

-- Customer features
CREATE TABLE IF NOT EXISTS customer_features (
    customer_id VARCHAR(255) NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    feature_value JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, feature_name, timestamp)
);

-- Product features
CREATE TABLE IF NOT EXISTS product_features (
    product_id VARCHAR(255) NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    feature_value JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, feature_name, timestamp)
);

-- Customer-Product features (for recommendations, etc.)
CREATE TABLE IF NOT EXISTS customer_product_features (
    customer_id VARCHAR(255) NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    feature_value JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, product_id, feature_name, timestamp)
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_customer_features_feature_name ON customer_features(feature_name);
CREATE INDEX IF NOT EXISTS idx_product_features_feature_name ON product_features(feature_name);
CREATE INDEX IF NOT EXISTS idx_customer_product_features_feature_name ON customer_product_features(feature_name);

-- Function to clean up old feature values (retain only latest N versions)
CREATE OR REPLACE FUNCTION cleanup_old_feature_values(retention_count INT DEFAULT 10)
RETURNS void AS $$
DECLARE
    entity_types TEXT[] := ARRAY['customer', 'product', 'customer_product'];
    entity_type TEXT;
    cleanup_query TEXT;
BEGIN
    FOREACH entity_type IN ARRAY entity_types LOOP
        IF entity_type = 'customer' THEN
            cleanup_query := '
                DELETE FROM customer_features cf
                WHERE cf.timestamp < (
                    SELECT timestamp
                    FROM customer_features
                    WHERE customer_id = cf.customer_id AND feature_name = cf.feature_name
                    ORDER BY timestamp DESC
                    OFFSET ' || retention_count || ' LIMIT 1
                )';
        ELSIF entity_type = 'product' THEN
            cleanup_query := '
                DELETE FROM product_features pf
                WHERE pf.timestamp < (
                    SELECT timestamp
                    FROM product_features
                    WHERE product_id = pf.product_id AND feature_name = pf.feature_name
                    ORDER BY timestamp DESC
                    OFFSET ' || retention_count || ' LIMIT 1
                )';
        ELSIF entity_type = 'customer_product' THEN
            cleanup_query := '
                DELETE FROM customer_product_features cpf
                WHERE cpf.timestamp < (
                    SELECT timestamp
                    FROM customer_product_features
                    WHERE customer_id = cpf.customer_id 
                    AND product_id = cpf.product_id 
                    AND feature_name = cpf.feature_name
                    ORDER BY timestamp DESC
                    OFFSET ' || retention_count || ' LIMIT 1
                )';
        END IF;
        
        EXECUTE cleanup_query;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to clean up old feature values (PostgreSQL 12+ with pg_cron extension)
-- NOTE: Enable pg_cron extension if needed in your production database
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
-- SELECT cron.schedule('0 3 * * *', 'SELECT cleanup_old_feature_values();');
EOF

echo -e "${GREEN}Feature Registry database schema created.${NC}"
echo ""

# Create ConfigMap for the initialization SQL
echo -e "${YELLOW}Creating ConfigMap for database initialization...${NC}"
kubectl create configmap feature-init-sql -n storage --from-file=kubernetes/feature-engineering/initialize-feature-schemas.sql --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}ConfigMap created.${NC}"
echo ""

# Initialize the Feature Registry database schema
echo -e "${YELLOW}Initializing Feature Registry database...${NC}"
kubectl get pod -n storage -l app=postgres -o name | head -n 1 | xargs -I{} kubectl cp kubernetes/feature-engineering/initialize-feature-schemas.sql {}:/tmp/initialize-feature-schemas.sql -n storage
kubectl get pod -n storage -l app=postgres -o name | head -n 1 | xargs -I{} kubectl exec {} -n storage -- psql -U postgres -d mlops -f /tmp/initialize-feature-schemas.sql
echo -e "${GREEN}Feature Registry database initialized.${NC}"
echo ""

# Deploy Feature Registry API
echo -e "${YELLOW}Deploying Feature Registry API...${NC}"
kubectl apply -f kubernetes/feature-engineering/feature-registry.yaml
echo -e "${GREEN}Feature Registry API deployed.${NC}"
echo ""

# Wait for Feature Registry API to be ready
echo -e "${YELLOW}Waiting for Feature Registry API to be ready...${NC}"
kubectl rollout status deployment/feature-registry -n mlops
echo -e "${GREEN}Feature Registry API is ready.${NC}"
echo ""

# Deploy Feature Store API
echo -e "${YELLOW}Deploying Feature Store API...${NC}"
kubectl apply -f kubernetes/feature-engineering/feature-store.yaml
echo -e "${GREEN}Feature Store API deployed.${NC}"
echo ""

# Wait for Feature Store API to be ready
echo -e "${YELLOW}Waiting for Feature Store API to be ready...${NC}"
kubectl rollout status deployment/feature-store -n mlops
echo -e "${GREEN}Feature Store API is ready.${NC}"
echo ""

# Create a SparkApplication for batch feature engineering
echo -e "${YELLOW}Creating Batch Feature Engineering SparkApplication...${NC}"
cat <<EOF > kubernetes/feature-engineering/batch-feature-engineering-job.yaml
apiVersion: "sparkoperator.k8s.io/v1beta2"
kind: SparkApplication
metadata:
  name: batch-feature-engineering
  namespace: spark
spec:
  type: Python
  mode: cluster
  image: "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/mlops/spark-driver:latest"
  imagePullPolicy: Always
  mainApplicationFile: local:///opt/spark/work-dir/batch_feature_engineer.py
  sparkVersion: "3.4.1"
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
    onFailureRetryInterval: 10
    onSubmissionFailureRetries: 5
    onSubmissionFailureRetryInterval: 20
  pythonVersion: "3"
  deps:
    jars:
      - local:///opt/spark/jars/org.apache.spark_spark-sql-kafka-0-10_2.12-3.4.1.jar
      - local:///opt/spark/jars/org.apache.kafka_kafka-clients-3.3.2.jar
      - local:///opt/spark/jars/org.postgresql_postgresql-42.6.0.jar
    packages:
      - org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1
      - org.postgresql:postgresql:42.6.0
  driver:
    cores: 1
    coreLimit: "1000m"
    memory: "1024m"
    serviceAccount: spark
    labels:
      version: 3.4.1
    env:
      - name: POSTGRES_HOST
        value: postgres.storage.svc.cluster.local
      - name: POSTGRES_PORT
        value: "5432"
      - name: POSTGRES_DB
        value: mlops
      - name: POSTGRES_USER
        valueFrom:
          secretKeyRef:
            name: postgres-credentials
            key: username
      - name: POSTGRES_PASSWORD
        valueFrom:
          secretKeyRef:
            name: postgres-credentials
            key: password
      - name: FEATURE_STORE_URL
        value: http://feature-store.mlops.svc.cluster.local:8000
      - name: FEATURE_REGISTRY_URL
        value: http://feature-registry.mlops.svc.cluster.local:8000
  executor:
    cores: 1
    instances: 1
    memory: "1024m"
    labels:
      version: 3.4.1
EOF

# Apply the SparkApplication
kubectl apply -f kubernetes/feature-engineering/batch-feature-engineering-job.yaml
echo -e "${GREEN}Batch Feature Engineering SparkApplication created.${NC}"
echo ""

# Create a CronJob for scheduled feature engineering
echo -e "${YELLOW}Creating CronJob for scheduled feature engineering...${NC}"
cat <<EOF > kubernetes/feature-engineering/feature-engineering-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: feature-engineering-scheduler
  namespace: mlops
spec:
  schedule: "0 0 * * *"  # Run daily at midnight
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: spark-admin
          containers:
          - name: feature-engineering-trigger
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              kubectl delete --ignore-not-found=true sparkapplication batch-feature-engineering -n spark && 
              kubectl apply -f /etc/config/batch-feature-engineering-job.yaml
            volumeMounts:
            - name: spark-job-config
              mountPath: /etc/config
          volumes:
          - name: spark-job-config
            configMap:
              name: feature-engineering-job-config
          restartPolicy: OnFailure
EOF

# Create ConfigMap for the Spark job
kubectl create configmap feature-engineering-job-config -n mlops --from-file=batch-feature-engineering-job.yaml=kubernetes/feature-engineering/batch-feature-engineering-job.yaml --dry-run=client -o yaml | kubectl apply -f -

# Apply the CronJob
kubectl apply -f kubernetes/feature-engineering/feature-engineering-cronjob.yaml
echo -e "${GREEN}CronJob for scheduled feature engineering created.${NC}"
echo ""

# Create the feature validation service
echo -e "${YELLOW}Creating Feature Validation Service...${NC}"
cat <<EOF > kubernetes/feature-engineering/feature-validation.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: feature-validation-config
  namespace: mlops
data:
  config.yaml: |
    validation:
      # Feature Statistics Validation
      statistics:
        enabled: true
        min_samples: 100
        check_completeness: true
        completeness_threshold: 0.95
        check_distribution: true
        distribution_threshold: 0.1
      
      # Feature Value Validation
      value:
        enabled: true
        types:
          numeric:
            check_range: true
            check_variance: true
            check_zeros: true
          categorical:
            check_cardinality: true
            max_cardinality: 1000
          timestamp:
            check_range: true
            check_future: true
      
      # Feature Drift Detection
      drift:
        enabled: true
        window_size: 7
        threshold: 0.05
        metrics:
          - psi
          - kl_divergence
          - ks_test
      
      # Reporting
      reporting:
        store_results: true
        generate_dashboard: true
        alert_on_failure: true
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: feature-validation
  namespace: mlops
spec:
  replicas: 1
  selector:
    matchLabels:
      app: feature-validation
  template:
    metadata:
      labels:
        app: feature-validation
    spec:
      containers:
      - name: feature-validation
        image: python:3.9-slim
        command:
        - /bin/sh
        - -c
        - |
          pip install fastapi uvicorn pandas numpy scikit-learn great-expectations psycopg2-binary requests redis && 
          mkdir -p /app && 
          while true; do
            echo "Feature validation service running. Implement validation API here."
            sleep 3600
          done
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: 500m
            memory: 512Mi
          requests:
            cpu: 200m
            memory: 256Mi
        env:
        - name: POSTGRES_HOST
          value: postgres.storage.svc.cluster.local
        - name: POSTGRES_PORT
          value: "5432"
        - name: POSTGRES_DB
          value: mlops
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        - name: FEATURE_STORE_URL
          value: http://feature-store.mlops.svc.cluster.local:8000
        - name: FEATURE_REGISTRY_URL
          value: http://feature-registry.mlops.svc.cluster.local:8000
        - name: VALIDATION_CONFIG_PATH
          value: /etc/config/config.yaml
        volumeMounts:
        - name: validation-config
          mountPath: /etc/config
      volumes:
      - name: validation-config
        configMap:
          name: feature-validation-config
---
apiVersion: v1
kind: Service
metadata:
  name: feature-validation
  namespace: mlops
spec:
  selector:
    app: feature-validation
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
EOF

# Apply the Feature Validation configuration
kubectl apply -f kubernetes/feature-engineering/feature-validation.yaml
echo -e "${GREEN}Feature Validation Service created.${NC}"
echo ""

# Create a Python script for batch feature engineering
echo -e "${YELLOW}Creating batch feature engineering script...${NC}"
cat <<EOF > src/feature_engineering/batch_feature_engineer.py
#!/usr/bin/env python3
"""
Batch Feature Engineering Job

This script is designed to be run as a Spark job to compute
features in batch mode and store them in the Feature Store.
It's optimized for AWS Free Tier with minimal resource usage.
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
import requests
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, udf, datediff, current_timestamp, count, sum,
    avg, max, min, expr, to_timestamp, window, explode
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    IntegerType, TimestampType, ArrayType, MapType
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BatchFeatureEngineer")

# Environment Variables
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres.storage.svc.cluster.local")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "mlops")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
FEATURE_STORE_URL = os.environ.get("FEATURE_STORE_URL", "http://feature-store.mlops.svc.cluster.local:8000")
FEATURE_REGISTRY_URL = os.environ.get("FEATURE_REGISTRY_URL", "http://feature-registry.mlops.svc.cluster.local:8000")


class BatchFeatureEngineer:
    """
    Batch Feature Engineering Pipeline.
    
    This class implements batch processing for feature engineering,
    calculating features based on historical data and storing them
    in the feature store.
    """
    
    def __init__(self):
        """Initialize the batch feature engineering pipeline."""
        self.spark = self._create_spark_session()
        
    def _create_spark_session(self) -> SparkSession:
        """Create and configure a Spark session optimized for AWS Free Tier."""
        return (
            SparkSession.builder
            .appName("BatchFeatureEngineering")
            .config("spark.executor.memory", "1g")
            .config("spark.driver.memory", "1g")
            .config("spark.executor.cores", "1")
            .config("spark.driver.cores", "1")
            .config("spark.default.parallelism", "4")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.memory.fraction", "0.7")
            .config("spark.memory.storageFraction", "0.3")
            .config("spark.rdd.compress", "true")
            .config("spark.streaming.backpressure.enabled", "true")
            .getOrCreate()
        )
    
    def compute_customer_features(self, lookback_days: int = 30):
        """
        Compute customer features based on historical data.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        logger.info(f"Computing customer features with {lookback_days} days lookback")
        
        # Example: Read customer events from PostgreSQL
        customer_events_df = (
            self.spark.read
            .format("jdbc")
            .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
            .option("user", POSTGRES_USER)
            .option("password", POSTGRES_PASSWORD)
            .option("dbtable", "customer_events")
            .load()
        )
        
        # Example: Register as temp view for SQL queries
        customer_events_df.createOrReplaceTempView("customer_events")
        
        # Example: Compute recency features
        recency_df = self.spark.sql(f"""
            SELECT 
                customer_id,
                MAX(event_timestamp) as last_active_timestamp,
                DATEDIFF(CURRENT_TIMESTAMP(), MAX(event_timestamp)) as days_since_last_active
            FROM 
                customer_events
            WHERE 
                event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL {lookback_days} DAYS
            GROUP BY 
                customer_id
        """)
        
        # Example: Compute frequency features
        frequency_df = self.spark.sql(f"""
            SELECT 
                customer_id,
                COUNT(*) as event_count,
                COUNT(DISTINCT DATE(event_timestamp)) as active_days
            FROM 
                customer_events
            WHERE 
                event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL {lookback_days} DAYS
            GROUP BY 
                customer_id
        """)
        
        # Example: Join features
        customer_features_df = recency_df.join(frequency_df, on="customer_id", how="outer")
        
        # Example: Compute additional features
        # ... add more feature computations here ...
        
        # Convert to pandas for easier API integration
        customer_features_pd = customer_features_df.toPandas()
        
        # Store features in feature store
        self._store_features(customer_features_pd, "customer")
        
        logger.info(f"Computed and stored features for {len(customer_features_pd)} customers")
        
        return customer_features_df
    
    def compute_product_features(self, lookback_days: int = 30):
        """
        Compute product features based on historical data.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        logger.info(f"Computing product features with {lookback_days} days lookback")
        
        # Example: Read product events from PostgreSQL
        product_events_df = (
            self.spark.read
            .format("jdbc")
            .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
            .option("user", POSTGRES_USER)
            .option("password", POSTGRES_PASSWORD)
            .option("dbtable", "product_events")
            .load()
        )
        
        # Example: Register as temp view for SQL queries
        product_events_df.createOrReplaceTempView("product_events")
        
        # Example: Compute popularity features
        popularity_df = self.spark.sql(f"""
            SELECT 
                product_id,
                COUNT(*) as view_count,
                SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) as purchase_count,
                SUM(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) as cart_count
            FROM 
                product_events
            WHERE 
                event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL {lookback_days} DAYS
            GROUP BY 
                product_id
        """)
        
        # Example: Compute additional product features
        # ... add more feature computations here ...
        
        # Convert to pandas for easier API integration
        product_features_pd = popularity_df.toPandas()
        
        # Store features in feature store
        self._store_features(product_features_pd, "product")
        
        logger.info(f"Computed and stored features for {len(product_features_pd)} products")
        
        return popularity_df
    
    def compute_customer_product_features(self, lookback_days: int = 90):
        """
        Compute customer-product interaction features for recommendations.
        
        Args:
            lookback_days: Number of days to look back for feature computation
        """
        logger.info(f"Computing customer-product features with {lookback_days} days lookback")
        
        # Example: Read customer-product interactions from PostgreSQL
        interactions_df = (
            self.spark.read
            .format("jdbc")
            .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
            .option("user", POSTGRES_USER)
            .option("password", POSTGRES_PASSWORD)
            .option("dbtable", "customer_product_interactions")
            .load()
        )
        
        # Example: Register as temp view for SQL queries
        interactions_df.createOrReplaceTempView("interactions")
        
        # Example: Compute interaction features
        cp_features_df = self.spark.sql(f"""
            SELECT 
                customer_id,
                product_id,
                COUNT(*) as interaction_count,
                SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) as view_count,
                SUM(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) as cart_count,
                SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) as purchase_count,
                MAX(event_timestamp) as last_interaction_time
            FROM 
                interactions
            WHERE 
                event_timestamp >= CURRENT_TIMESTAMP() - INTERVAL {lookback_days} DAYS
            GROUP BY 
                customer_id, product_id
        """)
        
        # Example: Compute additional features
        # ... add more feature computations here ...
        
        # Convert to pandas for easier API integration
        cp_features_pd = cp_features_df.toPandas()
        
        # Store features in feature store
        self._store_customer_product_features(cp_features_pd)
        
        logger.info(f"Computed and stored {len(cp_features_pd)} customer-product interaction features")
        
        return cp_features_df
    
    def _store_features(self, features_df: pd.DataFrame, entity_type: str):
        """
        Store features in the feature store.
        
        Args:
            features_df: DataFrame with feature values
            entity_type: Type of entity (customer, product, etc.)
        """
        id_column = f"{entity_type}_id"
        
        # Check if DataFrame has data
        if features_df.empty:
            logger.warning(f"No {entity_type} features to store")
            return
        
        # Ensure ID column exists
        if id_column not in features_df.columns:
            logger.error(f"ID column {id_column} not found in DataFrame")
            return
        
        # Store features for each entity
        for _, row in features_df.iterrows():
            entity_id = row[id_column]
            
            # Create feature dictionary
            feature_values = {}
            for col in features_df.columns:
                if col != id_column:
                    # Convert numpy types to Python types for JSON serialization
                    value = row[col]
                    if pd.isna(value):
                        continue
                    
                    if hasattr(value, 'item'):
                        value = value.item()
                    
                    feature_values[col] = value
            
            # Skip if no features to store
            if not feature_values:
                continue
            
            # Call Feature Store API
            try:
                response = requests.post(
                    f"{FEATURE_STORE_URL}/store/{entity_type}/{entity_id}",
                    json=feature_values
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to store {entity_type} features for {entity_id}: {response.text}")
            except Exception as e:
                logger.error(f"Error storing {entity_type} features for {entity_id}: {str(e)}")
    
    def _store_customer_product_features(self, cp_features_df: pd.DataFrame):
        """
        Store customer-product features in the feature store.
        
        Args:
            cp_features_df: DataFrame with customer-product feature values
        """
        # Check if DataFrame has data
        if cp_features_df.empty:
            logger.warning("No customer-product features to store")
            return
        
        # Ensure required columns exist
        required_columns = ["customer_id", "product_id"]
        for column in required_columns:
            if column not in cp_features_df.columns:
                logger.error(f"Required column {column} not found in DataFrame")
                return
        
        # Store features for each customer-product pair
        for _, row in cp_features_df.iterrows():
            customer_id = row["customer_id"]
            product_id = row["product_id"]
            
            # Create feature dictionary
            feature_values = {}
            for col in cp_features_df.columns:
                if col not in required_columns:
                    # Convert numpy types to Python types for JSON serialization
                    value = row[col]
                    if pd.isna(value):
                        continue
                    
                    if hasattr(value, 'item'):
                        value = value.item()
                    
                    feature_values[col] = value
            
            # Skip if no features to store
            if not feature_values:
                continue
            
            # Call Feature Store API
            try:
                response = requests.post(
                    f"{FEATURE_STORE_URL}/store/customer_product/{customer_id}/{product_id}",
                    json=feature_values
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to store customer-product features for {customer_id}-{product_id}: {response.text}")
            except Exception as e:
                logger.error(f"Error storing customer-product features for {customer_id}-{product_id}: {str(e)}")
    
    def run_feature_computation(self, feature_types: Optional[List[str]] = None, lookback_days: int = 30):
        """
        Run feature computation for specified types.
        
        Args:
            feature_types: List of feature types to compute (customer, product, customer_product)
            lookback_days: Number of days to look back for feature computation
        """
        if feature_types is None:
            feature_types = ["customer", "product", "customer_product"]
        
        if "customer" in feature_types:
            self.compute_customer_features(lookback_days)
        
        if "product" in feature_types:
            self.compute_product_features(lookback_days)
        
        if "customer_product" in feature_types:
            self.compute_customer_product_features(lookback_days)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Batch Feature Engineering Job")
    
    parser.add_argument(
        "--feature-types",
        type=str,
        help="Comma-separated list of feature types to compute: customer,product,customer_product"
    )
    
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Number of days to look back for feature computation"
    )
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()
    
    # Parse feature types
    feature_types = None
    if args.feature_types:
        feature_types = [ft.strip() for ft in args.feature_types.split(",")]
    
    try:
        # Initialize feature engineer
        feature_engineer = BatchFeatureEngineer()
        
        # Run feature computation
        feature_engineer.run_feature_computation(
            feature_types=feature_types,
            lookback_days=args.lookback_days
        )
        
        logger.info("Feature computation completed successfully")
    except Exception as e:
        logger.error(f"Error in feature computation: {str(e)}")
        sys.exit(1)
    finally:
        # Stop Spark session
        SparkSession.builder.getOrCreate().stop()


if __name__ == "__main__":
    main()
EOF

echo -e "${GREEN}Batch feature engineering script created.${NC}"
echo ""

# Make the batch feature engineering script executable
chmod +x src/feature_engineering/batch_feature_engineer.py

# Print completion message
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   MLOps Platform Feature Engineering Deployed!   ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo ""
echo -e "Components deployed:"
echo -e "  - ${YELLOW}Feature Registry API${NC} (namespace: mlops)"
echo -e "  - ${YELLOW}Feature Store API${NC} (namespace: mlops)"
echo -e "  - ${YELLOW}Feature Validation Service${NC} (namespace: mlops)"
echo -e "  - ${YELLOW}Batch Feature Engineering${NC} (SparkApplication in namespace: spark)"
echo -e "  - ${YELLOW}Feature Engineering Scheduler${NC} (CronJob in namespace: mlops)"
echo ""
echo -e "Next steps:"
echo -e "  1. Build and push the Spark Docker image if not already done:"
echo -e "     ${YELLOW}./build-spark-image.sh${NC}"
echo -e "  2. Update the Feature Registry with your feature definitions"
echo -e "  3. Run the batch feature engineering job manually to test:"
echo -e "     ${YELLOW}kubectl create -f kubernetes/feature-engineering/batch-feature-engineering-job.yaml${NC}"
echo -e "  4. Access the Feature Registry API: ${YELLOW}kubectl port-forward svc/feature-registry 8000:8000 -n mlops${NC}"
echo -e "  5. Access the Feature Store API: ${YELLOW}kubectl port-forward svc/feature-store 8001:8000 -n mlops${NC}"
echo ""
echo -e "${GREEN}======================================================${NC}" 