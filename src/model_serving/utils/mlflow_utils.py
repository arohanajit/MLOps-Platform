"""MLflow utilities for model serving."""
import os
import logging
from typing import Dict, Any, Optional, Union

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger("MLflowUtils")

def load_model_from_registry(
    model_name: str, 
    version_or_stage: Union[str, int]
) -> Any:
    """
    Load a model from MLflow model registry.
    
    Args:
        model_name: Name of the model in the registry
        version_or_stage: Version number or stage name ('Production', 'Staging', etc.)
        
    Returns:
        Loaded model
    """
    client = MlflowClient()
    
    # Handle version as string or int
    if isinstance(version_or_stage, int) or (isinstance(version_or_stage, str) and version_or_stage.isdigit()):
        model_uri = f"models:/{model_name}/{version_or_stage}"
        logger.info(f"Loading model from URI: {model_uri}")
    else:
        # Handle stage names
        version_or_stage = version_or_stage.lower()
        if version_or_stage in ['production', 'staging', 'archived', 'none']:
            # Convert to title case for MLflow
            stage = version_or_stage.title()
            model_uri = f"models:/{model_name}/{stage}"
            logger.info(f"Loading model from URI: {model_uri}")
        else:
            raise ValueError(f"Invalid stage name: {version_or_stage}")
    
    # Load the model
    model = mlflow.pyfunc.load_model(model_uri)
    return model

def get_model_info(
    model_name: str, 
    version_or_stage: Union[str, int]
) -> Dict[str, Any]:
    """
    Get information about a model in the registry.
    
    Args:
        model_name: Name of the model in the registry
        version_or_stage: Version number or stage name ('Production', 'Staging', etc.)
        
    Returns:
        Dictionary with model information
    """
    client = MlflowClient()
    
    # Handle version as int or string
    if isinstance(version_or_stage, int) or (isinstance(version_or_stage, str) and version_or_stage.isdigit()):
        version = int(version_or_stage)
        model_version = client.get_model_version(model_name, version)
    else:
        # Handle stage names
        version_or_stage = version_or_stage.lower()
        if version_or_stage in ['production', 'staging', 'archived', 'none']:
            # Convert to title case for MLflow
            stage = version_or_stage.title()
            model_versions = client.get_latest_versions(model_name, stages=[stage])
            if not model_versions:
                raise ValueError(f"No model version found with stage {stage}")
            model_version = model_versions[0]
        else:
            raise ValueError(f"Invalid stage name: {version_or_stage}")
    
    # Extract model information
    info = {
        "name": model_version.name,
        "version": model_version.version,
        "stage": model_version.current_stage,
        "description": model_version.description or "",
        "run_id": model_version.run_id,
        "status": model_version.status,
        "creation_timestamp": model_version.creation_timestamp,
    }
    
    return info 