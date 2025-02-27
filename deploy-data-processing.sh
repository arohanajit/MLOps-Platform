#!/bin/bash

set -e

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   MLOps Platform - Data Processing Layer   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed.${NC}"
    exit 1
fi

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm is not installed.${NC}"
    exit 1
fi

# Create namespaces if they don't exist
echo -e "${YELLOW}Creating namespaces...${NC}"
kubectl apply -f kubernetes/namespaces.yaml
echo ""

# Deploy Spark Operator with optimized resource settings
echo -e "${YELLOW}Deploying Spark Operator...${NC}"
kubectl apply -f kubernetes/spark/spark-operator.yaml
echo -e "${GREEN}Spark Operator deployed.${NC}"
echo ""

# Wait for Spark Operator to be ready
echo -e "${YELLOW}Waiting for Spark Operator to be ready...${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/spark-operator -n spark
echo -e "${GREEN}Spark Operator is ready.${NC}"
echo ""

# Create Spark configuration for resource constraints
echo -e "${YELLOW}Creating custom resource profile for Spark...${NC}"
cat <<EOF > kubernetes/spark/resource-profile.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: spark-resource-profile
  namespace: spark
data:
  spark.driver.memory: "1g"
  spark.executor.memory: "1g"
  spark.driver.cores: "1"
  spark.executor.cores: "1"
  spark.executor.instances: "1"
  spark.memory.fraction: "0.7"
  spark.memory.storageFraction: "0.3"
  spark.streaming.backpressure.enabled: "true"
  spark.streaming.kafka.consumer.cache.enabled: "false"
  spark.sql.shuffle.partitions: "10"
EOF
kubectl apply -f kubernetes/spark/resource-profile.yaml
echo -e "${GREEN}Resource profile created.${NC}"
echo ""

# Deploy Airflow using Helm with resource constraints
echo -e "${YELLOW}Deploying Airflow...${NC}"
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Optimize Airflow values for AWS Free Tier
cat <<EOF > kubernetes/airflow/free-tier-values.yaml
# Override values for AWS Free Tier
webserver:
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi

scheduler:
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi

workers:
  replicas: 1
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi

# Use existing PostgreSQL
data:
  metadataConnection:
    user: postgres
    pass: postgrespass
    host: postgres.storage.svc.cluster.local
    port: 5432
    db: airflow

# Minimal Redis
redis:
  resources:
    limits:
      cpu: 200m
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 128Mi

# Add Great Expectations package
extraPipPackages:
  - "apache-airflow-providers-postgres==5.6.0"
  - "apache-airflow-providers-amazon==8.1.0"
  - "pyspark==3.4.1"
  - "pandas==2.0.3"
  - "great-expectations==0.17.16"

# Disable features not needed
env:
  - name: AIRFLOW__CORE__LOAD_EXAMPLES
    value: "false"
  - name: AIRFLOW__SCHEDULER__WORKER_CONCURRENCY
    value: "2"
  - name: AIRFLOW__WEBSERVER__WORKERS
    value: "1"
  - name: AIRFLOW__WEBSERVER__ENABLE_PROXY_FIX
    value: "true"
  - name: AIRFLOW__CORE__DAG_FILE_PROCESSOR_TIMEOUT
    value: "60"
EOF

helm upgrade --install airflow apache-airflow/airflow \
  --namespace airflow \
  --values kubernetes/airflow/values.yaml \
  --values kubernetes/airflow/free-tier-values.yaml \
  --timeout 10m0s

echo -e "${GREEN}Airflow deployed with resource constraints.${NC}"
echo ""

# Create directory for DAGs if it doesn't exist
echo -e "${YELLOW}Setting up Airflow DAGs directory...${NC}"
mkdir -p src/airflow/dags
echo -e "${GREEN}DAGs directory created.${NC}"
echo ""

