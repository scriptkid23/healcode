"""
Example Usage of the Error Analysis Workflow

Demonstrates how to use the LangGraph-based error analysis system
with various configuration options and error types.
"""

import asyncio
import json
from pathlib import Path

from ai.workflows.error_analysis_graph import ErrorAnalysisWorkflow
from ai.workflows.config import WorkflowConfig
from indexer.zoekt_client import ZoektClient

async def basic_example():
    """Basic usage example with default configuration"""
    
    # Create configuration
    config = WorkflowConfig()
    
    # Initialize workflow
    workflow = ErrorAnalysisWorkflow(config)
    
    # Setup with Zoekt client (you would provide your actual Zoekt instance)
    zoekt_client = ZoektClient("http://localhost:6070")  # Replace with your Zoekt URL
    workflow.setup(zoekt_client)
    
    # Example error to analyze
    error_text = "NullPointerException at hello.java:15:22"
    
    # Run analysis
    result = await workflow.run_analysis(error_text)
    
    print("Analysis Result:")
    print(json.dumps(result, indent=2, default=str))
    
    return result

async def advanced_example():
    """Advanced usage with custom configuration"""
    
    # Create custom configuration
    config = WorkflowConfig()
    
    # Customize security settings
    config.security.max_memory_mb = 1024
    config.security.max_execution_time_seconds = 600
    config.security.enable_sandboxing = True
    
    # Customize performance settings
    config.performance.max_concurrent_nodes = 5
    config.performance.desired_cache_hit_rate = 0.9
    config.performance.max_dependency_depth = 5
    
    # Customize language support
    config.language.supported_languages = ['python', 'java', 'javascript', 'rust']
    config.language.fallback_to_regex = True
    
    # Customize LLM settings
    config.primary_model = "google_gemini"
    config.model_temperature = 0.05  # Very low for consistent results
    config.max_tokens = 4096
    
    # Enable metrics
    config.metrics.enable_metrics = True
    config.metrics.track_node_performance = True
    config.metrics.track_cache_performance = True
    
    # Initialize workflow
    workflow = ErrorAnalysisWorkflow(config)
    
    # Setup with Zoekt client
    zoekt_client = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt_client)
    
    # Multiple error examples
    error_examples = [
        "AttributeError: 'NoneType' object has no attribute 'get' at user_service.py:45",
        "TypeError: unsupported operand type(s) for +: 'int' and 'str' at calculator.py:23",
        "ReferenceError: calculateTotal is not defined at main.js:12",
        "cannot borrow `data` as mutable because it is also borrowed as immutable at processor.rs:67"
    ]
    
    results = []
    for error_text in error_examples:
        print(f"\nAnalyzing: {error_text}")
        result = await workflow.run_analysis(error_text)
        results.append(result)
        
        # Print summary
        print(f"Status: {'Success' if result['status']['success'] else 'Failed'}")
        print(f"Risk Level: {result['impact_analysis']['risk_level']}")
        print(f"Affected Files: {len(result['impact_analysis']['affected_files'])}")
        print(f"Execution Time: {result['metrics']['total_execution_time_ms']}ms")
        print(f"Cache Hit Rate: {result['metrics']['cache_hit_rate']:.2%}")
    
    return results

async def configuration_from_file_example():
    """Example using configuration from YAML file"""
    
    # Create a sample configuration file
    config_data = {
        'security': {
            'enable_sandboxing': True,
            'max_memory_mb': 512,
            'max_execution_time_seconds': 300
        },
        'performance': {
            'max_concurrent_nodes': 3,
            'cache_ttl_seconds': 7200,
            'desired_cache_hit_rate': 0.85,
            'max_dependency_depth': 4
        },
        'language': {
            'supported_languages': ['python', 'java', 'javascript', 'typescript'],
            'fallback_to_regex': True
        },
        'metrics': {
            'enable_metrics': True,
            'track_node_performance': True,
            'track_cache_performance': True
        },
        'primary_model': 'google_gemini',
        'model_temperature': 0.1,
        'max_tokens': 2048,
        'enable_few_shot': True
    }
    
    # Save to temporary file
    config_file = Path("temp_workflow_config.yaml")
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    try:
        # Load configuration from file
        config = WorkflowConfig.from_file(str(config_file))
        
        # Validate configuration
        issues = config.validate()
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  - {issue}")
        
        # Initialize workflow
        workflow = ErrorAnalysisWorkflow(config)
        
        # Setup and run analysis
        zoekt_client = ZoektClient("http://localhost:6070")
        workflow.setup(zoekt_client)
        
        error_text = "IndexError: list index out of range at data_processor.py:89"
        result = await workflow.run_analysis(error_text)
        
        print("Configuration-based Analysis Result:")
        print(json.dumps(result, indent=2, default=str))
        
        return result
        
    finally:
        # Clean up temporary file
        if config_file.exists():
            config_file.unlink()

