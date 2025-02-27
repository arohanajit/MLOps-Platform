"""
Feature Store API

This module implements the API for the Feature Store, allowing
users to retrieve feature values for model inference.
"""

import logging
import sys
import os
from typing import List, Dict, Any, Optional
import time

# Add the current directory to sys.path to find local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel

# Import from local module with proper path
from src.feature_store.feature_store import FeatureStore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Feature Store API",
    description="API for retrieving ML features for model inference",
    version="1.0.0"
)

# Initialize feature store
feature_store = FeatureStore()


# Request/Response models
class FeatureRequest(BaseModel):
    entity_id: str
    feature_names: List[str]
    entity_type: str
    
    class Config:
        schema_extra = {
            "example": {
                "entity_id": "customer123",
                "feature_names": [
                    "customer_total_purchases_30d",
                    "customer_days_since_last_purchase",
                    "customer_purchase_frequency_30d"
                ],
                "entity_type": "customer"
            }
        }


class BatchFeatureRequest(BaseModel):
    entity_ids: List[str]
    feature_names: List[str]
    entity_type: str
    
    class Config:
        schema_extra = {
            "example": {
                "entity_ids": ["customer123", "customer456", "customer789"],
                "feature_names": [
                    "customer_total_purchases_30d",
                    "customer_days_since_last_purchase",
                    "customer_purchase_frequency_30d"
                ],
                "entity_type": "customer"
            }
        }


class HistoricalFeatureRequest(BaseModel):
    entity_id: str
    feature_names: List[str]
    entity_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100
    
    class Config:
        schema_extra = {
            "example": {
                "entity_id": "customer123",
                "feature_names": [
                    "customer_total_purchases_30d",
                    "customer_days_since_last_purchase"
                ],
                "entity_type": "customer",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-04-01T00:00:00Z",
                "limit": 100
            }
        }


class FeatureStoreRequest(BaseModel):
    entity_id: str
    entity_type: str
    feature_values: Dict[str, Any]
    ttl: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "entity_id": "customer123",
                "entity_type": "customer",
                "feature_values": {
                    "customer_total_purchases_30d": 1250.75,
                    "customer_days_since_last_purchase": 3,
                    "customer_purchase_frequency_30d": 5
                },
                "ttl": 86400
            }
        }


class BatchStoreRequest(BaseModel):
    entity_feature_values: Dict[str, Dict[str, Any]]
    entity_type: str
    ttl: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "entity_feature_values": {
                    "customer123": {
                        "customer_total_purchases_30d": 1250.75,
                        "customer_days_since_last_purchase": 3
                    },
                    "customer456": {
                        "customer_total_purchases_30d": 753.25,
                        "customer_days_since_last_purchase": 7
                    }
                },
                "entity_type": "customer",
                "ttl": 86400
            }
        }


class FeatureResponse(BaseModel):
    entity_id: str
    features: Dict[str, Any]
    entity_type: str
    missing_features: List[str] = []
    timestamp: str


class BatchFeatureResponse(BaseModel):
    entities: Dict[str, Dict[str, Any]]
    entity_type: str
    timestamp: str


def get_store():
    """Dependency for getting the feature store."""
    return feature_store


@app.on_event("startup")
async def startup_event():
    """Initialize the feature store on startup."""
    logger.info("Initializing feature store schema")
    feature_store.initialize_schema()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "feature-store"}


@app.post("/features", response_model=FeatureResponse)
async def get_features(request: FeatureRequest, store: FeatureStore = Depends(get_store)):
    """
    Get feature values for an entity.
    """
    try:
        # Get the feature values
        features = store.get_feature_values(
            request.entity_id,
            request.feature_names,
            request.entity_type
        )
        
        # Check for missing features
        missing_features = [f for f in request.feature_names if f not in features]
        
        return FeatureResponse(
            entity_id=request.entity_id,
            features=features,
            entity_type=request.entity_type,
            missing_features=missing_features,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
    
    except Exception as e:
        logger.error(f"Error retrieving features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-features", response_model=BatchFeatureResponse)
async def get_batch_features(request: BatchFeatureRequest, store: FeatureStore = Depends(get_store)):
    """
    Get feature values for multiple entities in a batch.
    """
    try:
        # Get the feature values
        entities = store.get_batch_feature_values(
            request.entity_ids,
            request.feature_names,
            request.entity_type
        )
        
        return BatchFeatureResponse(
            entities=entities,
            entity_type=request.entity_type,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
    
    except Exception as e:
        logger.error(f"Error retrieving batch features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/historical-features")
async def get_historical_features(request: HistoricalFeatureRequest, store: FeatureStore = Depends(get_store)):
    """
    Get historical feature values for an entity.
    """
    try:
        # Get the historical feature values
        df = store.get_historical_feature_values(
            request.entity_id,
            request.feature_names,
            request.entity_type,
            request.start_time,
            request.end_time,
            request.limit
        )
        
        # Convert DataFrame to dictionary
        response = df.reset_index().to_dict(orient='records')
        
        return {
            "entity_id": request.entity_id,
            "entity_type": request.entity_type,
            "feature_history": response
        }
    
    except Exception as e:
        logger.error(f"Error retrieving historical features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/store-features", status_code=201)
async def store_features(request: FeatureStoreRequest, store: FeatureStore = Depends(get_store)):
    """
    Store feature values for an entity.
    """
    try:
        # Store the feature values
        store.store_feature_values(
            request.entity_id,
            request.feature_values,
            request.entity_type,
            request.ttl
        )
        
        # Also store in historical storage
        store.store_historical_features(
            request.entity_id,
            request.feature_values,
            request.entity_type
        )
        
        return {
            "status": "success",
            "message": f"Stored {len(request.feature_values)} features for {request.entity_type}:{request.entity_id}"
        }
    
    except Exception as e:
        logger.error(f"Error storing features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-store-features", status_code=201)
async def batch_store_features(request: BatchStoreRequest, store: FeatureStore = Depends(get_store)):
    """
    Store feature values for multiple entities in a batch.
    """
    try:
        # Store the feature values
        store.store_batch_feature_values(
            request.entity_feature_values,
            request.entity_type,
            request.ttl
        )
        
        # Also store in historical storage
        for entity_id, feature_values in request.entity_feature_values.items():
            store.store_historical_features(
                entity_id,
                feature_values,
                request.entity_type
            )
        
        return {
            "status": "success",
            "message": f"Stored features for {len(request.entity_feature_values)} entities of type {request.entity_type}"
        }
    
    except Exception as e:
        logger.error(f"Error storing batch features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vector/{entity_type}/{entity_id}")
async def get_feature_vector(
    entity_type: str,
    entity_id: str,
    feature_names: List[str] = Query(...),
    store: FeatureStore = Depends(get_store)
):
    """
    Get a feature vector for model inference.
    """
    try:
        # Get the feature vector
        vector = store.create_feature_vector(
            entity_id,
            feature_names,
            entity_type
        )
        
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "feature_vector": vector,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    except Exception as e:
        logger.error(f"Error creating feature vector: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 