# Create a sample data processing DAG
echo -e "${YELLOW}Creating sample data processing DAG...${NC}"
cat <<EOF > src/airflow/dags/data_processing_pipeline.py
"""
Data Processing Pipeline DAG

This DAG orchestrates the following steps:
1. Validates raw data using Great Expectations
2. Runs a Spark job to process customer events
3. Materializes features to the feature store
4. Validates processed data
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.providers.cncf.kubernetes.sensors.spark_kubernetes import SparkKubernetesSensor
from airflow.operators.python import PythonOperator

# Define default arguments
default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
dag = DAG(
    'data_processing_pipeline',
    default_args=default_args,
    description='Data processing pipeline with validation',
    schedule_interval=timedelta(days=1),
    catchup=False,
    max_active_runs=1,
)

# Define tasks
def validate_raw_data(**kwargs):
    """Validates raw data using Great Expectations"""
    # Import here to avoid loading libraries in the DAG definition
    import great_expectations as ge
    from great_expectations.data_context import DataContext
    
    # Initialize Great Expectations context
    context = DataContext('/opt/airflow/great_expectations')
    
    # Run validation
    results = context.run_checkpoint(
        checkpoint_name="raw_data_checkpoint",
        batch_request=None,
        run_name=f"airflow_triggered_{kwargs['ds']}"
    )
    
    # Check if validation passed
    if not results["success"]:
        raise ValueError("Data validation failed")
    
    return True

# Task 1: Validate raw data
validate_raw_data_task = PythonOperator(
    task_id='validate_raw_data',
    python_callable=validate_raw_data,
    provide_context=True,
    dag=dag,
)

# Task 2: Submit Spark job for customer events processing
customer_events_job = SparkKubernetesOperator(
    task_id='process_customer_events',
    application_file='customer-events-processor.yaml',
    namespace='spark',
    kubernetes_conn_id='kubernetes_default',
    do_xcom_push=True,
    dag=dag,
)

# Task 3: Monitor Spark job
monitor_customer_events_job = SparkKubernetesSensor(
    task_id='monitor_customer_events_job',
    application_name="{{ task_instance.xcom_pull(task_ids='process_customer_events')['metadata']['name'] }}",
    namespace='spark',
    kubernetes_conn_id='kubernetes_default',
    dag=dag,
)

# Define the workflow
validate_raw_data_task >> customer_events_job >> monitor_customer_events_job
EOF

echo -e "${GREEN}Sample DAG created.${NC}"
echo ""

# Create Great Expectations configuration
echo -e "${YELLOW}Setting up Great Expectations...${NC}"
mkdir -p src/great_expectations/expectations
mkdir -p src/great_expectations/checkpoints

# Create a Great Expectations configuration file
cat <<EOF > src/great_expectations/great_expectations.yml
# Basic Great Expectations configuration
config_version: 3.0

# Datasources
datasources:
  kafka_source:
    class_name: PandasDatasource
    module_name: great_expectations.datasource
    data_asset_type:
      class_name: PandasDataset
      module_name: great_expectations.dataset
  
  postgres_source:
    class_name: SqlAlchemyDatasource
    module_name: great_expectations.datasource
    credentials:
      drivername: postgresql
      host: postgres.storage.svc.cluster.local
      port: 5432
      username: postgres
      password: postgrespass
      database: mlops

# Store for expectations
stores:
  expectations_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: expectations/

  validations_store:
    class_name: ValidationsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: validations/

  checkpoint_store:
    class_name: CheckpointStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: checkpoints/

# Evaluation parameters for validation
evaluation_parameter_store:
  class_name: EvaluationParameterStore

# Data docs for visualization
data_docs_sites:
  local_site:
    class_name: SiteBuilder
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: data_docs/

# Validation operators
validation_operators:
  action_list_operator:
    class_name: ActionListValidationOperator
    action_list:
      - name: store_validation_result
        action:
          class_name: StoreValidationResultAction
      - name: store_evaluation_params
        action:
          class_name: StoreEvaluationParametersAction
      - name: update_data_docs
        action:
          class_name: UpdateDataDocsAction
EOF

# Create a basic expectation suite for customer events
cat <<EOF > src/great_expectations/expectations/customer_events_suite.json
{
  "data_asset_type": null,
  "expectation_suite_name": "customer_events_suite",
  "expectations": [
    {
      "expectation_type": "expect_table_columns_to_match_ordered_list",
      "kwargs": {
        "column_list": [
          "event_id",
          "customer_id",
          "event_type",
          "event_timestamp",
          "event_data"
        ]
      },
      "meta": {}
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {
        "column": "event_id"
      },
      "meta": {}
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {
        "column": "customer_id"
      },
      "meta": {}
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {
        "column": "event_type"
      },
      "meta": {}
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {
        "column": "event_timestamp"
      },
      "meta": {}
    }
  ],
  "meta": {
    "great_expectations_version": "0.17.16"
  }
}
EOF

# Create a checkpoint for validation
cat <<EOF > src/great_expectations/checkpoints/raw_data_checkpoint.yml
name: raw_data_checkpoint
config_version: 1.0
template_name:
module_name: great_expectations.checkpoint
class_name: Checkpoint
run_name_template: "%Y%m%d-%H%M%S-raw-data-validation"
expectation_suite_name: customer_events_suite
batch_request:
  datasource_name: kafka_source
  data_connector_name: default_inferred_data_connector_name
  data_asset_name: customer_events
  data_connector_query:
    index: -1
action_list:
  - name: store_validation_result
    action:
      class_name: StoreValidationResultAction
  - name: store_evaluation_params
    action:
      class_name: StoreEvaluationParametersAction
  - name: update_data_docs
    action:
      class_name: UpdateDataDocsAction
evaluation_parameters: {}
runtime_configuration: {}
validations: []
EOF

echo -e "${GREEN}Great Expectations configuration created.${NC}"
echo ""

# Create directory for Spark validation jobs
echo -e "${YELLOW}Creating Spark data validation jobs...${NC}"
mkdir -p src/processing/spark/validation

# Create Spark data validation job
cat <<EOF > src/processing/spark/validation/data_validator.py
#!/usr/bin/env python3
"""
Spark job for data validation using Great Expectations

