FROM apache/spark:3.4.1-python3

USER root

# Install necessary dependencies
RUN apt-get update && \
    apt-get install -y curl wget unzip python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/spark/work-dir

# Copy requirements file
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy Spark jobs
COPY customer_events_processor.py .
COPY utils/ ./utils/
COPY validation/ ./validation/

# Download PostgreSQL JDBC driver
RUN wget https://jdbc.postgresql.org/download/postgresql-42.6.0.jar -O /opt/spark/jars/postgresql-42.6.0.jar

# Download additional JARs for Kafka, Delta, etc.
RUN mkdir -p /opt/spark/jars && \
    # Kafka
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.4.1/spark-sql-kafka-0-10_2.12-3.4.1.jar -O /opt/spark/jars/org.apache.spark_spark-sql-kafka-0-10_2.12-3.4.1.jar && \
    wget https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.3.2/kafka-clients-3.3.2.jar -O /opt/spark/jars/org.apache.kafka_kafka-clients-3.3.2.jar && \
    # Delta
    wget https://repo1.maven.org/maven2/io/delta/delta-core_2.12/2.4.0/delta-core_2.12-2.4.0.jar -O /opt/spark/jars/io.delta_delta-core_2.12-2.4.0.jar && \
    # Avro
    wget https://repo1.maven.org/maven2/org/apache/avro/avro/1.11.1/avro-1.11.1.jar -O /opt/spark/jars/org.apache.avro_avro-1.11.1.jar

# Prometheus JMX exporter
RUN mkdir -p /prometheus && \
    wget https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.17.0/jmx_prometheus_javaagent-0.17.0.jar -O /prometheus/jmx_prometheus_javaagent-0.17.0.jar

# Create directory for Great Expectations
RUN mkdir -p /opt/great-expectations

# Create required directories
RUN mkdir -p /opt/spark/logs && \
    mkdir -p /tmp/spark-checkpoints && \
    chmod -R 777 /tmp/spark-checkpoints && \
    chmod -R 777 /opt/great-expectations && \
    chmod -R 777 /opt/spark/logs

# Set environment variables for resource optimization
ENV SPARK_WORKER_MEMORY=1g \
    SPARK_DRIVER_MEMORY=1g \
    SPARK_EXECUTOR_MEMORY=1g \
    SPARK_DRIVER_CORES=1 \
    SPARK_EXECUTOR_CORES=1 \
    SPARK_WORKER_CORES=1 \
    SPARK_MEMORY_FRACTION=0.7 \
    SPARK_MEMORY_STORAGE_FRACTION=0.3 \
    SPARK_RDD_COMPRESS=true \
    SPARK_EXECUTOR_INSTANCES=1 \
    SPARK_SQL_SHUFFLE_PARTITIONS=10 \
    SPARK_DEFAULT_PARALLELISM=10

USER 185

# The entrypoint is inherited from the base image 