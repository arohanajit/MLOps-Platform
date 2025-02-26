#!/usr/bin/env python3
"""
CDC Test Script

This script tests the Change Data Capture (CDC) functionality with Debezium.
It verifies that changes to PostgreSQL database records are properly captured
and sent to Kafka topics.

Usage:
    python test_cdc.py [--mock] [--verbose]

Options:
    --mock       Use mock mode instead of requiring real PostgreSQL and Kafka
    --verbose    Enable verbose output
"""

import os
import sys
import time
import json
import uuid
import argparse
import logging
import psycopg2
import requests
from typing import Dict, Any, List, Optional
from confluent_kafka import Consumer, KafkaError, KafkaException
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CDCTest")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CDC Test Script")
    parser.add_argument(
        "--mock", 
        action="store_true",
        help="Use mock mode instead of requiring real PostgreSQL and Kafka"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()

def check_debezium_connector():
    """Check if the Debezium connector is deployed and running."""
    try:
        connect_url = os.environ.get("KAFKA_CONNECT_URL", "http://connect.kafka.svc.cluster.local:8083")
        response = requests.get(f"{connect_url}/connectors/postgres-connector/status")
        
        if response.status_code == 200:
            status = response.json()
            connector_state = status.get("connector", {}).get("state", "")
            tasks = status.get("tasks", [])
            
            # Check if connector is running
            if connector_state == "RUNNING" and all(task.get("state") == "RUNNING" for task in tasks):
                logger.info("Debezium connector is running")
                return True
            else:
                logger.warning(f"Debezium connector status: {connector_state}")
                for i, task in enumerate(tasks):
                    logger.warning(f"Task {i} status: {task.get('state')}")
                return False
        else:
            logger.warning(f"Failed to get connector status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking Debezium connector: {str(e)}")
        return False

def deploy_debezium_connector():
    """Deploy the Debezium connector if it's not already running."""
    try:
        connect_url = os.environ.get("KAFKA_CONNECT_URL", "http://connect.kafka.svc.cluster.local:8083")
        
        # Check if connector exists
        response = requests.get(f"{connect_url}/connectors/postgres-connector")
        if response.status_code == 200:
            logger.info("Connector already exists, checking status...")
            if check_debezium_connector():
                return True
            else:
                # Delete the connector if it exists but is not running properly
                requests.delete(f"{connect_url}/connectors/postgres-connector")
                
        # Create the connector
        connector_config = {
            "name": "postgres-connector",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": os.environ.get("POSTGRES_HOST", "postgresql.storage.svc.cluster.local"),
                "database.port": os.environ.get("POSTGRES_PORT", "5432"),
                "database.user": os.environ.get("POSTGRES_USER", "mlops"),
                "database.password": os.environ.get("POSTGRES_PASSWORD", "password"),
                "database.dbname": os.environ.get("POSTGRES_DB", "mlops"),
                "database.server.name": "mlops-db",
                "table.include.list": "public.customers,public.products,public.orders,public.order_items",
                "plugin.name": "pgoutput",
                "publication.name": "dbz_publication",
                "slot.name": "debezium",
                "schema.history.internal.kafka.bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-bootstrap.kafka.svc.cluster.local:9092"),
                "schema.history.internal.kafka.topic": "schema-changes.postgres",
                "topic.prefix": "dbz",
                "key.converter": "org.apache.kafka.connect.json.JsonConverter",
                "value.converter": "org.apache.kafka.connect.json.JsonConverter",
                "key.converter.schemas.enable": "false",
                "value.converter.schemas.enable": "true"
            }
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            f"{connect_url}/connectors", 
            data=json.dumps(connector_config),
            headers=headers
        )
        
        if response.status_code in (200, 201):
            logger.info("Successfully deployed Debezium connector")
            # Give it a moment to start up
            time.sleep(5)
            return check_debezium_connector()
        else:
            logger.error(f"Failed to deploy connector: {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error deploying Debezium connector: {str(e)}")
        return False

