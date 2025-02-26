"""
Feature Registry Models

This module defines the data models for the feature registry.
"""

import datetime
import enum
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, validator


class ValueType(str, enum.Enum):
    """Enum for feature value types."""
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    BOOL = "BOOL"
    ARRAY = "ARRAY"
    MAP = "MAP"
    TIMESTAMP = "TIMESTAMP"


class FeatureSource(str, enum.Enum):
    """Enum for feature sources."""
    BATCH = "BATCH"
    STREAMING = "STREAMING"
    ONLINE = "ONLINE"
    DERIVED = "DERIVED"


class FeatureCategory(str, enum.Enum):
    """Enum for feature categories."""
    RAW = "RAW"
    DERIVED = "DERIVED"
    ENGINEERED = "ENGINEERED"
    TARGET = "TARGET"


class FeatureFrequency(str, enum.Enum):
    """Enum for feature update frequency."""
    REAL_TIME = "REAL_TIME"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    STATIC = "STATIC"


class SourceConfig(BaseModel):
    """Configuration for feature sources."""
    table: Optional[str] = None
    query: Optional[str] = None
    stream: Optional[str] = None
    config: Dict[str, Any] = {}


class TransformationStep(BaseModel):
    """Single transformation step for a feature."""
    type: str
    config: Dict[str, Any] = {}


class Transformation(BaseModel):
    """Transformation chain for a feature."""
    steps: List[TransformationStep] = []


class Stats(BaseModel):
    """Statistical metadata for a feature."""
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    stddev: Optional[float] = None
    unique_count: Optional[int] = None
    missing_percentage: Optional[float] = None
    histogram: Optional[Dict[str, Any]] = None


class FeatureVersion(BaseModel):
    """Version info for a feature."""
    version: int
    status: str = "ACTIVE"  # ACTIVE, DEPRECATED, ARCHIVED
    created_at: Optional[datetime.datetime] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = datetime.datetime.now(datetime.timezone.utc)
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }


class Feature(BaseModel):
    """Feature metadata model."""
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
    versions: List[FeatureVersion] = []
    stats: Optional[Stats] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if not self.versions:
            self.versions = [FeatureVersion(version=1)]
    
    @validator('updated_at', always=True)
    def updated_timestamp(cls, v):
        """Ensure updated_at is always current when feature is updated."""
        return datetime.datetime.now(datetime.timezone.utc)
    
    def add_version(self):
        """Add a new version of the feature."""
        if not self.versions:
            new_version = 1
        else:
            new_version = max(v.version for v in self.versions) + 1
        
        self.versions.append(FeatureVersion(version=new_version))
        return new_version
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }


class FeatureGroup(BaseModel):
    """Group of related features."""
    name: str
    description: str
    feature_names: List[str]
    entity_type: str
    owner: str
    tags: List[str] = []
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    @validator('updated_at', always=True)
    def updated_timestamp(cls, v):
        """Ensure updated_at is always current when group is updated."""
        return datetime.datetime.now(datetime.timezone.utc)
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }


class FeatureRegistry:
    """Registry of all features and groups."""
    
    def __init__(self):
        """Initialize an empty registry."""
        self.features: Dict[str, Feature] = {}
        self.groups: Dict[str, FeatureGroup] = {}
    
    def add_feature(self, feature: Feature):
        """Add a feature to the registry."""
        self.features[feature.name] = feature
    
    def get_feature(self, name: str) -> Optional[Feature]:
        """Get a feature by name."""
        return self.features.get(name)
    
    def add_group(self, group: FeatureGroup):
        """Add a feature group to the registry."""
        self.groups[group.name] = group
    
    def get_group(self, name: str) -> Optional[FeatureGroup]:
        """Get a feature group by name."""
        return self.groups.get(name)
    
    def list_features(self, entity_type: Optional[str] = None) -> List[Feature]:
        """List features, optionally filtered by entity type."""
        if entity_type:
            return [f for f in self.features.values() if f.entity_type == entity_type]
        return list(self.features.values())
    
    def list_groups(self) -> List[FeatureGroup]:
        """List all feature groups."""
        return list(self.groups.values()) 