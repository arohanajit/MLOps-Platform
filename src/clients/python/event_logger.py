import json
import logging
import os
import socket
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

class KafkaEventLogger:
    """
    A client for sending events to Kafka with schema validation.
    
    This class provides a simple interface for publishing events to Kafka topics,
    with support for Avro schema validation through Schema Registry.
    """
    
    def __init__(
        self,
        kafka_bootstrap_servers: str,
        schema_registry_url: str,
        default_topic: str = "customer-events",
        app_name: str = "unknown-app",
        use_avro: bool = True
    ):
        """
        Initialize the Kafka event logger.
        
        Args:
            kafka_bootstrap_servers: Comma-separated list of Kafka bootstrap servers
            schema_registry_url: URL of the Schema Registry
            default_topic: Default topic to publish events to
            app_name: Name of the application producing events
            use_avro: Whether to use Avro serialization (requires schema registry)
        """
        self.default_topic = default_topic
        self.app_name = app_name
        self.hostname = socket.gethostname()
        self.use_avro = use_avro
        
        # Configure logging
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
        
        self.logger = structlog.get_logger()
        
        # Configure Kafka Producer
        producer_conf = {
            'bootstrap.servers': kafka_bootstrap_servers,
            'client.id': f'{app_name}-{socket.gethostname()}',
        }
        
        if use_avro:
            # Configure Schema Registry client
            schema_registry_conf = {'url': schema_registry_url}
            self.schema_registry_client = SchemaRegistryClient(schema_registry_conf)
            
            # Default Avro schema for events
            self.default_schema = {
                "type": "record",
                "name": "CustomerEvent",
                "fields": [
                    {"name": "event_id", "type": "string"},
                    {"name": "event_type", "type": "string"},
                    {"name": "timestamp", "type": "string"},
                    {"name": "app_name", "type": "string"},
                    {"name": "hostname", "type": "string"},
                    {"name": "payload", "type": ["null", {"type": "map", "values": ["null", "string", "int", "float", "boolean"]}]}
                ]
            }
            
            # Create serializers
            self.string_serializer = StringSerializer('utf_8')
            self.avro_serializer = AvroSerializer(
                self.schema_registry_client,
                json.dumps(self.default_schema)
            )
            
            # Keep serializers separate, don't add to producer_conf
            
        self.producer = Producer(producer_conf)
        self.logger.info("Kafka event logger initialized", 
                        bootstrap_servers=kafka_bootstrap_servers, 
                        schema_registry_url=schema_registry_url)
    
    def log_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        topic: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> str:
        """
        Log an event to Kafka.
        
        Args:
            event_type: Type of the event
            payload: Event payload as a dictionary
            topic: Kafka topic to publish to (uses default if None)
            event_id: Unique ID for the event (generated if None)
            
        Returns:
            The event ID
        """
        if event_id is None:
            event_id = str(uuid.uuid4())
            
        if topic is None:
            topic = self.default_topic
            
        if payload is None:
            payload = {}
            
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "app_name": self.app_name,
            "hostname": self.hostname,
            "payload": payload
        }
        
        if self.use_avro:
            key = event_id
            self.producer.produce(
                topic=topic,
                key=self.string_serializer(key),
                value=event,
                on_delivery=self._delivery_report
            )
        else:
            # If not using Avro, serialize to JSON
            event_json = json.dumps(event)
            self.producer.produce(
                topic=topic,
                key=event_id,
                value=event_json,
                on_delivery=self._delivery_report
            )
        
        # Make sure the message is sent
        self.producer.flush(timeout=10)
        
        self.logger.info("Event published to Kafka", 
                        event_id=event_id, 
                        event_type=event_type, 
                        topic=topic)
        return event_id
        
    def _delivery_report(self, err, msg):
        """
        Callback for message delivery reports.
        """
        if err is not None:
            self.logger.error("Failed to deliver message", 
                             error=str(err))
        else:
            # Handle both real Kafka messages and mock messages (dictionaries)
            if isinstance(msg, dict):
                topic = msg.get('topic', 'unknown')
                partition = msg.get('partition', -1)
                offset = msg.get('offset', -1)
            else:
                topic = msg.topic()
                partition = msg.partition()
                offset = msg.offset()
            
            self.logger.debug("Message delivered", 
                             topic=topic, 
                             partition=partition, 
                             offset=offset) 