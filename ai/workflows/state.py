"""
State schema for LangGraph Error Analysis Workflow

Defines the state structure that flows through the workflow nodes.
"""

from typing import TypedDict, Optional, List, Dict, Any
from dataclasses import dataclass
import time

from ai.core.error_context_collector import ErrorInfo, FunctionContext, UsageContext

@dataclass
class DependencyInfo:
    """Information about file dependencies and imports"""
    file_path: str
    import_type: str  # 'import', 'require', 'include', etc.
    line_number: int
    import_statement: str
    
@dataclass
class ImpactAnalysis:
    """Analysis of error impact on dependent files"""
    risk_level: str  # 'high', 'medium', 'low'
    affected_files: List[str]
    fix_suggestions: List[str]
    breaking_changes: List[str]
    test_recommendations: List[str]
    confidence_score: float  # 0.0 to 1.0

@dataclass
class NodeMetrics:
    """Metrics for individual node execution"""
    node_name: str
    execution_time_ms: int
    memory_usage_mb: float
    cache_hit: bool
    retry_count: int
    error_count: int
    
@dataclass
class WorkflowMetrics:
    """Overall workflow execution metrics"""
    total_execution_time_ms: int
    total_memory_usage_mb: float
    cache_hit_rate: float
    node_metrics: List[NodeMetrics]
    started_at: float
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = time.time()

class AnalysisState(TypedDict):
    """
    Main state structure for the Error Analysis Workflow
    
    This state flows through all nodes in the LangGraph workflow and accumulates
    information at each step.
    """
    
    # Input
    raw_error: str
    workflow_id: str
    
    # Parsed Error Information
    parsed_error: Optional[ErrorInfo]
    
    # Function Analysis
    target_function: Optional[FunctionContext]
    
    # Dependency Analysis
    dependent_files: List[str]  # Files that import/use the target file
    import_dependencies: List[DependencyInfo]  # Detailed import information
    usage_contexts: List[UsageContext]  # How the function is used
    
    # Impact Analysis
    impact_analysis: Optional[ImpactAnalysis]
    
    # Error Handling
    error: Optional[str]  # Error message if any node fails
    warnings: List[str]  # Non-fatal warnings
    
    # Metrics and Performance
    metrics: WorkflowMetrics
    
    # Security and Sanitization
    sensitive_data_detected: bool
    sanitized_content: Dict[str, str]  # Original -> Sanitized mappings
    
    # Cache Information
    cache_keys: List[str]  # Cache keys used in this workflow
    cache_hits: int
    cache_misses: int
    
    # Configuration
    config_snapshot: Dict[str, Any]  # Snapshot of config used
    
    # Output Schema
    output_schema: Optional[Dict[str, Any]]  # Final JSON output

def create_initial_state(raw_error: str, workflow_id: str, config: Dict[str, Any]) -> AnalysisState:
    """
    Create initial state for the workflow
    
    Args:
        raw_error: The error string to analyze
        workflow_id: Unique identifier for this workflow run
        config: Configuration snapshot
        
    Returns:
        Initial AnalysisState
    """
    return AnalysisState(
        # Input
        raw_error=raw_error,
        workflow_id=workflow_id,
        
        # Parsed Error Information
        parsed_error=None,
        
        # Function Analysis
        target_function=None,
        
        # Dependency Analysis
        dependent_files=[],
        import_dependencies=[],
        usage_contexts=[],
        
        # Impact Analysis
        impact_analysis=None,
        
        # Error Handling
        error=None,
        warnings=[],
        
        # Metrics and Performance
        metrics=WorkflowMetrics(
            total_execution_time_ms=0,
            total_memory_usage_mb=0.0,
            cache_hit_rate=0.0,
            node_metrics=[],
            started_at=time.time()
        ),
        
        # Security and Sanitization
        sensitive_data_detected=False,
        sanitized_content={},
        
        # Cache Information
        cache_keys=[],
        cache_hits=0,
        cache_misses=0,
        
        # Configuration
        config_snapshot=config,
        
        # Output Schema
        output_schema=None
    )

def state_to_json_output(state: AnalysisState) -> Dict[str, Any]:
    """
    Convert final state to JSON output schema
    
    Args:
        state: Final workflow state
        
    Returns:
        JSON-serializable output
    """
    return {
        "workflow_id": state["workflow_id"],
        "timestamp": time.time(),
        "error_info": {
            "raw_error": state["raw_error"],
            "parsed_error": {
                "type": state["parsed_error"].error_type if state["parsed_error"] else None,
                "file": state["parsed_error"].file_path if state["parsed_error"] else None,
                "line": state["parsed_error"].line_number if state["parsed_error"] else None,
                "column": state["parsed_error"].column_number if state["parsed_error"] else None,
                "variable": state["parsed_error"].variable_or_symbol if state["parsed_error"] else None
            } if state["parsed_error"] else None
        },
        "function_context": {
            "name": state["target_function"].name if state["target_function"] else None,
            "file": state["target_function"].file_path if state["target_function"] else None,
            "language": state["target_function"].language if state["target_function"] else None,
            "signature": state["target_function"].signature if state["target_function"] else None,
            "parameters": state["target_function"].parameters if state["target_function"] else None,
            "documentation": state["target_function"].documentation if state["target_function"] else None
        } if state["target_function"] else None,
        "dependencies": {
            "dependent_files": state["dependent_files"],
            "import_dependencies": [
                {
                    "file": dep.file_path,
                    "type": dep.import_type,
                    "line": dep.line_number,
                    "statement": dep.import_statement
                } for dep in state["import_dependencies"]
            ],
            "usage_contexts": len(state["usage_contexts"]),
            "usage_summary": [
                {
                    "file": usage.file_path,
                    "line": usage.line_number,
                    "type": usage.usage_type,
                    "score": usage.score
                } for usage in state["usage_contexts"][:5]  # Top 5 usages
            ]
        },
        "impact_analysis": {
            "risk_level": state["impact_analysis"].risk_level if state["impact_analysis"] else "unknown",
            "affected_files": state["impact_analysis"].affected_files if state["impact_analysis"] else [],
            "fix_suggestions": state["impact_analysis"].fix_suggestions if state["impact_analysis"] else [],
            "breaking_changes": state["impact_analysis"].breaking_changes if state["impact_analysis"] else [],
            "test_recommendations": state["impact_analysis"].test_recommendations if state["impact_analysis"] else [],
            "confidence_score": state["impact_analysis"].confidence_score if state["impact_analysis"] else 0.0
        },
        "metrics": {
            "total_execution_time_ms": state["metrics"].total_execution_time_ms,
            "total_memory_usage_mb": state["metrics"].total_memory_usage_mb,
            "cache_hit_rate": state["metrics"].cache_hit_rate,
            "cache_hits": state["cache_hits"],
            "cache_misses": state["cache_misses"],
            "node_performance": [
                {
                    "node": metric.node_name,
                    "execution_time_ms": metric.execution_time_ms,
                    "memory_usage_mb": metric.memory_usage_mb,
                    "cache_hit": metric.cache_hit,
                    "retry_count": metric.retry_count,
                    "error_count": metric.error_count
                } for metric in state["metrics"].node_metrics
            ]
        },
        "security": {
            "sensitive_data_detected": state["sensitive_data_detected"],
            "sanitized_fields": len(state["sanitized_content"])
        },
        "status": {
            "success": state["error"] is None,
            "error": state["error"],
            "warnings": state["warnings"]
        }
    } 