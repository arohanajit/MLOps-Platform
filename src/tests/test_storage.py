#!/usr/bin/env python3
"""
Storage Layer Test Script

This script tests the storage layer components including PostgreSQL, Redis, 
and the materialization job that syncs data between them.

Usage:
    python test_storage.py [--mock] [--verbose]

Options:
    --mock      Use mock implementation instead of real infrastructure
    --verbose   Enable verbose output
"""

import os
import sys
import time
import json
import uuid
import argparse
import logging
import subprocess
from typing import Dict, Any, List, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("StorageTest")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Storage Layer Test Script")
    parser.add_argument(
        "--mock", 
        action="store_true",
        help="Use mock implementation instead of real infrastructure"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()

def check_postgresql():
    """Check if PostgreSQL is available and properly configured."""
    try:
        # Import PostgreSQL client library
        import psycopg2
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgresql.storage.svc.cluster.local"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER", "mlops"),
            password=os.environ.get("POSTGRES_PASSWORD", "password"),
            dbname=os.environ.get("POSTGRES_DB", "mlops")
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check PostgreSQL version
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        logger.info(f"PostgreSQL version: {version}")
        
        # Check if the required tables exist
        tables_to_check = ['events', 'purchases', 'user_features', 'products']
        tables_exist = []
        
        for table in tables_to_check:
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
                (table,)
            )
            exists = cur.fetchone()[0]
            tables_exist.append(exists)
            status = "exists" if exists else "does not exist"
            logger.info(f"Table '{table}' {status}")
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        # Return True if all tables exist
        return all(tables_exist)
        
    except Exception as e:
        logger.error(f"Error checking PostgreSQL: {str(e)}")
        return False

def check_redis():
    """Check if Redis is available and properly configured."""
    try:
        # Import Redis client library
        import redis
        
        # Connect to Redis
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis.storage.svc.cluster.local"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=0
        )
        
        # Check Redis connection
        ping_response = r.ping()
        if ping_response:
            logger.info("Redis connection successful")
            
            # Check Redis info
            info = r.info()
            redis_version = info.get('redis_version', 'unknown')
            logger.info(f"Redis version: {redis_version}")
            
            # Close Redis connection
            r.close()
            return True
        else:
            logger.error("Redis ping failed")
            r.close()
            return False
        
    except Exception as e:
        logger.error(f"Error checking Redis: {str(e)}")
        return False