This job validates data stored in various data sources using Great Expectations.
It's optimized for AWS Free Tier with minimal resource usage.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
import great_expectations as ge
from great_expectations.dataset import SparkDFDataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataValidator")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Data Validation Spark Job")
    parser.add_argument(
        "--source", 
        choices=["kafka", "postgres", "s3"],
        required=True,
        help="Source to validate data from"
    )
    parser.add_argument(
        "--topic", 
        help="Kafka topic to validate (required for kafka source)"
    )
    parser.add_argument(
        "--table", 
        help="Database table to validate (required for postgres source)"
    )
    parser.add_argument(
        "--s3-path", 
        help="S3 path to validate (required for s3 source)"
    )
    parser.add_argument(
        "--expectation-suite",
        required=True, 
        help="Name of the expectation suite to use for validation"
    )
    parser.add_argument(
        "--output-path",
        required=True, 
        help="Path to write validation results"
    )
    return parser.parse_args()

def create_spark_session() -> SparkSession:
    """Create a Spark session optimized for AWS Free Tier."""
    return (
        SparkSession.builder
        .appName("Data Validator")
        .config("spark.executor.memory", "1g")
        .config("spark.driver.memory", "1g")
        .config("spark.executor.cores", "1")
        .config("spark.driver.cores", "1")
        .config("spark.default.parallelism", "2")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.memory.fraction", "0.7")
        .config("spark.memory.storageFraction", "0.3")
        .config("spark.streaming.backpressure.enabled", "true")
        .getOrCreate()
    )

def read_data_from_source(spark: SparkSession, args) -> Optional[SparkDFDataset]:
    """Read data from the specified source."""
    try:
        if args.source == "kafka":
            if not args.topic:
                logger.error("Topic is required for Kafka source")
                return None
                
            # Read from Kafka
            df = (
                spark
                .read
                .format("kafka")
                .option("kafka.bootstrap.servers", os.environ.get("KAFKA_BOOTSTRAP_SERVERS"))
                .option("subscribe", args.topic)
                .option("startingOffsets", "earliest")
                .option("endingOffsets", "latest")
                .load()
            )
            
            # Convert value column from binary to string
            df = df.selectExpr("CAST(value AS STRING) as json_data")
            
            # Parse JSON data
            return SparkDFDataset(df)
            
        elif args.source == "postgres":
            if not args.table:
                logger.error("Table is required for Postgres source")
                return None
                
            # Read from PostgreSQL
            df = (
                spark
                .read
                .format("jdbc")
                .option("url", os.environ.get("POSTGRES_JDBC_URL"))
                .option("dbtable", args.table)
                .option("user", os.environ.get("POSTGRES_USER"))
                .option("password", os.environ.get("POSTGRES_PASSWORD"))
                .load()
            )
            
            return SparkDFDataset(df)
            
        elif args.source == "s3":
            if not args.s3_path:
                logger.error("S3 path is required for S3 source")
                return None
                
            # Read from S3
            df = (
                spark
                .read
                .format("parquet")
                .load(args.s3_path)
            )
            
            return SparkDFDataset(df)
            
        else:
            logger.error(f"Unsupported source: {args.source}")
            return None
            
    except Exception as e:
        logger.error(f"Error reading data from {args.source}: {str(e)}")
        return None

