# MLOps Platform Observability Components

This directory contains the Kubernetes manifests and configuration files for the observability components of the MLOps Platform.

## Components

### OpenTelemetry Collector

The OpenTelemetry Collector is used to collect metrics, traces, and logs from various components of the MLOps Platform. It provides a unified way to collect and export telemetry data.

- **Configuration**: `otel/otel-collector-config.yaml`
- **Deployment**: `otel/otel-collector.yaml`

### Prometheus

Prometheus is used to store metrics and provide a query language for analyzing them. It scrapes metrics from the OpenTelemetry Collector and other components.

- **Configuration**: `prometheus/prometheus-config.yaml`
- **Deployment**: `prometheus/prometheus.yaml`
- **Alert Rules**: `prometheus/alert-rules.yaml`

### Grafana

Grafana is used to visualize metrics and create dashboards for monitoring the MLOps Platform.

- **Deployment**: `grafana/grafana.yaml`
- **Dashboards**: `grafana/dashboards.yaml`

### Model Monitoring

The model monitoring component is responsible for detecting drift in model predictions and other model-related metrics.

- **Drift Detector**: `model-monitoring/drift-detector.yaml`

## Alternative: CloudWatch (Free Tier)

For deployments that want to leverage AWS CloudWatch for observability (using the free tier), we provide an alternative configuration.

- **OpenTelemetry for CloudWatch**: `cloudwatch/otel-cloudwatch.yaml`

## Deployment

To deploy the observability components, use the `deploy-observability.sh` script in the root directory of the project.

```bash
# Deploy all components
./deploy-observability.sh

# Deploy only specific components
./deploy-observability.sh --otel      # OpenTelemetry Collector
./deploy-observability.sh --prometheus # Prometheus
./deploy-observability.sh --grafana   # Grafana
./deploy-observability.sh --model-monitoring # Model Monitoring

# Setup port forwarding for local access
./deploy-observability.sh --port-forward
```

## Access

After deploying the components, you can access them locally using port forwarding:

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (default credentials: admin/admin)
- **OpenTelemetry Collector**: localhost:4317 (OTLP gRPC)

## Resource Requirements

The observability components are configured with minimal resource requirements to work on free-tier or small instances:

| Component | CPU Limit | Memory Limit | CPU Request | Memory Request |
|-----------|-----------|--------------|-------------|----------------|
| OpenTelemetry Collector | 200m | 400Mi | 100m | 200Mi |
| Prometheus | 500m | 1Gi | 200m | 512Mi |
| Grafana | 200m | 256Mi | 100m | 128Mi |
| Drift Detector | 500m | 1Gi | 200m | 512Mi |

## Integration with MLOps Components

### Instrumenting Services

To instrument your services to send telemetry data to the OpenTelemetry Collector:

1. Add the OpenTelemetry SDK to your application
2. Configure it to send data to the collector at `otel-collector.monitoring.svc.cluster.local:4317`

Example in Python:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure the tracer provider
resource = Resource(attributes={
    SERVICE_NAME: "your-service-name"
})
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Configure the OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint="otel-collector.monitoring.svc.cluster.local:4317",
    insecure=True
)
span_processor = BatchSpanProcessor(otlp_exporter)
tracer_provider.add_span_processor(span_processor)

# Get a tracer
tracer = trace.get_tracer(__name__)

# Use the tracer in your code
with tracer.start_as_current_span("my-operation"):
    # Your code here
    pass
```

### Prometheus Annotations

To have Prometheus automatically scrape metrics from your pods, add the following annotations to your pod template:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"  # The port your metrics endpoint is exposed on
  prometheus.io/path: "/metrics"  # The path to your metrics endpoint
```

## Adding Custom Dashboards

To add custom dashboards to Grafana:

1. Create a new ConfigMap with your dashboard JSON
2. Mount the ConfigMap as a volume in the Grafana pod
3. Update the `grafana-dashboard-provider` ConfigMap to include your dashboard

Example:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-custom-dashboard
  namespace: monitoring
data:
  my-dashboard.json: |
    {
      "title": "My Custom Dashboard",
      "panels": [
        ...
      ]
    }
```

## Troubleshooting

### Common Issues

1. **OpenTelemetry Collector not receiving data**: Check network policies and ensure your services are configured to send data to the correct endpoint.

2. **Prometheus not scraping metrics**: Check that your pods have the correct annotations and that the Prometheus configuration includes the correct job for your service.

3. **Grafana dashboards not showing data**: Verify that Grafana is correctly configured to use Prometheus as a data source and that the queries in your dashboards match the metrics being collected.

### Logs

To check logs from the observability components:

```bash
# OpenTelemetry Collector logs
kubectl logs -n monitoring deploy/otel-collector

# Prometheus logs
kubectl logs -n monitoring deploy/prometheus

# Grafana logs
kubectl logs -n monitoring deploy/grafana

# Drift Detector logs
kubectl logs -n monitoring deploy/drift-detector
```

## Free Tier Considerations

For running on free tier or minimal resources:

1. Use OpenTelemetry sampling to reduce the volume of telemetry data
2. Configure Prometheus retention to a shorter period (7 days instead of 15)
3. Limit the number of metrics collected to essential ones
4. Consider using CloudWatch as an alternative (10 metrics free) 