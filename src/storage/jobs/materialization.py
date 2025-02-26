import os
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import redis
from redis.commands.json.path import Path
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MaterializationJob")

# Environment variables with defaults
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "mlops-postgres-dev.database_endpoint_here")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "mlops")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

REDIS_HOST = os.environ.get("REDIS_HOST", "mlops-redis-cache-dev.redis_endpoint_here")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# Job configuration
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1000"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
TTL_SECONDS = int(os.environ.get("TTL_SECONDS", "86400"))  # 1 day default

class MaterializationJob:
    """
    Job to materialize data between PostgreSQL and Redis.
    
    This job synchronizes data between the offline store (PostgreSQL)
    and the online store (Redis) for low-latency feature access.
    """
    
    def __init__(self):
        """Initialize connections to PostgreSQL and Redis."""
        self.postgres_uri = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        self.engine = create_engine(self.postgres_uri)
        
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        logger.info("Materialization job initialized")
        
    def _get_postgres_connection(self):
        """Get a connection to PostgreSQL."""
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            return conn
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {str(e)}")
            raise
            
    def sync_users(self) -> int:
        """
        Sync user data from PostgreSQL to Redis.
        
        Returns:
            Number of users synchronized
        """
        logger.info("Syncing users from PostgreSQL to Redis")
        
        try:
            # Query users from PostgreSQL
            query = """
            SELECT user_id, username, email, 
                   created_at, updated_at, last_login
            FROM public.users
            WHERE updated_at > NOW() - INTERVAL '1 day'
            """
            
            df = pd.read_sql(query, self.engine)
            count = len(df)
            
            if count == 0:
                logger.info("No users to sync")
                return 0
                
            logger.info(f"Syncing {count} users to Redis")
            
            # Convert timestamps to strings for JSON serialization
            for col in ['created_at', 'updated_at', 'last_login']:
                if col in df.columns:
                    df[col] = df[col].astype(str)
            
            # Write to Redis
            for _, row in df.iterrows():
                user_data = row.to_dict()
                user_id = user_data.pop('user_id')
                
                # Store in Redis with TTL
                self.redis.json().set(f"user:{user_id}", Path.root_path(), user_data)
                self.redis.expire(f"user:{user_id}", TTL_SECONDS)
            
            logger.info(f"Successfully synced {count} users to Redis")
            return count
            
        except Exception as e:
            logger.error(f"Error syncing users: {str(e)}")
            return 0
    
    def sync_products(self) -> int:
        """
        Sync product data from PostgreSQL to Redis.
        
        Returns:
            Number of products synchronized
        """
        logger.info("Syncing products from PostgreSQL to Redis")
        
        try:
            # Query products from PostgreSQL
            query = """
            SELECT product_id, name, description, price, 
                   inventory, category, created_at, updated_at
            FROM public.products
            WHERE updated_at > NOW() - INTERVAL '1 day'
            """
            
            df = pd.read_sql(query, self.engine)
            count = len(df)
            
            if count == 0:
                logger.info("No products to sync")
                return 0
                
            logger.info(f"Syncing {count} products to Redis")
            
            # Convert timestamps and decimal values to strings for JSON serialization
            for col in ['created_at', 'updated_at']:
                if col in df.columns:
                    df[col] = df[col].astype(str)
            
            # Write to Redis
            for _, row in df.iterrows():
                product_data = row.to_dict()
                product_id = product_data.pop('product_id')
                
                # Convert numeric types to make them JSON serializable
                if 'price' in product_data:
                    product_data['price'] = float(product_data['price'])
                
                # Store in Redis with TTL
                self.redis.json().set(f"product:{product_id}", Path.root_path(), product_data)
                self.redis.expire(f"product:{product_id}", TTL_SECONDS)
            
            logger.info(f"Successfully synced {count} products to Redis")
            return count
            
        except Exception as e:
            logger.error(f"Error syncing products: {str(e)}")
            return 0
    
    def sync_orders(self) -> int:
        """
        Sync recent order data from PostgreSQL to Redis.
        
        Returns:
            Number of orders synchronized
        """
        logger.info("Syncing orders from PostgreSQL to Redis")
        
        try:
            # Query orders from PostgreSQL
            query = """
            SELECT o.order_id, o.user_id, o.order_date, o.status, 
                   o.total_amount, o.created_at, o.updated_at,
                   json_agg(json_build_object(
                     'product_id', oi.product_id,
                     'quantity', oi.quantity,
                     'price', oi.price
                   )) as items
            FROM public.orders o
            JOIN public.order_items oi ON o.order_id = oi.order_id
            WHERE o.updated_at > NOW() - INTERVAL '1 day'
            GROUP BY o.order_id
            """
            
            conn = self._get_postgres_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query)
            
            count = 0
            for row in cursor:
                row_dict = dict(row)
                order_id = row_dict.pop('order_id')
                
                # Convert timestamps and decimal values to strings for JSON serialization
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                    elif hasattr(value, 'to_json'):  # For Decimal and other custom types
                        row_dict[key] = float(value)
                
                # Store in Redis with TTL
                self.redis.json().set(f"order:{order_id}", Path.root_path(), row_dict)
                self.redis.expire(f"order:{order_id}", TTL_SECONDS)
                count += 1
            
            cursor.close()
            conn.close()
            
            logger.info(f"Successfully synced {count} orders to Redis")
            return count
            
        except Exception as e:
            logger.error(f"Error syncing orders: {str(e)}")
            return 0
    
    def sync_user_features(self) -> int:
        """
        Create and sync user feature vectors for machine learning.
        
        Returns:
            Number of user feature vectors synchronized
        """
        logger.info("Creating and syncing user feature vectors")
        
        try:
            # Query to create user features from order history
            query = """
            WITH user_order_stats AS (
                SELECT
                    u.user_id,
                    COUNT(o.order_id) AS order_count,
                    COALESCE(SUM(o.total_amount), 0) AS total_spent,
                    COALESCE(AVG(o.total_amount), 0) AS avg_order_value,
                    COALESCE(MAX(o.order_date), u.created_at) AS last_order_date,
                    NOW() - COALESCE(MAX(o.order_date), u.created_at) AS time_since_last_order
                FROM
                    public.users u
                LEFT JOIN
                    public.orders o ON u.user_id = o.user_id
                GROUP BY
                    u.user_id
            ),
            product_categories AS (
                SELECT
                    o.user_id,
                    p.category,
                    COUNT(*) AS purchase_count
                FROM
                    public.orders o
                JOIN
                    public.order_items oi ON o.order_id = oi.order_id
                JOIN
                    public.products p ON oi.product_id = p.product_id
                GROUP BY
                    o.user_id, p.category
            ),
            category_pivots AS (
                SELECT
                    user_id,
                    SUM(CASE WHEN category = 'Electronics' THEN purchase_count ELSE 0 END) AS electronics_count,
                    SUM(CASE WHEN category = 'Audio' THEN purchase_count ELSE 0 END) AS audio_count
                FROM
                    product_categories
                GROUP BY
                    user_id
            )
            SELECT
                s.user_id,
                s.order_count,
                s.total_spent,
                s.avg_order_value,
                EXTRACT(EPOCH FROM s.time_since_last_order) / 86400 AS days_since_last_order,
                COALESCE(p.electronics_count, 0) AS electronics_purchases,
                COALESCE(p.audio_count, 0) AS audio_purchases
            FROM
                user_order_stats s
            LEFT JOIN
                category_pivots p ON s.user_id = p.user_id
            """
            
            df = pd.read_sql(query, self.engine)
            count = len(df)
            
            if count == 0:
                logger.info("No user features to sync")
                return 0
                
            logger.info(f"Syncing {count} user feature vectors to Redis")
            
            # Write to Redis
            for _, row in df.iterrows():
                user_data = row.to_dict()
                user_id = user_data.pop('user_id')
                
                # Convert numeric types to make them JSON serializable
                for key, value in user_data.items():
                    if pd.isna(value):
                        user_data[key] = 0
                    elif hasattr(value, 'item'):  # numpy types
                        user_data[key] = value.item()
                
                # Store in Redis with TTL
                self.redis.json().set(f"user_features:{user_id}", Path.root_path(), user_data)
                self.redis.expire(f"user_features:{user_id}", TTL_SECONDS)
            
            logger.info(f"Successfully synced {count} user feature vectors to Redis")
            return count
            
        except Exception as e:
            logger.error(f"Error syncing user features: {str(e)}")
            return 0
    
    def run(self):
        """Run the materialization job continuously."""
        logger.info(f"Starting materialization job with {SYNC_INTERVAL_SECONDS} second interval")
        
        while True:
            try:
                start_time = time.time()
                
                # Sync different data types
                users_count = self.sync_users()
                products_count = self.sync_products()
                orders_count = self.sync_orders()
                features_count = self.sync_user_features()
                
                total_count = users_count + products_count + orders_count + features_count
                execution_time = time.time() - start_time
                
                logger.info(f"Materialization job completed: synced {total_count} items in {execution_time:.2f} seconds")
                
                # Sleep until next interval
                time_to_sleep = max(0, SYNC_INTERVAL_SECONDS - execution_time)
                if time_to_sleep > 0:
                    logger.info(f"Sleeping for {time_to_sleep:.2f} seconds")
                    time.sleep(time_to_sleep)
                    
            except Exception as e:
                logger.error(f"Error in materialization job: {str(e)}")
                time.sleep(10)  # Sleep briefly on error before retrying

if __name__ == "__main__":
    job = MaterializationJob()
    job.run() 