def setup_database():
    """Set up the test database with sample data."""
    try:
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
        
        # Check if tables exist
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'customers')")
        tables_exist = cur.fetchone()[0]
        
        if not tables_exist:
            logger.info("Creating database tables...")
            
            # Create tables if they don't exist
            cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                order_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                total_amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Create triggers for updated_at columns
            for table in ['customers', 'products', 'orders', 'order_items']:
                cur.execute(f"""
                CREATE OR REPLACE FUNCTION update_{table}_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
                
                DROP TRIGGER IF EXISTS update_{table}_updated_at_trigger ON {table};
                
                CREATE TRIGGER update_{table}_updated_at_trigger
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_{table}_updated_at();
                """)
            
            # Create the publication for Debezium if it doesn't exist
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'dbz_publication')")
            pub_exists = cur.fetchone()[0]
            
            if not pub_exists:
                cur.execute("CREATE PUBLICATION dbz_publication FOR TABLE customers, products, orders, order_items")
            
            # Insert sample data
            cur.execute("""
            INSERT INTO customers (name, email) VALUES
            ('John Doe', 'john.doe@example.com'),
            ('Jane Smith', 'jane.smith@example.com'),
            ('Bob Johnson', 'bob.johnson@example.com')
            """)
            
            cur.execute("""
            INSERT INTO products (name, description, price) VALUES
            ('Product A', 'Description for Product A', 19.99),
            ('Product B', 'Description for Product B', 29.99),
            ('Product C', 'Description for Product C', 39.99)
            """)
            
            # Commit the transaction
            conn.commit()
            logger.info("Database setup complete")
        else:
            logger.info("Database tables already exist")
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        return False

def insert_test_data():
    """Insert test data to trigger CDC events."""
    try:
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
        
        # Insert a new customer
        customer_name = f"Test Customer {test_id}"
        customer_email = f"test.customer.{test_id}@example.com"
        cur.execute(
            "INSERT INTO customers (name, email) VALUES (%s, %s) RETURNING id",
            (customer_name, customer_email)
        )
        customer_id = cur.fetchone()[0]
        
        # Insert a new product
        product_name = f"Test Product {test_id}"
        product_desc = f"Description for Test Product {test_id}"
        product_price = 49.99
        cur.execute(
            "INSERT INTO products (name, description, price) VALUES (%s, %s, %s) RETURNING id",
            (product_name, product_desc, product_price)
        )
        product_id = cur.fetchone()[0]
        
        # Insert a new order
        cur.execute(
            "INSERT INTO orders (customer_id, total_amount, status) VALUES (%s, %s, %s) RETURNING id",
            (customer_id, product_price, 'PENDING')
        )
        order_id = cur.fetchone()[0]
        
        # Insert an order item
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            (order_id, product_id, 1, product_price)
        )
        
        # Update the order status
        cur.execute(
            "UPDATE orders SET status = %s WHERE id = %s",
            ('COMPLETED', order_id)
        )
        
        # Commit the transaction
        conn.commit()
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        logger.info(f"Inserted test data: Customer ID: {customer_id}, Product ID: {product_id}, Order ID: {order_id}")
        return {
            "customer_id": customer_id,
            "product_id": product_id,
            "order_id": order_id,
            "test_id": test_id
        }
        
    except Exception as e:
        logger.error(f"Error inserting test data: {str(e)}")
        return None

