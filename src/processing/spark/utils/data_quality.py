#!/usr/bin/env python3
"""
Data Quality Validation Utilities

Provides helper functions to validate data using Great Expectations
within Spark jobs. Optimized for AWS Free Tier resource constraints.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from pyspark.sql import DataFrame
import great_expectations as ge
from great_expectations.dataset import SparkDFDataset
from great_expectations.validator.validator import Validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataQualityUtils")

class DataQualityValidator:
    """Data quality validation using Great Expectations with Spark."""
    
    def __init__(self, ge_root_dir: str = "/opt/great-expectations"):
        """
        Initialize the data quality validator.
        
        Args:
            ge_root_dir: Path to the Great Expectations directory
        """
        self.ge_root_dir = ge_root_dir
        self._context = None
        
    @property
    def context(self):
        """Lazily initialize the Great Expectations context."""
        if self._context is None:
            try:
                self._context = ge.data_context.DataContext(self.ge_root_dir)
            except Exception as e:
                logger.error(f"Error initializing Great Expectations context: {str(e)}")
                raise
        return self._context
    
    def validate_dataframe(
        self, 
        df: DataFrame, 
        expectation_suite_name: str,
        run_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a Spark DataFrame using a Great Expectations suite.
        
        Args:
            df: Spark DataFrame to validate
            expectation_suite_name: Name of the expectation suite to use
            run_name: Optional run name for the validation
            
        Returns:
            Validation result dictionary
        """
        try:
            # Convert to Great Expectations dataset
            ge_dataset = SparkDFDataset(df)
            
            # Get the expectation suite
            suite = self.context.get_expectation_suite(expectation_suite_name)
            
            # Set the expectation suite on the dataset
            ge_dataset.expectation_suite = suite
            
            # Generate run name if not provided
            if run_name is None:
                run_name = f"spark_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Validate the dataset
            results = ge_dataset.validate(
                expectation_suite=suite,
                run_name=run_name
            )
            
            # Log validation summary
            if results["success"]:
                logger.info(
                    f"Validation succeeded: "
                    f"{results['statistics']['successful_expectations']} of "
                    f"{results['statistics']['evaluated_expectations']} expectations passed"
                )
            else:
                logger.warning(
                    f"Validation failed: "
                    f"{results['statistics']['unsuccessful_expectations']} of "
                    f"{results['statistics']['evaluated_expectations']} expectations failed"
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating DataFrame: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def validate_batch(
        self,
        batch_id: str,
        df: DataFrame,
        expectation_suite_name: str,
        run_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a batch of data and store results in the Great Expectations store.
        
        Args:
            batch_id: Batch identifier
            df: Spark DataFrame to validate
            expectation_suite_name: Name of the expectation suite to use
            run_name: Optional run name for the validation
            
        Returns:
            Validation result dictionary
        """
        try:
            # Convert to Great Expectations dataset
            ge_dataset = SparkDFDataset(df)
            
            # Get the expectation suite
            suite = self.context.get_expectation_suite(expectation_suite_name)
            
            # Create a validator
            validator = Validator(
                execution_engine=ge_dataset.execution_engine,
                expectation_suite=suite,
                data_context=self.context
            )
            
            # Generate run name if not provided
            if run_name is None:
                run_name = f"spark_batch_{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Validate the batch
            results = validator.validate(run_name=run_name)
            
            # Store validation results
            self.context.store_validation_result(
                results,
                expectation_suite_name=expectation_suite_name,
                run_id=run_name
            )
            
            # Log validation summary
            if results["success"]:
                logger.info(
                    f"Batch {batch_id} validation succeeded: "
                    f"{results['statistics']['successful_expectations']} of "
                    f"{results['statistics']['evaluated_expectations']} expectations passed"
                )
            else:
                logger.warning(
                    f"Batch {batch_id} validation failed: "
                    f"{results['statistics']['unsuccessful_expectations']} of "
                    f"{results['statistics']['evaluated_expectations']} expectations failed"
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating batch {batch_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def save_validation_result(
        self, 
        results: Dict[str, Any], 
        output_path: str
    ) -> None:
        """
        Save validation results to a file.
        
        Args:
            results: Validation results dictionary
            output_path: Path to save the results
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write results to file
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
                
            logger.info(f"Validation results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving validation results: {str(e)}")

def create_expectation_suite(
    context: ge.data_context.DataContext,
    suite_name: str,
    expectations: List[Dict[str, Any]]
) -> None:
    """
    Create or update an expectation suite.
    
    Args:
        context: Great Expectations context
        suite_name: Name of the suite to create or update
        expectations: List of expectation configurations
    """
    try:
        # Create empty suite
        suite = context.create_expectation_suite(
            expectation_suite_name=suite_name,
            overwrite_existing=True
        )
        
        # Add expectations
        for expectation in expectations:
            suite.add_expectation(
                ge.core.expectation_configuration.ExpectationConfiguration(
                    expectation_type=expectation["expectation_type"],
                    kwargs=expectation["kwargs"],
                    meta=expectation.get("meta", {})
                )
            )
        
        # Save the suite
        context.save_expectation_suite(suite)
        logger.info(f"Expectation suite {suite_name} created/updated with {len(expectations)} expectations")
        
    except Exception as e:
        logger.error(f"Error creating expectation suite {suite_name}: {str(e)}")
        raise 