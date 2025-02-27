"""
Test imports for feature-store
"""

try:
    import feature_store
    print("Successfully imported feature_store directly")
except ImportError as e:
    print(f"Failed to import feature_store directly: {e}")
    
try:
    from feature_store import FeatureStore
    print("Successfully imported FeatureStore from feature_store")
except ImportError as e:
    print(f"Failed to import FeatureStore from feature_store: {e}")
    
try:
    from .feature_store import FeatureStore
    print("Successfully imported FeatureStore from .feature_store")
except ImportError as e:
    print(f"Failed to import FeatureStore from .feature_store: {e}") 