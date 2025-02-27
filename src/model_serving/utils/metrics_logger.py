"""Metrics logging utility for model serving."""
import json
import logging
import time
from typing import Dict, Any, Optional
import threading

class MetricsLogger:
    """Logger for model serving metrics including latency and request/response data."""
    
    def __init__(self, model_name: str, version: str, log_file: Optional[str] = None):
        """
        Initialize the metrics logger.
        
        Args:
            model_name: Name of the model being served
            version: Version or stage of the model
            log_file: Optional path to log file, if None logs to console only
        """
        self.model_name = model_name
        self.version = version
        self.logger = logging.getLogger(f"MetricsLogger-{model_name}")
        
        if log_file:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Thread local storage for timing
        self.thread_local = threading.local()
    
    def start_request(self, request_id: str, request_data: Dict[str, Any]) -> None:
        """
        Log the start of a request and store the start time.
        
        Args:
            request_id: Unique identifier for the request
            request_data: The request data (features)
        """
        self.thread_local.start_time = time.time()
        self.thread_local.request_id = request_id
        
        # Log request data (be careful with PII)
        self.logger.info(
            f"Request {request_id} started for model {self.model_name}:{self.version} - "
            f"Input size: {len(json.dumps(request_data))} bytes"
        )
    
    def end_request(self, prediction: Any) -> float:
        """
        Log the end of a request with prediction result and return the latency.
        
        Args:
            prediction: The prediction result
            
        Returns:
            Request latency in milliseconds
        """
        end_time = time.time()
        start_time = getattr(self.thread_local, 'start_time', end_time)
        request_id = getattr(self.thread_local, 'request_id', 'unknown')
        
        latency_ms = (end_time - start_time) * 1000
        
        # Log prediction result (be careful with PII)
        if isinstance(prediction, (list, dict)):
            pred_size = len(json.dumps(prediction))
            pred_type = type(prediction).__name__
        else:
            pred_size = len(str(prediction))
            pred_type = type(prediction).__name__
        
        self.logger.info(
            f"Request {request_id} completed in {latency_ms:.2f}ms - "
            f"Model: {self.model_name}:{self.version} - "
            f"Result type: {pred_type}, size: {pred_size} bytes"
        )
        
        return latency_ms
    
    def log_error(self, error: Exception, request_id: Optional[str] = None) -> None:
        """
        Log an error during model prediction.
        
        Args:
            error: The exception that occurred
            request_id: Optional request identifier
        """
        if request_id is None:
            request_id = getattr(self.thread_local, 'request_id', 'unknown')
            
        self.logger.error(
            f"Error in request {request_id} for model {self.model_name}:{self.version} - "
            f"{type(error).__name__}: {str(error)}"
        )
        
    def log_model_loaded(self) -> None:
        """Log when a model is successfully loaded."""
        self.logger.info(f"Model {self.model_name}:{self.version} successfully loaded")
        
    def log_model_load_failed(self, error: Exception) -> None:
        """Log when a model fails to load."""
        self.logger.error(
            f"Failed to load model {self.model_name}:{self.version} - "
            f"{type(error).__name__}: {str(error)}"
        ) 