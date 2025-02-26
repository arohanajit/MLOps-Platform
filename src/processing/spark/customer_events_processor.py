import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, from_json, expr, to_timestamp, lit, window, count, sum, avg, 
    when, explode, array, struct, udf, get_json_object, schema_of_json
)
from pyspark.sql.types import (
    StructType, StructField, StringType, TimestampType, 
    DoubleType, IntegerType, BooleanType, MapType, ArrayType
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CustomerEventsProcessor")

# Environment variables with defaults
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-bootstrap.kafka.svc.cluster.local:9092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry.kafka.svc.cluster.local:8081")
CHECKPOINT_LOCATION = os.environ.get("CHECKPOINT_LOCATION", "/tmp/spark-checkpoints")
POSTGRES_JDBC_URL = os.environ.get("POSTGRES_JDBC_URL", "jdbc:postgresql://postgres-k8s.storage.svc.cluster.local:5432/mlops")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis-k8s.storage.svc.cluster.local")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# Define schemas for different event types
CUSTOMER_EVENT_SCHEMA = StructType([
    StructField("event_id", StringType(), False),
    StructField("event_type", StringType(), False),
    StructField("timestamp", StringType(), False),
    StructField("app_name", StringType(), True),
    StructField("hostname", StringType(), True),
    StructField("payload", MapType(StringType(), StringType()), True)
])

# Helper functions for data quality checks
def validate_event(event: Dict[str, Any]) -> bool:
    """
    Validates if an event has the required fields and correct format.
    """
    required_fields = ["event_id", "event_type", "timestamp"]
    
    # Check required fields exist
    for field in required_fields:
        if field not in event or not event[field]:
            logger.warning(f"Event missing required field: {field}")
            return False
    
    # Validate timestamp format
    try:
        datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
    except (ValueError, TypeError):
        logger.warning(f"Invalid timestamp format: {event.get('timestamp')}")
        return False
    
    return True

# UDF for data validation
validate_event_udf = udf(validate_event, BooleanType())

class CustomerEventsProcessor:
    """
    Spark Streaming processor for customer events from Kafka.
    """
    
    def __init__(self, app_name: str = "customer-events-processor"):
        """Initialize the Spark session and streaming context."""
        
        self.app_name = app_name
        self.spark = (
            SparkSession.builder
            .appName(app_name)
            .config("spark.sql.streaming.schemaInference", "true")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.streaming.stopGracefullyOnShutdown", "true")
            .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true")
            .getOrCreate()
        )
        
        # Set log level for Spark
        self.spark.sparkContext.setLogLevel("WARN")
        
        logger.info(f"Initialized Spark session for {app_name}")
    
    def read_from_kafka(
        self, 
        topics: List[str], 
        starting_offsets: str = "latest"
    ) -> DataFrame:
        """
        Read from Kafka topics.
        
        Args:
            topics: List of Kafka topics to subscribe to
            starting_offsets: Where to start reading from ("latest" or "earliest")
            
        Returns:
            DataFrame with raw Kafka data
        """
        topics_str = ",".join(topics)
        logger.info(f"Reading from Kafka topics: {topics_str}")
        
        return (
            self.spark
            .readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
            .option("subscribe", topics_str)
            .option("startingOffsets", starting_offsets)
            .option("failOnDataLoss", "false")
            .load()
        )
    
    def process_customer_events(self, df: DataFrame) -> DataFrame:
        """
        Process customer events.
        
        Args:
            df: Input DataFrame with raw Kafka messages
            
        Returns:
            Processed DataFrame with parsed events
        """
        logger.info("Processing customer events")
        
        # Parse the Kafka message value as JSON
        parsed_df = (
            df
            .selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)", "topic", "timestamp as kafka_timestamp")
            .withColumn("event", from_json(col("value"), CUSTOMER_EVENT_SCHEMA))
            .select(
                col("key").alias("kafka_key"),
                col("kafka_timestamp"),
                col("topic"),
                col("event.event_id"),
                col("event.event_type"),
                to_timestamp(col("event.timestamp")).alias("event_timestamp"),
                col("event.app_name"),
                col("event.hostname"),
                col("event.payload")
            )
        )
        
        # Apply data quality validation
        validated_df = (
            parsed_df
            .withColumn("is_valid", 
                       (col("event_id").isNotNull()) & 
                       (col("event_type").isNotNull()) & 
                       (col("event_timestamp").isNotNull()))
        )
        
        # Split into valid and invalid streams
        valid_events = validated_df.filter(col("is_valid") == True)
        invalid_events = validated_df.filter(col("is_valid") == False)
        
        # Log count of invalid events
        invalid_events_count = invalid_events.count()
        if invalid_events_count > 0:
            logger.warning(f"Found {invalid_events_count} invalid events")
            
            # Write invalid events to a dead-letter queue topic
            invalid_query = (
                invalid_events
                .selectExpr("event_id as key", "to_json(struct(*)) as value")
                .writeStream
                .format("kafka")
                .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
                .option("topic", "dead-letter-queue")
                .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/invalid-events")
                .start()
            )
        
        return valid_events
    
    def analyze_events(self, df: DataFrame) -> Dict[str, DataFrame]:
        """
        Analyze events to create insightful aggregations.
        
        Args:
            df: DataFrame with parsed events
            
        Returns:
            Dictionary of DataFrames with different analyses
        """
        logger.info("Analyzing customer events")
        
        # Event counts by type
        events_by_type = (
            df
            .groupBy("event_type")
            .count()
            .withColumnRenamed("count", "event_count")
        )
        
        # Event counts by app
        events_by_app = (
            df
            .groupBy("app_name")
            .count()
            .withColumnRenamed("count", "event_count")
        )
        
        # Events over time (windowed analysis)
        events_over_time = (
            df
            .withWatermark("event_timestamp", "5 minutes")
            .groupBy(
                window(col("event_timestamp"), "5 minutes"),
                col("event_type")
            )
            .count()
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("event_type"),
                col("count").alias("event_count")
            )
        )
        
        return {
            "events_by_type": events_by_type,
            "events_by_app": events_by_app,
            "events_over_time": events_over_time
        }
    
    def write_to_postgres(self, df: DataFrame, table: str, mode: str = "append") -> None:
        """
        Write results to PostgreSQL.
        
        Args:
            df: DataFrame to write
            table: Target table name
            mode: Write mode (append, overwrite, etc.)
        """
        logger.info(f"Writing to PostgreSQL table: {table}")
        
        # Write to PostgreSQL
        df.writeStream \
            .foreachBatch(lambda batch_df, _: self._write_batch_to_postgres(batch_df, table, mode)) \
            .outputMode("update") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/{table}") \
            .start()
    
    def _write_batch_to_postgres(self, batch_df: DataFrame, table: str, mode: str) -> None:
        """Write a batch to PostgreSQL."""
        if batch_df.isEmpty():
            logger.info(f"No data to write to {table}")
            return
        
        properties = {
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "driver": "org.postgresql.Driver"
        }
        
        batch_df.write \
            .jdbc(
                url=POSTGRES_JDBC_URL,
                table=table,
                mode=mode,
                properties=properties
            )
        
        logger.info(f"Successfully wrote batch to {table}")
    
    def write_to_redis(self, df: DataFrame, key_column: str, value_columns: List[str]) -> None:
        """
        Write results to Redis for fast access.
        
        Args:
            df: DataFrame to write
            key_column: Column to use as Redis key
            value_columns: Columns to include in Redis value
        """
        logger.info(f"Writing to Redis with key column: {key_column}")
        
        # Process each batch and write to Redis
        query = df.writeStream \
            .foreachBatch(lambda batch_df, _: self._write_batch_to_redis(batch_df, key_column, value_columns)) \
            .outputMode("update") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/redis-{key_column}") \
            .start()
    
    def _write_batch_to_redis(self, batch_df: DataFrame, key_column: str, value_columns: List[str]) -> None:
        """Write a batch to Redis."""
        if batch_df.isEmpty():
            logger.info("No data to write to Redis")
            return
        
        import redis
        from redis.commands.json.path import Path
        
        # Connect to Redis
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            password=REDIS_PASSWORD,
            decode_responses=True,
            ssl=False
        )
        
        try:
            # Convert the batch to a list of records
            records = batch_df.select([key_column] + value_columns).collect()
            
            # Write each record to Redis
            for record in records:
                key = record[key_column]
                value = {col: record[col] for col in value_columns}
                
                # Store JSON in Redis
                redis_client.json().set(f"event:{key}", Path.root_path(), value)
                
                # Set expiry (optional, e.g., 1 day = 86400 seconds)
                redis_client.expire(f"event:{key}", 86400)
            
            logger.info(f"Successfully wrote {len(records)} records to Redis")
        except Exception as e:
            logger.error(f"Error writing to Redis: {str(e)}")
        finally:
            redis_client.close()
    
    def run(self) -> None:
        """Run the streaming job."""
        logger.info("Starting streaming job")
        
        try:
            # Read from Kafka
            raw_events = self.read_from_kafka(["customer-events", "purchase-events"], "earliest")
            
            # Process events
            processed_events = self.process_customer_events(raw_events)
            
            # Analyze events
            analyses = self.analyze_events(processed_events)
            
            # Write to PostgreSQL
            # 1. Raw events
            self.write_to_postgres(
                processed_events.select(
                    "event_id", "event_type", "event_timestamp", 
                    "app_name", "hostname", "payload"
                ),
                "customer_events_raw"
            )
            
            # 2. Event counts by type
            self.write_to_postgres(analyses["events_by_type"], "customer_events_by_type")
            
            # 3. Event counts by app
            self.write_to_postgres(analyses["events_by_app"], "customer_events_by_app")
            
            # 4. Events over time
            self.write_to_postgres(analyses["events_over_time"], "customer_events_over_time")
            
            # Write to Redis for real-time access
            self.write_to_redis(
                processed_events,
                "event_id",
                ["event_type", "event_timestamp", "app_name", "payload"]
            )
            
            # Start the streaming queries and await termination
            self.spark.streams.awaitAnyTermination()
            
        except Exception as e:
            logger.error(f"Error in streaming job: {str(e)}")
            raise

if __name__ == "__main__":
    processor = CustomerEventsProcessor()
    processor.run() 