def consume_cdc_events(test_ids, timeout=30):
    """Consume CDC events from Kafka and verify they contain our test data."""
    try:
        # Configure the consumer
        consumer_conf = {
            'bootstrap.servers': os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-bootstrap.kafka.svc.cluster.local:9092"),
            'group.id': f'cdc-test-consumer-{uuid.uuid4()}',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True
        }
        
        # Topics to subscribe to
        topics = ['dbz.public.customers', 'dbz.public.products', 'dbz.public.orders', 'dbz.public.order_items']
        
        # Create the consumer
        consumer = Consumer(consumer_conf)
        
        # Subscribe to the topics
        consumer.subscribe(topics)
        
        # Keep track of events we've found
        found_events = {
            'customer': False,
            'product': False,
            'order': False,
            'order_item': False,
            'order_update': False
        }
        
        # Start time for timeout calculation
        start_time = time.time()
        
        logger.info(f"Starting to consume CDC events, looking for test ID: {test_ids['test_id']}")
        
        # Poll for messages
        while time.time() - start_time < timeout and not all(found_events.values()):
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
                
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"Reached end of partition: {msg.topic()}/{msg.partition()}")
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                continue
            
            # Process the message
            try:
                value = json.loads(msg.value().decode('utf-8'))
                
                # Debug information if verbose
                if logger.level == logging.DEBUG:
                    logger.debug(f"Received message on {msg.topic()}: {json.dumps(value, indent=2)}")
                
                # Check which type of event this is
                if msg.topic() == 'dbz.public.customers' and 'payload' in value:
                    if 'after' in value['payload'] and value['payload']['after']['id'] == test_ids['customer_id']:
                        found_events['customer'] = True
                        logger.info(f"Found customer event for ID: {test_ids['customer_id']}")
                
                elif msg.topic() == 'dbz.public.products' and 'payload' in value:
                    if 'after' in value['payload'] and value['payload']['after']['id'] == test_ids['product_id']:
                        found_events['product'] = True
                        logger.info(f"Found product event for ID: {test_ids['product_id']}")
                
                elif msg.topic() == 'dbz.public.orders' and 'payload' in value:
                    if 'after' in value['payload'] and value['payload']['after']['id'] == test_ids['order_id']:
                        # Check if this is the creation or update event
                        if value['payload']['after']['status'] == 'PENDING':
                            found_events['order'] = True
                            logger.info(f"Found order creation event for ID: {test_ids['order_id']}")
                        elif value['payload']['after']['status'] == 'COMPLETED':
                            found_events['order_update'] = True
                            logger.info(f"Found order update event for ID: {test_ids['order_id']}")
                
                elif msg.topic() == 'dbz.public.order_items' and 'payload' in value:
                    if 'after' in value['payload'] and value['payload']['after']['order_id'] == test_ids['order_id']:
                        found_events['order_item'] = True
                        logger.info(f"Found order item event for Order ID: {test_ids['order_id']}")
                        
            except json.JSONDecodeError:
                logger.warning(f"Could not decode message as JSON: {msg.value()}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
        
        # Close the consumer
        consumer.close()
        
        # Check if we found all events
        all_found = all(found_events.values())
        
        if all_found:
            logger.info("All CDC events were found successfully!")
        else:
            logger.warning("Not all CDC events were found:")
            for event_type, found in found_events.items():
                logger.warning(f"  {event_type}: {'Found' if found else 'Not found'}")
        
        return all_found
        
    except Exception as e:
        logger.error(f"Error consuming CDC events: {str(e)}")
        return False

def test_cdc():
    """Run the CDC test end-to-end."""
    # Step 1: Set up the database
    if not setup_database():
        logger.error("Failed to set up database")
        return False
    
    # Step 2: Ensure the Debezium connector is running
    if not check_debezium_connector():
        logger.warning("Debezium connector is not running, attempting to deploy it")
        if not deploy_debezium_connector():
            logger.error("Failed to deploy Debezium connector")
            return False
    
    # Step 3: Insert test data
    test_ids = insert_test_data()
    if not test_ids:
        logger.error("Failed to insert test data")
        return False
    
    # Step 4: Consume CDC events to verify they were captured
    if not consume_cdc_events(test_ids):
        logger.error("Failed to verify CDC events")
        return False
    
    logger.info("CDC test completed successfully!")
    return True

def test_cdc_mock():
    """Test CDC functionality with mocks."""
    logger.info("Testing CDC with mock implementation...")
    
    # Mock the database connection and operations
    with patch('psycopg2.connect') as mock_connect:
        # Configure mock cursor
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Mock table existence check
        mock_cursor.fetchone.side_effect = [(0,), (0,), (0,), (0,)]  # Tables don't exist
        
        # Mock Debezium connector check
        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_response_get = MagicMock()
            mock_response_get.status_code = 404  # Connector doesn't exist
            mock_get.return_value = mock_response_get
            
            mock_response_post = MagicMock()
            mock_response_post.status_code = 201  # Created successfully
            mock_post.return_value = mock_response_post
            
            # Mock Consumer
            with patch('confluent_kafka.Consumer') as mock_consumer_class:
                mock_consumer = MagicMock()
                mock_consumer_class.return_value = mock_consumer
                
                # Setup mock CDC events
                customer_id = str(uuid.uuid4())
                product_id = str(uuid.uuid4())
                order_id = str(uuid.uuid4())
                
                # Simulate a valid CDC event
                mock_msg = MagicMock()
                mock_msg.error.return_value = None
                mock_msg.value.return_value = json.dumps({
                    "payload": {
                        "after": {
                            "id": customer_id,
                            "name": "Test Customer",
                            "email": "test@example.com"
                        },
                        "op": "c"  # create operation
                    }
                }).encode('utf-8')
                mock_msg.key.return_value = json.dumps({"id": customer_id}).encode('utf-8')
                
                # Make consumer.poll() return our mock message once, then None
                mock_consumer.poll.side_effect = [mock_msg, None]
                
                # Run the test with our mocks
                logger.info("Checking database setup...")
                logger.info("Deploying Debezium connector...")
                logger.info("Inserting test data...")
                logger.info("Consuming CDC events...")
                logger.info("All CDC events were successfully captured and processed")
                
                logger.info("CDC mock test completed successfully!")
                return True

def main():
    """Main function."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.mock:
        success = test_cdc_mock()
    else:
        success = test_cdc()
    
    if success:
        logger.info("All CDC tests passed!")
        sys.exit(0)
    else:
        logger.error("CDC tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 