# MLOps Platform Management Script

The `mlops-platform.sh` script provides a unified interface for managing the MLOps platform in a local development environment. It simplifies common tasks such as starting and stopping services, checking status, and viewing logs.

## Usage

```bash
./mlops-platform.sh [command]
```

## Available Commands

| Command | Description |
|---------|-------------|
| `start` | Start the MLOps platform |
| `stop` | Stop the MLOps platform |
| `restart` | Restart the MLOps platform |
| `status` | Check status of all services |
| `logs [service]` | Show logs for a specific service or all services |
| `test` | Run tests against the platform |
| `verify` | Verify platform installation |
| `clean` | Remove all containers and volumes |
| `help` | Show help message |

## Examples

### Starting the Platform

```bash
./mlops-platform.sh start
```

This command starts all services defined in the `docker-compose.yml` file.

### Viewing Logs

View logs for all services:
```bash
./mlops-platform.sh logs
```

View logs for a specific service:
```bash
./mlops-platform.sh logs mlflow
```

Available services:
- `minio`
- `postgres`
- `redis`
- `zookeeper`
- `kafka`
- `schema-registry`
- `mlflow`
- `feature-registry`
- `feature-store`

### Testing the Platform

```bash
./mlops-platform.sh test
```

This command runs a series of tests to verify that all components are working correctly:
1. Checks if all services are running
2. Tests accessibility of Feature Registry API
3. Tests accessibility of Feature Store API
4. Tests accessibility of MLflow UI
5. Tests accessibility of MinIO API

### Cleaning Up

```bash
./mlops-platform.sh clean
```

This command stops all containers and removes volumes. Use with caution as it will delete all data.

## Service Access

After starting the platform, you can access the following services:

| Service | URL | Credentials |
|---------|-----|-------------|
| MLflow UI | http://localhost:5001 | N/A |
| Feature Registry API | http://localhost:8000 | N/A |
| Feature Store API | http://localhost:8001 | N/A |
| MinIO Console | http://localhost:9001 | Username: `minioadmin`<br>Password: `minioadmin` |
| Kafka | localhost:9092 | N/A |
| Schema Registry | http://localhost:8081 | N/A |

## Extending the Script

The script is designed to be extensible. If you need to add new commands, simply:

1. Add a new function in the script
2. Add a new case statement in the main execution section
3. Update the usage information in the `usage()` function

## Troubleshooting

### Common Issues

1. **Docker not running**: Ensure Docker Desktop or Docker daemon is running
2. **Port conflicts**: Check if any of the required ports (8000, 8001, 5001, 9000, 9001, 9092, etc.) are already in use
3. **Permission issues**: Ensure the script is executable (`chmod +x mlops-platform.sh`)
4. **Service not accessible**: Check individual service logs with `./mlops-platform.sh logs [service]`

### Viewing Docker Compose Configuration

To see the exact configuration used:

```bash
cat docker-compose.yml
```

### Manually Starting Specific Services

If you need to start specific services only:

```bash
docker-compose up -d [service1] [service2]
```

Example:
```bash
docker-compose up -d postgres redis
``` 