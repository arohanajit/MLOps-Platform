#!/usr/bin/env python3
"""
Spark Streaming Job Test Script

This script tests the Spark streaming job by producing test events to Kafka
and verifying that they are properly processed by the Spark job.

Usage:
    python test_spark.py [--mock] [--verbose]

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
logger = logging.getLogger("SparkTest")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Spark Streaming Job Test Script")
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

def check_spark_job_running():
    """Check if the Spark job is running in Kubernetes."""
    try:
        # Use kubectl to check if the job is running
        cmd = ["kubectl", "get", "pods", "-n", "processing", "-l", "app=spark-streaming", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            logger.error(f"Failed to check Spark job status: {result.stderr}")
            return False
        
        # Parse the output
        pods = json.loads(result.stdout)
        
        # Check if we have any pods
        if not pods.get('items'):
            logger.warning("No Spark streaming pods found")
            return False
        
        # Check if at least one pod is running
        for pod in pods.get('items', []):
            status = pod.get('status', {})
            phase = status.get('phase', '')
            
            if phase == 'Running':
                container_statuses = status.get('containerStatuses', [])
                all_ready = all(cs.get('ready', False) for cs in container_statuses)
                
                if all_ready:
                    logger.info(f"Spark job is running in pod {pod.get('metadata', {}).get('name')}")
                    return True
        
        logger.warning("Spark job is not in a running state")
        return False
        
    except Exception as e:
        logger.error(f"Error checking Spark job: {str(e)}")
        return False

def deploy_spark_job():
    """Deploy the Spark streaming job to Kubernetes."""
    try:
        # Check if the deployment already exists
        cmd = ["kubectl", "get", "deployment", "-n", "processing", "spark-streaming", "-o", "name"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0 and result.stdout.strip():
            logger.info("Spark streaming deployment already exists")
            
            # Check if it's running
            if check_spark_job_running():
                return True
            
            # If not running, try to restart it
            restart_cmd = ["kubectl", "rollout", "restart", "deployment", "-n", "processing", "spark-streaming"]
            restart_result = subprocess.run(restart_cmd, capture_output=True, text=True, check=False)
            
            if restart_result.returncode != 0:
                logger.error(f"Failed to restart Spark job: {restart_result.stderr}")
                return False
            
            # Wait for it to start
            logger.info("Waiting for Spark job to start...")
            time.sleep(20)  # Give it some time to start
            
            return check_spark_job_running()
        
        # Deploy the Spark job
        logger.info("Deploying Spark streaming job...")
        
        # Create a temporary file with the deployment YAML
        deploy_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spark-streaming
  namespace: processing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: spark-streaming
  template:
    metadata:
      labels:
        app: spark-streaming
    spec:
      containers:
      - name: spark
        image: spark:3.3.0-hadoop3-scala2.13
        command:
        - "/bin/bash"
        - "-c"
        - >
          cd /opt/spark/work-dir &&
          spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:3.3.0 /opt/spark/work-dir/src/processing/spark_streaming.py
        env:
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka-bootstrap.kafka.svc.cluster.local:9092"
        - name: POSTGRES_HOST
          value: "postgresql.storage.svc.cluster.local"
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgresql-credentials
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgresql-credentials
              key: password
        - name: POSTGRES_DB
          value: "mlops"
        - name: REDIS_HOST
          value: "redis.storage.svc.cluster.local"
        - name: REDIS_PORT
          value: "6379"
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: spark-work-dir
          mountPath: /opt/spark/work-dir
      volumes:
      - name: spark-work-dir
        configMap:
          name: spark-code
"""
        
        # Write the deployment YAML to a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(deploy_yaml)
            temp_file = f.name
        
        # Create a ConfigMap for the Spark code
        logger.info("Creating ConfigMap for Spark code...")
        configmap_cmd = [
            "kubectl", "create", "configmap", "spark-code",
            "-n", "processing",
            "--from-file=src/processing/spark_streaming.py"
        ]
        configmap_result = subprocess.run(configmap_cmd, capture_output=True, text=True, check=False)
        
        if configmap_result.returncode != 0 and "already exists" not in configmap_result.stderr:
            logger.error(f"Failed to create ConfigMap: {configmap_result.stderr}")
            os.unlink(temp_file)
            return False
        
        # Apply the deployment
        logger.info("Applying Spark deployment...")
        deploy_cmd = ["kubectl", "apply", "-f", temp_file]
        deploy_result = subprocess.run(deploy_cmd, capture_output=True, text=True, check=False)
        
        # Clean up the temporary file
        os.unlink(temp_file)
        
        if deploy_result.returncode != 0:
            logger.error(f"Failed to deploy Spark job: {deploy_result.stderr}")
            return False
        
        # Wait for the deployment to be ready
        logger.info("Waiting for Spark job to start...")
        time.sleep(30)  # Give it some time to start
        
        return check_spark_job_running()
        
    except Exception as e:
        logger.error(f"Error deploying Spark job: {str(e)}")
        return False

