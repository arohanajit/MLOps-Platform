"""
Feature Registry Storage

This module implements the storage backend for the feature registry,
allowing feature definitions to be persisted and retrieved.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Union
import datetime

import psycopg2
from psycopg2.extras import Json as PgJson
from psycopg2.extras import RealDictCursor

from src.feature_registry.models import Feature, FeatureGroup, FeatureRegistry

logger = logging.getLogger(__name__)


# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


class PostgresFeatureStore:
    """PostgreSQL storage backend for the feature registry."""
    
    def __init__(self, connection_params: Optional[Dict[str, Any]] = None):
        """Initialize the feature store with connection parameters."""
        self.connection_params = connection_params or {
            'host': os.environ.get('POSTGRES_HOST', 'postgresql.storage.svc.cluster.local'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'user': os.environ.get('POSTGRES_USER', 'mlops'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'password'),
            'dbname': os.environ.get('POSTGRES_DB', 'mlops')
        }
    
    def _get_connection(self):
        """Get a database connection."""
        return psycopg2.connect(**self.connection_params)
    
    def initialize_schema(self):
        """Create the necessary tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Create features table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_registry_features (
                name VARCHAR(255) PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """)
            
            # Create feature groups table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_registry_groups (
                name VARCHAR(255) PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """)
            
            # Create trigger for updated_at
            cursor.execute("""
            CREATE OR REPLACE FUNCTION update_modified_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
            """)
            
            # Create triggers
            for table in ['feature_registry_features', 'feature_registry_groups']:
                cursor.execute(f"""
                DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                
                CREATE TRIGGER update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_modified_column();
                """)
            
            conn.commit()
            logger.info("Feature registry schema initialized successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error initializing feature registry schema: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def save_feature(self, feature: Feature):
        """Save a feature to the registry."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Convert feature to JSON with custom encoder for datetime
            feature_data = json.loads(json.dumps(feature.dict(), cls=DateTimeEncoder))
            
            # Upsert the feature
            cursor.execute("""
            INSERT INTO feature_registry_features (name, data)
            VALUES (%s, %s)
            ON CONFLICT (name) 
            DO UPDATE SET data = %s, updated_at = NOW()
            """, (feature.name, PgJson(feature_data), PgJson(feature_data)))
            
            conn.commit()
            logger.info(f"Feature '{feature.name}' saved successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving feature '{feature.name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def save_feature_group(self, group: FeatureGroup):
        """Save a feature group to the registry."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Convert group to JSON with custom encoder for datetime
            group_data = json.loads(json.dumps(group.dict(), cls=DateTimeEncoder))
            
            # Upsert the group
            cursor.execute("""
            INSERT INTO feature_registry_groups (name, data)
            VALUES (%s, %s)
            ON CONFLICT (name) 
            DO UPDATE SET data = %s, updated_at = NOW()
            """, (group.name, PgJson(group_data), PgJson(group_data)))
            
            conn.commit()
            logger.info(f"Feature group '{group.name}' saved successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving feature group '{group.name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_feature(self, name: str) -> Optional[Feature]:
        """Get a feature by name."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
            SELECT data FROM feature_registry_features
            WHERE name = %s
            """, (name,))
            
            result = cursor.fetchone()
            if result:
                return Feature(**result['data'])
            return None
            
        except Exception as e:
            logger.error(f"Error getting feature '{name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_feature_group(self, name: str) -> Optional[FeatureGroup]:
        """Get a feature group by name."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
            SELECT data FROM feature_registry_groups
            WHERE name = %s
            """, (name,))
            
            result = cursor.fetchone()
            if result:
                return FeatureGroup(**result['data'])
            return None
            
        except Exception as e:
            logger.error(f"Error getting feature group '{name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def list_features(self, entity_type: Optional[str] = None, category: Optional[str] = None) -> List[Feature]:
        """List features, optionally filtered by entity type or category."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            query = "SELECT data FROM feature_registry_features"
            params = []
            
            # Add filters if provided
            if entity_type or category:
                query += " WHERE "
                conditions = []
                
                if entity_type:
                    conditions.append("data->>'entity_type' = %s")
                    params.append(entity_type)
                
                if category:
                    conditions.append("data->>'category' = %s")
                    params.append(category)
                
                query += " AND ".join(conditions)
            
            cursor.execute(query, tuple(params))
            
            results = cursor.fetchall()
            return [Feature(**row['data']) for row in results]
            
        except Exception as e:
            logger.error(f"Error listing features: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def list_feature_groups(self) -> List[FeatureGroup]:
        """List all feature groups."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("SELECT data FROM feature_registry_groups")
            
            results = cursor.fetchall()
            return [FeatureGroup(**row['data']) for row in results]
            
        except Exception as e:
            logger.error(f"Error listing feature groups: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def delete_feature(self, name: str) -> bool:
        """Delete a feature by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            DELETE FROM feature_registry_features
            WHERE name = %s
            RETURNING name
            """, (name,))
            
            deleted = cursor.fetchone() is not None
            conn.commit()
            
            if deleted:
                logger.info(f"Feature '{name}' deleted successfully")
            else:
                logger.warning(f"Feature '{name}' not found for deletion")
            
            return deleted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting feature '{name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def delete_feature_group(self, name: str) -> bool:
        """Delete a feature group by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            DELETE FROM feature_registry_groups
            WHERE name = %s
            RETURNING name
            """, (name,))
            
            deleted = cursor.fetchone() is not None
            conn.commit()
            
            if deleted:
                logger.info(f"Feature group '{name}' deleted successfully")
            else:
                logger.warning(f"Feature group '{name}' not found for deletion")
            
            return deleted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting feature group '{name}': {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def load_registry(self) -> FeatureRegistry:
        """Load the complete feature registry."""
        registry = FeatureRegistry()
        
        # Load all features
        features = self.list_features()
        for feature in features:
            registry.add_feature(feature)
        
        # Load all feature groups
        groups = self.list_feature_groups()
        for group in groups:
            registry.add_group(group)
        
        return registry 