async def environment_config_example():
    """Example using environment variables for configuration"""
    
    import os
    
    # Set environment variables
    os.environ['WORKFLOW_ENABLE_SANDBOXING'] = 'true'
    os.environ['WORKFLOW_MAX_MEMORY_MB'] = '1024'
    os.environ['WORKFLOW_MAX_EXECUTION_TIME'] = '600'
    os.environ['WORKFLOW_CACHE_TTL'] = '3600'
    os.environ['WORKFLOW_DESIRED_CACHE_HIT_RATE'] = '0.8'
    os.environ['WORKFLOW_PRIMARY_MODEL'] = 'google_gemini'
    os.environ['WORKFLOW_MODEL_TEMPERATURE'] = '0.1'
    
    # Create configuration from environment
    config = WorkflowConfig.from_env()
    
    # Initialize workflow
    workflow = ErrorAnalysisWorkflow(config)
    
    # Setup and run analysis
    zoekt_client = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt_client)
    
    error_text = "FileNotFoundError: [Errno 2] No such file or directory: 'config.json' at app.py:15"
    result = await workflow.run_analysis(error_text, workspace_path="/path/to/project")
    
    print("Environment-based Analysis Result:")
    print(json.dumps(result, indent=2, default=str))
    
    return result

async def batch_analysis_example():
    """Example of batch processing multiple errors"""
    
    config = WorkflowConfig()
    config.performance.max_concurrent_nodes = 5  # Higher concurrency for batch processing
    config.metrics.enable_metrics = True
    
    workflow = ErrorAnalysisWorkflow(config)
    zoekt_client = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt_client)
    
    # Batch of errors to analyze
    error_batch = [
        "ValueError: invalid literal for int() with base 10: 'abc' at parser.py:34",
        "KeyError: 'user_id' at session_manager.py:78",
        "ImportError: No module named 'requests' at api_client.py:1",
        "SyntaxError: invalid syntax at config.py:12",
        "MemoryError: Unable to allocate array at large_processor.py:156"
    ]
    
    # Process batch concurrently
    tasks = []
    for i, error_text in enumerate(error_batch):
        task = workflow.run_analysis(error_text)
        tasks.append(task)
    
    # Wait for all analyses to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful_analyses = 0
    total_execution_time = 0
    total_cache_hits = 0
    total_cache_operations = 0
    
    print("Batch Analysis Results:")
    print("=" * 50)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Error {i+1}: Failed - {result}")
            continue
            
        successful_analyses += 1
        total_execution_time += result['metrics']['total_execution_time_ms']
        total_cache_hits += result['metrics']['cache_hits']
        total_cache_operations += result['metrics']['cache_hits'] + result['metrics']['cache_misses']
        
        print(f"Error {i+1}: {result['status']['success']}")
        print(f"  Risk: {result['impact_analysis']['risk_level']}")
        print(f"  Time: {result['metrics']['total_execution_time_ms']}ms")
        print(f"  Files: {len(result['impact_analysis']['affected_files'])}")
    
    print("\nBatch Summary:")
    print(f"Successful analyses: {successful_analyses}/{len(error_batch)}")
    print(f"Total execution time: {total_execution_time}ms")
    print(f"Average execution time: {total_execution_time/max(successful_analyses, 1):.1f}ms")
    print(f"Overall cache hit rate: {total_cache_hits/max(total_cache_operations, 1):.2%}")
    
    return results