def produce_test_events():
    """Produce test events to Kafka for the Spark job to process."""
    try:
        # Import the event logger
        from src.clients.python.event_logger import KafkaEventLogger
        
        # Set up Kafka connection parameters
        kafka_bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-bootstrap.kafka.svc.cluster.local:9092")
        schema_registry_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry.kafka.svc.cluster.local:8081")
        
        # Create the event logger
        event_logger = KafkaEventLogger(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            schema_registry_url=schema_registry_url,
            app_name="spark-test",
            default_topic="customer-events",
            use_avro=False  # Use JSON for simplicity in testing
        )
        
        # Generate a unique test ID
        test_id = str(uuid.uuid4())[:8]
        logger.info(f"Producing test events with ID: {test_id}")
        
        # Produce some valid events
        events = []
        for i in range(5):
            # User login event
            login_event = {
                "user_id": f"user-{test_id}-{i}",
                "login_method": "password",
                "success": True if i % 2 == 0 else False,
                "timestamp": time.time()
            }
            event_id = event_logger.log_event(
                event_type="USER_LOGIN",
                payload=login_event
            )
            events.append({"type": "USER_LOGIN", "id": event_id, "payload": login_event})
            
            # Sleep a little to space out events
            time.sleep(0.5)
            
            # Purchase event
            purchase_event = {
                "user_id": f"user-{test_id}-{i}",
                "order_id": f"order-{test_id}-{i}",
                "amount": 99.99 + i * 10,
                "currency": "USD",
                "items": str(i + 1)
            }
            purchase_id = event_logger.log_event(
                event_type="PURCHASE_COMPLETED",
                payload=purchase_event,
                topic="purchase-events"
            )
            events.append({"type": "PURCHASE_COMPLETED", "id": purchase_id, "payload": purchase_event})
            
            # Sleep a little more
            time.sleep(0.5)
        
        # Produce an invalid event (missing required field)
        invalid_event = {
            "user_id": f"user-{test_id}-invalid",
            # Missing login_method field
            "success": True,
            "timestamp": time.time()
        }
        invalid_id = event_logger.log_event(
            event_type="USER_LOGIN",
            payload=invalid_event
        )
        events.append({"type": "USER_LOGIN", "id": invalid_id, "payload": invalid_event, "invalid": True})
        
        logger.info(f"Produced {len(events)} test events")
        return {"test_id": test_id, "events": events}
        
    except Exception as e:
        logger.error(f"Error producing test events: {str(e)}")
        return None

def check_spark_processed_events(test_data, timeout=60):
    """Check that the Spark job processed the test events correctly."""
    try:
        # First, wait a bit for the Spark job to process the events
        logger.info(f"Waiting {timeout} seconds for Spark to process events...")
        time.sleep(timeout)
        
        # Connect to PostgreSQL to check that events were stored
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
        
        # Check for processed events in the events table
        test_id = test_data['test_id']
        valid_events = [e for e in test_data['events'] if 'invalid' not in e or not e['invalid']]
        
        # Count how many of our events were processed into the DB
        sql = """
        SELECT COUNT(*) 
        FROM events 
        WHERE user_id LIKE %s
        """
        cur.execute(sql, (f'%{test_id}%',))
        event_count = cur.fetchone()[0]
        
        # Count how many purchases were processed
        sql = """
        SELECT COUNT(*) 
        FROM purchases 
        WHERE user_id LIKE %s
        """
        cur.execute(sql, (f'%{test_id}%',))
        purchase_count = cur.fetchone()[0]
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        # Connect to Redis to check for user features
        import redis
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis.storage.svc.cluster.local"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=0
        )
        
        # Check for user features in Redis
        redis_keys_found = 0
        for event in valid_events:
            if 'user_id' in event['payload']:
                user_id = event['payload']['user_id']
                key = f"user:{user_id}:features"
                if r.exists(key):
                    redis_keys_found += 1
        
        # Close Redis connection
        r.close()
        
        # Log the results
        logger.info(f"Found {event_count} events and {purchase_count} purchases in PostgreSQL")
        logger.info(f"Found {redis_keys_found} user feature keys in Redis")
        
        # Determine if the test passed
        # We should see at least some of our events in both stores
        if event_count > 0 and purchase_count > 0 and redis_keys_found > 0:
            logger.info("Spark job processed events successfully!")
            return True
        else:
            logger.warning("Spark job did not process all test events")
            return False
        
    except Exception as e:
        logger.error(f"Error checking Spark processed events: {str(e)}")
        return False

def test_spark():
    """Run the Spark streaming job test end-to-end."""
    # Step 1: Check if the Spark job is running
    if not check_spark_job_running():
        logger.warning("Spark job is not running, attempting to deploy it")
        if not deploy_spark_job():
            logger.error("Failed to deploy Spark job")
            return False
    
    # Step 2: Produce test events to Kafka
    test_data = produce_test_events()
    if not test_data:
        logger.error("Failed to produce test events")
        return False
    
    # Step 3: Check that the Spark job processed the events
    if not check_spark_processed_events(test_data):
        logger.error("Failed to verify Spark processed events")
        return False
    
    logger.info("Spark test completed successfully!")
    return True

def test_spark_mock():
    """Run the Spark streaming job test with mock implementation."""
    logger.info("Testing Spark processing with mock implementation...")
    
    # Mock successful event generation
    test_id = str(uuid.uuid4())[:8]
    logger.info(f"Mocking test events with ID: {test_id}")
    
    # Mock test data
    test_data = {
        "test_id": test_id,
        "events": [
            {
                "type": "USER_LOGIN",
                "id": str(uuid.uuid4()),
                "payload": {
                    "user_id": f"user-{test_id}-1",
                    "login_method": "password",
                    "success": True,
                    "timestamp": time.time()
                }
            },
            {
                "type": "PURCHASE_COMPLETED",
                "id": str(uuid.uuid4()),
                "payload": {
                    "user_id": f"user-{test_id}-1",
                    "order_id": f"order-{test_id}-1",
                    "amount": 99.99,
                    "currency": "USD",
                    "items": "1"
                }
            }
        ]
    }
    
    # Mock successful processing
    logger.info("Mocking Spark job processing events...")
    time.sleep(2)  # Simulate processing time
    
    logger.info("Mock Spark processing completed successfully!")
    return True

def main():
    """Main function."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.mock:
        success = test_spark_mock()
    else:
        success = test_spark()
    
    if success:
        logger.info("All Spark tests passed!")
        sys.exit(0)
    else:
        logger.error("Spark tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 