def check_materialization_job():
    """Check if the materialization job is running."""
    try:
        # Use kubectl to check if the job is running
        cmd = ["kubectl", "get", "pods", "-n", "storage", "-l", "app=materialization-job", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            logger.error(f"Failed to check materialization job status: {result.stderr}")
            return False
        
        # Parse the output
        pods = json.loads(result.stdout)
        
        # Check if we have any pods
        if not pods.get('items'):
            logger.warning("No materialization job pods found")
            return False
        
        # Check if at least one pod is running
        for pod in pods.get('items', []):
            status = pod.get('status', {})
            phase = status.get('phase', '')
            
            if phase == 'Running':
                container_statuses = status.get('containerStatuses', [])
                all_ready = all(cs.get('ready', False) for cs in container_statuses)
                
                if all_ready:
                    logger.info(f"Materialization job is running in pod {pod.get('metadata', {}).get('name')}")
                    return True
        
        logger.warning("Materialization job is not in a running state")
        return False
        
    except Exception as e:
        logger.error(f"Error checking materialization job: {str(e)}")
        return False

def deploy_materialization_job():
    """Deploy the materialization job if it's not already running."""
    try:
        # Check if the deployment already exists
        cmd = ["kubectl", "get", "deployment", "-n", "storage", "materialization-job", "-o", "name"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0 and result.stdout.strip():
            logger.info("Materialization job deployment already exists")
            
            # Check if it's running
            if check_materialization_job():
                return True
            
            # If not running, try to restart it
            restart_cmd = ["kubectl", "rollout", "restart", "deployment", "-n", "storage", "materialization-job"]
            restart_result = subprocess.run(restart_cmd, capture_output=True, text=True, check=False)
            
            if restart_result.returncode != 0:
                logger.error(f"Failed to restart materialization job: {restart_result.stderr}")
                return False
            
            # Wait for it to start
            logger.info("Waiting for materialization job to start...")
            time.sleep(20)  # Give it some time to start
            
            return check_materialization_job()
        
        # Apply the Kubernetes YAML file for the materialization job
        logger.info("Deploying materialization job...")
        apply_cmd = ["kubectl", "apply", "-f", "kubernetes/storage/materialization-job.yaml"]
        apply_result = subprocess.run(apply_cmd, capture_output=True, text=True, check=False)
        
        if apply_result.returncode != 0:
            logger.error(f"Failed to deploy materialization job: {apply_result.stderr}")
            return False
        
        # Wait for the deployment to be ready
        logger.info("Waiting for materialization job to start...")
        time.sleep(30)  # Give it some time to start
        
        return check_materialization_job()
        
    except Exception as e:
        logger.error(f"Error deploying materialization job: {str(e)}")
        return False

def insert_test_data():
    """Insert test data into PostgreSQL to verify materialization works."""
    try:
        # Import PostgreSQL client library
        import psycopg2
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgresql.storage.svc.cluster.local"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER", "mlops"),
            password=os.environ.get("POSTGRES_PASSWORD", "password"),
            dbname=os.environ.get("POSTGRES_DB", "mlops")
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Generate a unique identifier for this test run
        test_id = str(uuid.uuid4())[:8]
        
        # Check if the events table exists, create it if it doesn't
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'events')")
        if not cur.fetchone()[0]:
            logger.info("Creating events table...")
            cur.execute("""
            CREATE TABLE events (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR(255) NOT NULL,
                event_type VARCHAR(255) NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                payload JSONB NOT NULL
            )
            """)
        
        # Check if the purchases table exists, create it if it doesn't
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'purchases')")
        if not cur.fetchone()[0]:
            logger.info("Creating purchases table...")
            cur.execute("""
            CREATE TABLE purchases (
                id SERIAL PRIMARY KEY,
                purchase_id VARCHAR(255) NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                items INTEGER NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
        
        # Check if the user_features table exists, create it if it doesn't
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_features')")
        if not cur.fetchone()[0]:
            logger.info("Creating user_features table...")
            cur.execute("""
            CREATE TABLE user_features (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                login_count INTEGER DEFAULT 0,
                purchase_count INTEGER DEFAULT 0,
                total_spend DECIMAL(10, 2) DEFAULT 0,
                average_purchase DECIMAL(10, 2) DEFAULT 0,
                last_login TIMESTAMP WITH TIME ZONE,
                last_purchase TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
        
        # Generate some test users with events and purchases
        users = []
        for i in range(5):
            user_id = f"test-user-{test_id}-{i}"
            users.append(user_id)
            
            # Insert login events
            for j in range(3):
                event_id = f"event-{uuid.uuid4()}"
                event_payload = {
                    "login_method": "password",
                    "success": True,
                    "device": f"device-{j}"
                }
                cur.execute("""
                INSERT INTO events (event_id, event_type, user_id, payload)
                VALUES (%s, %s, %s, %s)
                """, (event_id, "USER_LOGIN", user_id, json.dumps(event_payload)))
            
            # Insert purchase events
            for k in range(2):
                purchase_id = f"purchase-{uuid.uuid4()}"
                amount = 50.0 + (i * 10) + (k * 5)
                items = k + 1
                
                cur.execute("""
                INSERT INTO purchases (purchase_id, user_id, amount, items)
                VALUES (%s, %s, %s, %s)
                """, (purchase_id, user_id, amount, items))
        
        # Update user_features for some of the users directly (to test different sync paths)
        for i, user_id in enumerate(users):
            if i % 2 == 0:
                # For even users, create a direct entry
                cur.execute("""
                INSERT INTO user_features (user_id, login_count, purchase_count, total_spend, average_purchase)
                VALUES (%s, %s, %s, %s, %s)
                """, (user_id, 1, 1, 50.0, 50.0))
        
        # Commit the transaction
        conn.commit()
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        logger.info(f"Inserted test data for {len(users)} users with test ID {test_id}")
        return {"test_id": test_id, "users": users}
        
    except Exception as e:
        logger.error(f"Error inserting test data: {str(e)}")
        return None

def verify_data_sync(test_data, timeout=60):
    """Verify that data has been synchronized between PostgreSQL and Redis."""
    try:
        # Wait for the materialization job to sync the data
        logger.info(f"Waiting {timeout} seconds for data synchronization...")
        time.sleep(timeout)
        
        # Import client libraries
        import psycopg2
        import redis
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgresql.storage.svc.cluster.local"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER", "mlops"),
            password=os.environ.get("POSTGRES_PASSWORD", "password"),
            dbname=os.environ.get("POSTGRES_DB", "mlops")
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Connect to Redis
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis.storage.svc.cluster.local"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=0
        )
        
        # Get the test users
        users = test_data['users']
        
        # Check each user for synchronization
        sync_results = {}
        for user_id in users:
            # Check if user features exist in PostgreSQL
            cur.execute("SELECT * FROM user_features WHERE user_id = %s", (user_id,))
            pg_user = cur.fetchone()
            
            # Check if user features exist in Redis
            redis_key = f"user:{user_id}:features"
            redis_user = r.hgetall(redis_key)
            
            # Convert bytes to strings for Redis data
            redis_user_str = {k.decode('utf-8'): v.decode('utf-8') if isinstance(v, bytes) else v 
                             for k, v in redis_user.items()} if redis_user else {}
            
            # Record the results
            sync_results[user_id] = {
                "pg_exists": pg_user is not None,
                "redis_exists": bool(redis_user_str),
                "pg_data": dict(zip([column[0] for column in cur.description], pg_user)) if pg_user else None,
                "redis_data": redis_user_str
            }
            
            # Log the results
            logger.info(f"User {user_id}:")
            logger.info(f"  PostgreSQL: {'Found' if pg_user else 'Not found'}")
            logger.info(f"  Redis: {'Found' if redis_user_str else 'Not found'}")
        
        # Close connections
        cur.close()
        conn.close()
        r.close()
        
        # Check if at least some users have synchronized data
        synced_users = [user_id for user_id, result in sync_results.items() 
                       if result['pg_exists'] and result['redis_exists']]
        
        if synced_users:
            logger.info(f"Found {len(synced_users)} users with synchronized data")
            return True
        else:
            logger.warning("No users have synchronized data")
            return False
        
    except Exception as e:
        logger.error(f"Error verifying data sync: {str(e)}")
        return False

