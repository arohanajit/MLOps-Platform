"""
Observability utilities for the model serving component.
This module provides functions for setting up OpenTelemetry instrumentation.
"""

import os
import logging
from typing import Dict, Any, Optional, List

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Setup logging
logger = logging.getLogger(__name__)

def setup_opentelemetry(
    service_name: str,
    version: str,
    otlp_endpoint: Optional[str] = None,
    attributes: Optional[Dict[str, str]] = None,
    sample_rate: float = 1.0
) -> None:
    """
    Set up OpenTelemetry for the application.
    
    Args:
        service_name: The name of the service.
        version: The version of the service.
        otlp_endpoint: The OTLP endpoint to export telemetry to.
        attributes: Additional resource attributes.
        sample_rate: The sampling rate (0.0 to 1.0).
    """
    # Default OTLP endpoint (OpenTelemetry Collector)
    if otlp_endpoint is None:
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.monitoring.svc.cluster.local:4317")
    
    # Create resource with service info and custom attributes
    resource_attributes = {
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: version,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("DEPLOYMENT_ENVIRONMENT", "production"),
    }
    
    # Add custom attributes if provided
    if attributes:
        resource_attributes.update(attributes)
    
    # Create resource
    resource = Resource.create(resource_attributes)
    
    # Set up trace provider with resource
    trace_provider = TracerProvider(resource=resource)
    
    # Create OTLP trace exporter
    otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    
    # Add OTLP trace exporter to the trace provider
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    
    # Set global trace provider
    trace.set_tracer_provider(trace_provider)
    
    # Create OTLP metric exporter
    otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    
    # Create metric reader with OTLP exporter
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter, export_interval_millis=10000)
    
    # Create meter provider with resource and reader
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    
    # Set global meter provider
    metrics.set_meter_provider(meter_provider)
    
    # Log success
    logger.info(f"OpenTelemetry initialized for {service_name} v{version} with endpoint {otlp_endpoint}")

def instrument_flask(app) -> None:
    """
    Instrument a Flask application with OpenTelemetry.
    
    Args:
        app: The Flask application to instrument.
    """
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    logger.info("Flask application instrumented with OpenTelemetry")

def create_model_serving_metrics(model_name: str) -> Dict[str, Any]:
    """
    Create metrics for model serving.
    
    Args:
        model_name: The name of the model.
        
    Returns:
        A dictionary of metrics.
    """
    meter = metrics.get_meter("model_serving")
    
    # Create counters
    prediction_counter = meter.create_counter(
        name="model_prediction_count",
        description="Number of predictions made",
        unit="1",
    )
    
    error_counter = meter.create_counter(
        name="model_prediction_error_count",
        description="Number of prediction errors",
        unit="1",
    )
    
    # Create histogram for latency
    latency_histogram = meter.create_histogram(
        name="model_prediction_latency",
        description="Latency of model predictions",
        unit="ms",
    )
    
    # Create up/down counter for drift score
    drift_gauge = meter.create_up_down_counter(
        name="model_prediction_drift_score",
        description="Drift score of model predictions",
        unit="1",
    )
    
    # Create histogram for prediction values (for distribution tracking)
    prediction_value_histogram = meter.create_histogram(
        name="model_prediction_value",
        description="Distribution of prediction values",
        unit="1",
    )
    
    return {
        "prediction_counter": prediction_counter,
        "error_counter": error_counter,
        "latency_histogram": latency_histogram,
        "drift_gauge": drift_gauge,
        "prediction_value_histogram": prediction_value_histogram,
    }

def log_prediction(
    metrics: Dict[str, Any],
    model_name: str,
    features: Dict[str, Any],
    prediction: Any,
    latency_ms: float,
    error: Optional[str] = None,
    drift_score: Optional[float] = None,
) -> None:
    """
    Log a prediction event with metrics.
    
    Args:
        metrics: The metrics dictionary created by create_model_serving_metrics.
        model_name: The name of the model.
        features: The input features.
        prediction: The prediction result.
        latency_ms: The latency in milliseconds.
        error: An error message, if any.
        drift_score: The drift score, if available.
    """
    # Create attributes for metrics
    attributes = {
        "model.name": model_name,
        "model.version": os.getenv("MODEL_VERSION", "unknown"),
    }
    
    # Log prediction count
    metrics["prediction_counter"].add(1, attributes)
    
    # Log latency
    metrics["latency_histogram"].record(latency_ms, attributes)
    
    # Log error if any
    if error:
        metrics["error_counter"].add(1, attributes)
    
    # Log drift score if available
    if drift_score is not None:
        metrics["drift_gauge"].add(drift_score - (metrics["drift_gauge"].get_value() or 0), attributes)
    
    # Log prediction value for distribution tracking
    if isinstance(prediction, (int, float)):
        metrics["prediction_value_histogram"].record(float(prediction), attributes)
    elif isinstance(prediction, (list, tuple)) and all(isinstance(x, (int, float)) for x in prediction):
        for value in prediction:
            metrics["prediction_value_histogram"].record(float(value), attributes)
    
    # Get tracer
    tracer = trace.get_tracer("model_serving")
    
    # Create span for prediction
    with tracer.start_as_current_span(
        name=f"{model_name}_predict",
        attributes={
            "model.name": model_name,
            "model.version": os.getenv("MODEL_VERSION", "unknown"),
            "prediction.latency": latency_ms,
            "prediction.error": "true" if error else "false",
        }
    ):
        # Add feature names as span attributes
        for key in features.keys():
            trace.get_current_span().set_attribute(f"feature.{key}", "present")
        
        # Add error details if any
        if error:
            trace.get_current_span().set_attribute("error", True)
            trace.get_current_span().set_attribute("error.message", str(error))
        
        # Add drift score if available
        if drift_score is not None:
            trace.get_current_span().set_attribute("prediction.drift_score", drift_score) 