def validate_data(dataset: SparkDFDataset, expectation_suite_name: str) -> Dict[str, Any]:
    """Validate data using Great Expectations."""
    try:
        # Load expectation suite
        context = ge.data_context.DataContext()
        suite = context.get_expectation_suite(expectation_suite_name)
        
        # Attach expectation suite to dataset
        dataset.expectation_suite = suite
        
        # Validate dataset
        results = dataset.validate()
        
        return results
    except Exception as e:
        logger.error(f"Error validating data: {str(e)}")
        return {"success": False, "error": str(e)}

def save_validation_results(results: Dict[str, Any], output_path: str) -> None:
    """Save validation results to the specified output path."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_results_{timestamp}.json"
        full_path = os.path.join(output_path, filename)
        
        with open(full_path, "w") as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Validation results saved to {full_path}")
    except Exception as e:
        logger.error(f"Error saving validation results: {str(e)}")

def main():
    """Main function."""
    args = parse_args()
    
    logger.info("Starting data validation job")
    
    # Create Spark session
    spark = create_spark_session()
    
    # Read data from source
    dataset = read_data_from_source(spark, args)
    if not dataset:
        logger.error("Failed to read data from source")
        sys.exit(1)
    
    # Validate data
    results = validate_data(dataset, args.expectation_suite)
    
    # Save validation results
    save_validation_results(results, args.output_path)
    
    # Log validation summary
    if results.get("success", False):
        logger.info("Data validation succeeded")
    else:
        logger.error("Data validation failed")
        sys.exit(1)
    
    logger.info("Data validation job completed")
    spark.stop()

if __name__ == "__main__":
    main()
EOF

echo -e "${GREEN}Spark data validation job created.${NC}"
echo ""

# Create a Spark application yaml for the data validator
cat <<EOF > kubernetes/spark/data-validator.yaml
apiVersion: "sparkoperator.k8s.io/v1beta2"
kind: SparkApplication
metadata:
  name: data-validator
  namespace: spark
spec:
  type: Python
  mode: cluster
  image: "$(ECR_REPO)/mlops/spark-driver:latest"
  imagePullPolicy: Always
  mainApplicationFile: local:///opt/spark/work-dir/data_validator.py
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
      - name: KAFKA_BOOTSTRAP_SERVERS
        value: kafka-bootstrap.kafka.svc.cluster.local:9092
      - name: POSTGRES_JDBC_URL
        value: jdbc:postgresql://postgres.storage.svc.cluster.local:5432/mlops
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
  executor:
    cores: 1
    instances: 1
    memory: "1024m"
    labels:
      version: 3.4.1
  volumes:
    - name: great-expectations-volume
      hostPath:
        path: /opt/great-expectations
        type: DirectoryOrCreate
    - name: validation-results-volume
      hostPath:
        path: /opt/validation-results
        type: DirectoryOrCreate
EOF

echo -e "${GREEN}Data validator Spark application configuration created.${NC}"
echo ""

# Print completion message
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   MLOps Platform Data Processing Layer Deployed!    ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo ""
echo -e "Components deployed:"
echo -e "  - ${YELLOW}Spark Operator${NC} (namespace: spark)"
echo -e "  - ${YELLOW}Airflow${NC} (namespace: airflow)"
echo -e "  - ${YELLOW}Data validation pipelines${NC} using Great Expectations"
echo ""
echo -e "Next steps:"
echo -e "  1. Build and push the Spark Docker image"
echo -e "  2. Update the Spark application configurations with your ECR repository"
echo -e "  3. Deploy your Spark applications"
echo -e "  4. Access Airflow UI via port-forward: kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow"
echo ""
echo -e "${GREEN}======================================================${NC}" 