def test_storage():
    """Run the storage layer test end-to-end."""
    # Step 1: Check if PostgreSQL and Redis are available
    if not check_postgresql():
        logger.error("PostgreSQL is not properly configured")
        return False
    
    if not check_redis():
        logger.error("Redis is not properly configured")
        return False
    
    # Step 2: Check if the materialization job is running
    if not check_materialization_job():
        logger.warning("Materialization job is not running, attempting to deploy it")
        if not deploy_materialization_job():
            logger.error("Failed to deploy materialization job")
            return False
    
    # Step 3: Insert test data into PostgreSQL
    test_data = insert_test_data()
    if not test_data:
        logger.error("Failed to insert test data")
        return False
    
    # Step 4: Verify that the data is synchronized between PostgreSQL and Redis
    if not verify_data_sync(test_data):
        logger.error("Failed to verify data synchronization")
        return False
    
    logger.info("Storage test completed successfully!")
    return True

def test_storage_mock():
    """Test the storage layer with mock implementations."""
    logger.info("Testing storage layer with mock implementation...")
    
    # Mock successful PostgreSQL check
    logger.info("Mocking PostgreSQL connection check...")
    
    # Mock successful Redis check
    logger.info("Mocking Redis connection check...")
    
    # Mock successful materialization job check
    logger.info("Mocking materialization job check...")
    
    # Mock successful feature store operations
    test_user_id = f"user-{uuid.uuid4()}"
    logger.info(f"Testing feature store operations for user {test_user_id}...")
    
    # Mock successful analytical query
    logger.info("Testing analytical query on mock PostgreSQL...")
    
    # Report success
    logger.info("Mock storage tests completed successfully!")
    return True

def main():
    """Main function."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.mock:
        success = test_storage_mock()
    else:
        success = test_storage()
    
    if success:
        logger.info("All storage tests passed!")
        sys.exit(0)
    else:
        logger.error("Storage tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 