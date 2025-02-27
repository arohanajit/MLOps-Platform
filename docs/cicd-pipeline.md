# CI/CD Pipeline Documentation

This document explains the Continuous Integration and Continuous Deployment (CI/CD) pipeline implemented for the MLOps Platform project.

## Overview

Our CI/CD pipeline leverages GitHub Actions to automate testing, building, and deploying the MLOps platform components. The pipeline is designed to be efficient, using GitHub's free tier minutes effectively.

## Pipeline Components

The CI/CD pipeline consists of three main workflow files:

1. **`run-tests.yml`**: Runs automated tests for individual components and all tests together
2. **`code-quality.yml`**: Performs code quality checks including linting, formatting, and security scanning
3. **`build-and-deploy.yml`**: Builds Docker images and deploys them to the Kubernetes cluster

## Pipeline Workflow

### When a Developer Creates a PR:

1. The `run-tests.yml` workflow runs tests for each component in parallel
2. The `code-quality.yml` workflow checks code style, formatting, and security issues
3. PR reviewers are notified and can see the test and code quality results

### When a PR is Merged to Develop:

1. The `run-tests.yml` workflow runs all tests
2. The `code-quality.yml` workflow checks code quality
3. No automatic deployment is performed (deployment to development is manual)

### When Code is Pushed to Main:

1. The `run-tests.yml` workflow runs all tests
2. The `code-quality.yml` workflow checks code quality
3. The `build-and-deploy.yml` workflow:
   - Builds Docker images for each component
   - Tags images with the git SHA
   - Pushes images to GitHub Container Registry
   - Updates Kubernetes manifests with new image tags
   - Deploys to the development environment

### When a Release Tag is Created:

1. The `run-tests.yml` workflow runs all tests
2. The `code-quality.yml` workflow checks code quality
3. The `build-and-deploy.yml` workflow:
   - Builds Docker images for each component
   - Tags images with the version number and 'latest'
   - Pushes images to GitHub Container Registry
   - Updates Kubernetes manifests with new image tags
   - Deploys to the requested environment (development, staging, or production)

## GitHub Actions Workflows in Detail

### `run-tests.yml`

- Runs tests for components individually in parallel (client, cdc, spark, storage)
- Uploads test results as artifacts
- For PRs and workflow dispatches, also runs the full test suite

### `code-quality.yml`

- Performs linting with flake8
- Checks code formatting with black
- Validates imports with isort
- Performs type checking with mypy
- Runs security scanning with bandit
- Checks dependencies for vulnerabilities with safety

### `build-and-deploy.yml`

- Builds Docker images for all components
- Tags images appropriately based on the trigger (commit SHA or version tag)
- Pushes images to GitHub Container Registry
- Updates Kubernetes manifests with new image tags
- Deploys to the appropriate environment
- Verifies successful deployment

## Environment Deployments

- **Development**: Automatic deployment when merging to main
- **Staging**: Manual trigger via workflow dispatch or new version tag
- **Production**: Manual trigger via workflow dispatch or new version tag

## Secrets Management

The following secrets are required in GitHub:

- `KUBECONFIG`: Kubernetes configuration file (base64 encoded)
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions
- Optional: `DOCKER_HUB_USERNAME` and `DOCKER_HUB_PASSWORD` if using Docker Hub

## Free Tier Optimization

The pipeline is optimized to work within GitHub Actions free tier limits:

- Parallel jobs are used efficiently
- Caching is implemented for Docker builds
- Tests are run in parallel to speed up execution
- Build artifacts are reused across workflow steps

## Monitoring the Pipeline

- Check workflow status on the "Actions" tab in GitHub
- Review logs for any failed steps
- Test artifacts are available for download after each run

## Troubleshooting

### Common Issues

- **Tests failing**: Check the test logs to identify the specific test and failure reason
- **Build errors**: Review Docker build logs for issues with dependencies or configurations
- **Deployment failures**: Check Kubernetes logs and ensure the cluster is accessible

### Debugging Steps

1. Check workflow logs in GitHub Actions
2. Look for specific error messages
3. Try to reproduce the issue locally
4. Check if the issue is environment-specific

## Adding New Components

When adding a new component to the platform:

1. Add appropriate tests to the component's test directory
2. Update the `run-tests.yml` workflow if needed
3. Create a Dockerfile for the component
4. Add the component to the build and deploy workflow

## Future Improvements

- Add integration with centralized logging
- Implement canary deployments for production
- Add performance testing to the pipeline
- Implement infrastructure validation tests 