async def custom_few_shot_example():
    """Example with custom few-shot examples"""
    
    from ai.workflows.few_shot_examples import ErrorExample, FewShotExampleManager
    
    # Create custom example
    custom_example = ErrorExample(
        error_type="CustomError",
        error_pattern=r"CustomError: (.+)",
        language="python",
        description="Custom application error",
        error_context="""
def process_data(data):
    if not validate_data(data):
        raise CustomError("Invalid data format")
    return transform_data(data)
""",
        fix_suggestion="""
def process_data(data):
    # Add proper validation
    if not data:
        raise ValueError("Data cannot be empty")
    
    if not validate_data(data):
        # Log the specific validation error
        logger.error(f"Data validation failed: {data}")
        raise CustomError("Invalid data format")
    
    return transform_data(data)
""",
        explanation="Add proper input validation and logging for better error handling.",
        confidence_score=0.9,
        tags=["validation", "custom_error", "logging"]
    )
    
    # Create configuration
    config = WorkflowConfig()
    config.enable_few_shot = True
    
    # Initialize workflow
    workflow = ErrorAnalysisWorkflow(config)
    
    # Add custom example
    workflow.few_shot_manager.add_custom_example(custom_example)
    
    # Setup and run analysis
    zoekt_client = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt_client)
    
    error_text = "CustomError: Invalid data format at data_processor.py:25"
    result = await workflow.run_analysis(error_text)
    
    print("Custom Few-Shot Analysis Result:")
    print(json.dumps(result, indent=2, default=str))
    
    return result

async def workflow_statistics_example():
    """Example showing workflow statistics and monitoring"""
    
    config = WorkflowConfig()
    config.metrics.enable_metrics = True
    config.metrics.track_node_performance = True
    config.metrics.track_cache_performance = True
    
    workflow = ErrorAnalysisWorkflow(config)
    zoekt_client = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt_client)
    
    # Get workflow statistics
    stats = workflow.get_workflow_statistics()
    
    print("Workflow Statistics:")
    print(json.dumps(stats, indent=2, default=str))
    
    # Run a few analyses to generate metrics
    test_errors = [
        "TypeError: 'NoneType' object is not subscriptable at handler.py:42",
        "ValueError: Math domain error at calculator.py:15"
    ]
    
    for error_text in test_errors:
        result = await workflow.run_analysis(error_text)
        print(f"\nAnalyzed: {error_text}")
        print(f"Success: {result['status']['success']}")
        print(f"Execution time: {result['metrics']['total_execution_time_ms']}ms")
        print(f"Memory usage: {result['metrics']['total_memory_usage_mb']:.2f}MB")
        print(f"Cache hit rate: {result['metrics']['cache_hit_rate']:.2%}")
    
    return stats

def main():
    """Main function to run examples"""
    
    print("Error Analysis Workflow Examples")
    print("=" * 40)
    
    # Choose which example to run
    examples = {
        '1': ('Basic Example', basic_example),
        '2': ('Advanced Example', advanced_example),
        '3': ('Configuration from File', configuration_from_file_example),
        '4': ('Environment Configuration', environment_config_example),
        '5': ('Batch Analysis', batch_analysis_example),
        '6': ('Custom Few-Shot', custom_few_shot_example),
        '7': ('Workflow Statistics', workflow_statistics_example)
    }
    
    print("\nAvailable examples:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    
    choice = input("\nEnter example number (or 'all' for all examples): ").strip()
    
    if choice.lower() == 'all':
        # Run all examples
        for key, (name, func) in examples.items():
            print(f"\n{'='*50}")
            print(f"Running: {name}")
            print('='*50)
            try:
                asyncio.run(func())
            except Exception as e:
                print(f"Example failed: {e}")
    elif choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}")
        try:
            asyncio.run(func())
        except Exception as e:
            print(f"Example failed: {e}")
    else:
        print("Invalid choice. Running basic example...")
        asyncio.run(basic_example())

if __name__ == "__main__":
    main() 