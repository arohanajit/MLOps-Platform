"""
Test imports for feature-registry
"""

try:
    import models
    print("Successfully imported models directly")
except ImportError as e:
    print(f"Failed to import models directly: {e}")
    
try:
    from models import Feature
    print("Successfully imported Feature from models")
except ImportError as e:
    print(f"Failed to import Feature from models: {e}")
    
try:
    from .models import Feature
    print("Successfully imported Feature from .models")
except ImportError as e:
    print(f"Failed to import Feature from .models: {e}")
    
try:
    import storage
    print("Successfully imported storage directly")
except ImportError as e:
    print(f"Failed to import storage directly: {e}") 