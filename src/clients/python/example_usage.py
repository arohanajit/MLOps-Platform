import time
from event_logger import KafkaEventLogger

def main():
    """
    Example usage of the KafkaEventLogger.
    """
    # Initialize the event logger
    logger = KafkaEventLogger(
        kafka_bootstrap_servers="kafka-bootstrap.kafka.svc.cluster.local:9092",
        schema_registry_url="http://schema-registry.kafka.svc.cluster.local:8081",
        app_name="example-app",
        default_topic="customer-events"
    )
    
    # Log a simple event
    logger.log_event(
        event_type="USER_LOGIN",
        payload={
            "user_id": "user-123",
            "login_method": "password",
            "success": True,
            "timestamp": time.time()
        }
    )
    
    # Log an event with a custom topic
    logger.log_event(
        event_type="PURCHASE_COMPLETED",
        payload={
            "user_id": "user-123",
            "order_id": "order-456",
            "amount": 99.99,
            "currency": "USD",
            "items": "3"  # Note: Complex types need to be serialized for Avro
        },
        topic="purchase-events"
    )
    
    print("Events published successfully!")

if __name__ == "__main__":
    main() 