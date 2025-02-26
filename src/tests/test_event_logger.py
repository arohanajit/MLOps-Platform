#!/usr/bin/env python3
"""
Event Logger Client Test Script

This script tests the KafkaEventLogger client with both real Kafka
and a mock implementation for offline testing.

Usage:
    python test_event_logger.py [--mock] [--verbose]

Options:
    --mock      Use mock Kafka implementation instead of real Kafka
    --verbose   Enable verbose output
"""

import os
import sys
import time
import uuid
import json
import argparse
import logging
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EventLoggerTest")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Event Logger Client Test Script")
    parser.add_argument(
        "--mock", 
        action="store_true",
        help="Use mock Kafka implementation instead of real Kafka"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()

class KafkaConsumerMock:
    """Mock Kafka consumer for testing."""
    
    def __init__(self, topics):
        self.topics = topics
        self.messages = []
        self.position = 0
    
    def add_message(self, topic, key, value):
        """Add a message to the mock consumer."""
        self.messages.append({
            'topic': topic,
            'key': key,
            'value': value,
            'timestamp': int(time.time() * 1000)
        })
    
    def poll(self, timeout=None):
        """Poll for a message."""
        if self.position < len(self.messages):
            message = self.messages[self.position]
            self.position += 1
            return message
        return None
    
    def close(self):
        """Close the consumer."""
        pass

class KafkaProducerMock:
    """Mock Kafka producer for testing."""
    
    def __init__(self, config):
        self.config = config
        self.messages = []
        self.consumer = None
    
    def produce(self, topic, key, value, on_delivery=None):
        """Produce a message to the mock Kafka."""
        self.messages.append({
            'topic': topic,
            'key': key,
            'value': value
        })
        
        # If there's a consumer, add the message to it
        if self.consumer:
            self.consumer.add_message(topic, key, value)
        
        # Call the delivery callback if provided
        if on_delivery:
            on_delivery(None, {'topic': topic, 'partition': 0, 'offset': len(self.messages) - 1})
    
    def flush(self, timeout=None):
        """Flush the producer."""
        pass
    
    def set_consumer(self, consumer):
        """Set a consumer to receive messages from this producer."""
        self.consumer = consumer

def get_test_event():
    """Get a test event."""
    return {
        "user_id": f"user-{uuid.uuid4()}",
        "login_method": "password",
        "success": True,
        "timestamp": time.time()
    }

def test_event_logger_mock():
    """Test the event logger with mock Kafka."""
    logger.info("Testing event logger with mock Kafka...")
    
    # Create mocks
    producer_mock = KafkaProducerMock({})
    consumer_mock = KafkaConsumerMock(['customer-events', 'purchase-events'])
    producer_mock.set_consumer(consumer_mock)
    
    # Patch the required modules
    with patch('src.clients.python.event_logger.Producer', return_value=producer_mock), \
         patch('src.clients.python.event_logger.SchemaRegistryClient'), \
         patch('src.clients.python.event_logger.AvroSerializer'), \
         patch('src.clients.python.event_logger.StringSerializer'):
        
        # Import the event logger here so the patches take effect
        from src.clients.python.event_logger import KafkaEventLogger
        
        # Create the event logger
        event_logger = KafkaEventLogger(
            kafka_bootstrap_servers="mock:9092",
            schema_registry_url="http://mock:8081",
            app_name="test-app",
            default_topic="customer-events",
            use_avro=False  # Use JSON instead of Avro for simplicity
        )
        
        # Log a test event
        event_payload = get_test_event()
        event_id = event_logger.log_event(
            event_type="USER_LOGIN",
            payload=event_payload
        )
        
        # Log another event with a custom topic
        purchase_payload = {
            "user_id": event_payload["user_id"],
            "order_id": f"order-{uuid.uuid4()}",
            "amount": 99.99,
            "currency": "USD",
            "items": "3"
        }
        purchase_id = event_logger.log_event(
            event_type="PURCHASE_COMPLETED",
            payload=purchase_payload,
            topic="purchase-events"
        )
        
        # Check that the messages were produced
        assert len(producer_mock.messages) == 2, "Expected 2 messages, got {}".format(len(producer_mock.messages))
        
        # Check the first message
        assert producer_mock.messages[0]['topic'] == "customer-events"
        assert producer_mock.messages[0]['key'] == event_id
        
        # Check the second message
        assert producer_mock.messages[1]['topic'] == "purchase-events"
        assert producer_mock.messages[1]['key'] == purchase_id
        
        logger.info("Event logger mock test passed!")
        return True

def test_event_logger_real(verbose: bool = False):
    """Test the event logger with real Kafka."""
    logger.info("Testing event logger with real Kafka...")
    
    # Import client
    from src.clients.python.event_logger import KafkaEventLogger
    
    # Set up Kafka connection parameters
    kafka_bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-bootstrap.kafka.svc.cluster.local:9092")
    schema_registry_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry.kafka.svc.cluster.local:8081")
    
    # Try to connect to Kafka with a timeout
    try:
        # Create the event logger
        event_logger = KafkaEventLogger(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            schema_registry_url=schema_registry_url,
            app_name="test-app",
            default_topic="customer-events",
            use_avro=True  # Use Avro with real Kafka
        )
        
        # Log a test event
        event_payload = get_test_event()
        event_id = event_logger.log_event(
            event_type="USER_LOGIN",
            payload=event_payload
        )
        
        # Log another event with a custom topic
        purchase_payload = {
            "user_id": event_payload["user_id"],
            "order_id": f"order-{uuid.uuid4()}",
            "amount": 99.99,
            "currency": "USD",
            "items": "3"
        }
        purchase_id = event_logger.log_event(
            event_type="PURCHASE_COMPLETED",
            payload=purchase_payload,
            topic="purchase-events"
        )
        
        logger.info(f"Successfully sent events with IDs: {event_id}, {purchase_id}")
        logger.info("Event logger real Kafka test passed!")
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to Kafka: {str(e)}")
        return False

def main():
    """Main function."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.mock:
        success = test_event_logger_mock()
    else:
        success = test_event_logger_real(args.verbose)
    
    if success:
        logger.info("All event logger tests passed!")
        sys.exit(0)
    else:
        logger.error("Event logger tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 