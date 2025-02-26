#!/usr/bin/env python3
"""
Data Pipeline Test Runner

This script runs all the tests for the data pipeline components and reports the results.
It can run individual component tests or all tests together.

Usage:
    python run_all_tests.py [--component COMPONENT] [--verbose]

Options:
    --component COMPONENT   Run tests for a specific component only. 
                           Valid options: client, cdc, spark, storage.
    --verbose               Enable verbose output

Example:
    # Run all tests
    python run_all_tests.py
    
    # Run only the client tests with verbose output
    python run_all_tests.py --component client --verbose
"""

import os
import sys
import time
import argparse
import logging
import subprocess
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data_pipeline_test_results.log")
    ]
)
logger = logging.getLogger("TestRunner")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Data Pipeline Test Runner")
    parser.add_argument(
        "--component", 
        choices=["client", "cdc", "spark", "storage"],
        help="Run tests for a specific component only"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()

def run_test(test_script: str, verbose: bool = False) -> bool:
    """Run a test script and return whether it passed."""
    cmd = [sys.executable, test_script]
    
    if verbose:
        cmd.append("--verbose")
    
    logger.info(f"Running test: {test_script}")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # Log the output
        for line in result.stdout.splitlines():
            logger.info(f"  {line}")
        
        for line in result.stderr.splitlines():
            logger.warning(f"  {line}")
        
        # Check the return code
        success = result.returncode == 0
        
        # Log the result
        elapsed_time = time.time() - start_time
        if success:
            logger.info(f"Test {test_script} PASSED in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"Test {test_script} FAILED in {elapsed_time:.2f} seconds")
        
        return success
    
    except Exception as e:
        logger.error(f"Error running test {test_script}: {str(e)}")
        return False

def run_client_tests(verbose: bool = False) -> bool:
    """Run tests for the client components."""
    logger.info("Running CLIENT tests...")
    # Add --mock option for test_event_logger.py to avoid requiring a real Kafka cluster
    cmd = [sys.executable, "src/tests/test_event_logger.py", "--mock"]
    
    if verbose:
        cmd.append("--verbose")
    
    logger.info(f"Running test: src/tests/test_event_logger.py")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # Log the output
        for line in result.stdout.splitlines():
            logger.info(f"  {line}")
        
        for line in result.stderr.splitlines():
            logger.warning(f"  {line}")
        
        # Check the return code
        success = result.returncode == 0
        
        # Log the result
        elapsed_time = time.time() - start_time
        if success:
            logger.info(f"Test src/tests/test_event_logger.py PASSED in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"Test src/tests/test_event_logger.py FAILED in {elapsed_time:.2f} seconds")
        
        return success
    
    except Exception as e:
        logger.error(f"Error running test src/tests/test_event_logger.py: {str(e)}")
        return False

def run_cdc_tests(verbose: bool = False) -> bool:
    """Run tests for the CDC components."""
    logger.info("Running CDC tests...")
    # Add --mock option for test_cdc.py to avoid requiring a real PostgreSQL and Kafka cluster
    cmd = [sys.executable, "src/tests/test_cdc.py", "--mock"]
    
    if verbose:
        cmd.append("--verbose")
    
    logger.info(f"Running test: src/tests/test_cdc.py")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # Log the output
        for line in result.stdout.splitlines():
            logger.info(f"  {line}")
        
        for line in result.stderr.splitlines():
            logger.warning(f"  {line}")
        
        # Check the return code
        success = result.returncode == 0
        
        # Log the result
        elapsed_time = time.time() - start_time
        if success:
            logger.info(f"Test src/tests/test_cdc.py PASSED in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"Test src/tests/test_cdc.py FAILED in {elapsed_time:.2f} seconds")
        
        return success
    
    except Exception as e:
        logger.error(f"Error running test src/tests/test_cdc.py: {str(e)}")
        return False

def run_spark_tests(verbose: bool = False) -> bool:
    """Run tests for the Spark streaming components."""
    logger.info("Running SPARK tests...")
    return run_test("src/tests/test_spark.py", verbose)

def run_storage_tests(verbose: bool = False) -> bool:
    """Run tests for the storage components."""
    logger.info("Running STORAGE tests...")
    return run_test("src/tests/test_storage.py", verbose)

def run_all_tests(verbose: bool = False) -> Dict[str, bool]:
    """Run all test components and return the results."""
    results = {}
    
    # Run client tests
    results["client"] = run_client_tests(verbose)
    
    # Run CDC tests
    results["cdc"] = run_cdc_tests(verbose)
    
    # Run Spark tests
    results["spark"] = run_spark_tests(verbose)
    
    # Run storage tests
    results["storage"] = run_storage_tests(verbose)
    
    return results

def main():
    """Main function."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Make sure we're in the root directory of the project
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(os.path.dirname(script_dir)))
    
    start_time = time.time()
    logger.info("Starting Data Pipeline tests")
    
    # Run the specified component test or all tests
    if args.component:
        if args.component == "client":
            success = run_client_tests(args.verbose)
        elif args.component == "cdc":
            success = run_cdc_tests(args.verbose)
        elif args.component == "spark":
            success = run_spark_tests(args.verbose)
        elif args.component == "storage":
            success = run_storage_tests(args.verbose)
        else:
            logger.error(f"Unknown component: {args.component}")
            sys.exit(1)
        
        # Exit with the appropriate status code
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        results = run_all_tests(args.verbose)
        
        # Print the summary
        logger.info("=" * 50)
        logger.info("Test Results Summary")
        logger.info("=" * 50)
        
        for component, success in results.items():
            status = "PASSED" if success else "FAILED"
            logger.info(f"{component.upper()} Tests: {status}")
        
        # Overall success if all tests passed
        overall_success = all(results.values())
        
        elapsed_time = time.time() - start_time
        if overall_success:
            logger.info(f"All tests PASSED in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"Some tests FAILED. Total run time: {elapsed_time:.2f} seconds")
        
        # Exit with the appropriate status code
        sys.exit(0 if overall_success else 1)

if __name__ == "__main__":
    main() 