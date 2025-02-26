"""
Feature Registry API

This module implements the API for the feature registry, allowing
users to register, discover, and retrieve feature metadata.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from models import Feature, FeatureGroup, ValueType, FeatureSource, FeatureCategory, FeatureFrequency
from storage import PostgresFeatureStore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Feature Registry API",
    description="API for registering and discovering ML features",
    version="1.0.0"
)

# Initialize storage backend
feature_store = PostgresFeatureStore()


# Request/Response models
class FeatureRequest(BaseModel):
    name: str
    description: str
    entity_type: str
    value_type: ValueType
    source: FeatureSource
    category: FeatureCategory
    frequency: FeatureFrequency
    owner: str
    tags: List[str] = []
    source_config: Dict[str, Any] = {}
    transformations: List[Dict[str, Any]] = []
    
    class Config:
        schema_extra = {
            "example": {
                "name": "customer_total_purchases_30d",
                "description": "Total purchase amount by customer in last 30 days",
                "entity_type": "customer",
                "value_type": "FLOAT",
                "source": "BATCH",
                "category": "DERIVED",
                "frequency": "DAILY",
                "owner": "data-science-team",
                "tags": ["purchase", "monetary", "customer_360"],
                "source_config": {
                    "table": "customer_purchases",
                    "filter": "purchase_date >= NOW() - INTERVAL '30 days'"
                },
                "transformations": [
                    {
                        "type": "aggregation",
                        "function": "sum",
                        "column": "purchase_amount"
                    }
                ]
            }
        }


class FeatureGroupRequest(BaseModel):
    name: str
    description: str
    feature_names: List[str]
    entity_type: str
    owner: str
    tags: List[str] = []
    
    class Config:
        schema_extra = {
            "example": {
                "name": "customer_rfm_features",
                "description": "RFM (Recency, Frequency, Monetary) features for customer segmentation",
                "feature_names": [
                    "customer_days_since_last_purchase",
                    "customer_purchase_frequency_30d",
                    "customer_total_purchases_30d"
                ],
                "entity_type": "customer",
                "owner": "data-science-team",
                "tags": ["rfm", "segmentation", "customer_360"]
            }
        }


class FeatureResponse(BaseModel):
    name: str
    description: str
    entity_type: str
    value_type: str
    source: str
    category: str
    frequency: str
    owner: str
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    versions: List[Dict[str, Any]] = []
    source_config: Dict[str, Any] = {}
    transformations: List[Dict[str, Any]] = []
    stats: Optional[Dict[str, Any]] = None


class FeatureGroupResponse(BaseModel):
    name: str
    description: str
    feature_names: List[str]
    entity_type: str
    owner: str
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ListResponse(BaseModel):
    count: int
    data: List[Any]


def get_store():
    """Dependency for getting the feature store."""
    return feature_store


@app.on_event("startup")
async def startup_event():
    """Initialize the feature registry on startup."""
    logger.info("Initializing feature registry schema")
    feature_store.initialize_schema()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "feature-registry"}


@app.post("/features", response_model=FeatureResponse, status_code=201)
async def create_feature(feature_data: FeatureRequest, store: PostgresFeatureStore = Depends(get_store)):
    """Create a new feature in the registry."""
    try:
        # Check if feature already exists
        existing = store.get_feature(feature_data.name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Feature '{feature_data.name}' already exists")
        
        # Create new feature
        feature = Feature(
            name=feature_data.name,
            description=feature_data.description,
            entity_type=feature_data.entity_type,
            value_type=feature_data.value_type,
            source=feature_data.source,
            category=feature_data.category,
            frequency=feature_data.frequency,
            owner=feature_data.owner,
            tags=feature_data.tags,
            source_config=feature_data.source_config,
            transformations=feature_data.transformations
        )
        
        # Save feature
        store.save_feature(feature)
        
        # Convert to response model
        return FeatureResponse(
            name=feature.name,
            description=feature.description,
            entity_type=feature.entity_type,
            value_type=feature.value_type.value,
            source=feature.source.value,
            category=feature.category.value,
            frequency=feature.frequency.value,
            owner=feature.owner,
            tags=feature.tags,
            created_at=feature.created_at.isoformat() if feature.created_at else None,
            updated_at=feature.updated_at.isoformat() if feature.updated_at else None,
            versions=[{
                "version": v.version,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None
            } for v in feature.versions],
            source_config=feature.source_config,
            transformations=feature.transformations,
            stats=feature.stats.dict() if feature.stats else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/features/{name}", response_model=FeatureResponse)
async def get_feature(name: str, store: PostgresFeatureStore = Depends(get_store)):
    """Get a feature by name."""
    feature = store.get_feature(name)
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    
    return FeatureResponse(
        name=feature.name,
        description=feature.description,
        entity_type=feature.entity_type,
        value_type=feature.value_type.value,
        source=feature.source.value,
        category=feature.category.value,
        frequency=feature.frequency.value,
        owner=feature.owner,
        tags=feature.tags,
        created_at=feature.created_at.isoformat() if feature.created_at else None,
        updated_at=feature.updated_at.isoformat() if feature.updated_at else None,
        versions=[{
            "version": v.version,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None
        } for v in feature.versions],
        source_config=feature.source_config,
        transformations=feature.transformations,
        stats=feature.stats.dict() if feature.stats else None
    )


@app.get("/features", response_model=ListResponse)
async def list_features(
    entity_type: Optional[str] = None,
    category: Optional[str] = None,
    store: PostgresFeatureStore = Depends(get_store)
):
    """List features, optionally filtered by entity type or category."""
    features = store.list_features(entity_type=entity_type, category=category)
    
    response_features = [
        FeatureResponse(
            name=feature.name,
            description=feature.description,
            entity_type=feature.entity_type,
            value_type=feature.value_type.value,
            source=feature.source.value,
            category=feature.category.value,
            frequency=feature.frequency.value,
            owner=feature.owner,
            tags=feature.tags,
            created_at=feature.created_at.isoformat() if feature.created_at else None,
            updated_at=feature.updated_at.isoformat() if feature.updated_at else None,
            versions=[{
                "version": v.version,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None
            } for v in feature.versions],
            source_config=feature.source_config,
            transformations=feature.transformations,
            stats=feature.stats.dict() if feature.stats else None
        )
        for feature in features
    ]
    
    return ListResponse(count=len(response_features), data=response_features)


@app.delete("/features/{name}", status_code=204)
async def delete_feature(name: str, store: PostgresFeatureStore = Depends(get_store)):
    """Delete a feature by name."""
    deleted = store.delete_feature(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")


@app.post("/feature-groups", response_model=FeatureGroupResponse, status_code=201)
async def create_feature_group(
    group_data: FeatureGroupRequest,
    store: PostgresFeatureStore = Depends(get_store)
):
    """Create a new feature group in the registry."""
    try:
        # Check if group already exists
        existing = store.get_feature_group(group_data.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Feature group '{group_data.name}' already exists"
            )
        
        # Verify that all features exist
        for feature_name in group_data.feature_names:
            if not store.get_feature(feature_name):
                raise HTTPException(
                    status_code=400,
                    detail=f"Feature '{feature_name}' not found"
                )
        
        # Create new feature group
        group = FeatureGroup(
            name=group_data.name,
            description=group_data.description,
            feature_names=group_data.feature_names,
            entity_type=group_data.entity_type,
            owner=group_data.owner,
            tags=group_data.tags
        )
        
        # Save feature group
        store.save_feature_group(group)
        
        # Convert to response model
        return FeatureGroupResponse(
            name=group.name,
            description=group.description,
            feature_names=group.feature_names,
            entity_type=group.entity_type,
            owner=group.owner,
            tags=group.tags,
            created_at=group.created_at.isoformat() if group.created_at else None,
            updated_at=group.updated_at.isoformat() if group.updated_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating feature group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feature-groups/{name}", response_model=FeatureGroupResponse)
async def get_feature_group(name: str, store: PostgresFeatureStore = Depends(get_store)):
    """Get a feature group by name."""
    group = store.get_feature_group(name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Feature group '{name}' not found")
    
    return FeatureGroupResponse(
        name=group.name,
        description=group.description,
        feature_names=group.feature_names,
        entity_type=group.entity_type,
        owner=group.owner,
        tags=group.tags,
        created_at=group.created_at.isoformat() if group.created_at else None,
        updated_at=group.updated_at.isoformat() if group.updated_at else None
    )


@app.get("/feature-groups", response_model=ListResponse)
async def list_feature_groups(store: PostgresFeatureStore = Depends(get_store)):
    """List all feature groups."""
    groups = store.list_feature_groups()
    
    response_groups = [
        FeatureGroupResponse(
            name=group.name,
            description=group.description,
            feature_names=group.feature_names,
            entity_type=group.entity_type,
            owner=group.owner,
            tags=group.tags,
            created_at=group.created_at.isoformat() if group.created_at else None,
            updated_at=group.updated_at.isoformat() if group.updated_at else None
        )
        for group in groups
    ]
    
    return ListResponse(count=len(response_groups), data=response_groups)


@app.delete("/feature-groups/{name}", status_code=204)
async def delete_feature_group(name: str, store: PostgresFeatureStore = Depends(get_store)):
    """Delete a feature group by name."""
    deleted = store.delete_feature_group(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feature group '{name}' not found") 