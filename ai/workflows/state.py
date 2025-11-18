"""
State schema for LangGraph Error Analysis Workflow

Defines the state structure that flows through the workflow nodes.
"""

from typing import TypedDict, Optional, List, Dict, Any
from dataclasses import dataclass
import time

from ai.core.error_context_collector import Dependent, ErrorInfo, FunctionContext, UsageContext

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

    def convert_llm_response_to_impact(llm_response: Dict[str, Any]): # type: ignore
        """
        Converts the LLM fix result (JSON) into 
        an instance of the ImpactAnalysis class.
        """
        
        # --- Extract and infer data ---
        
        # 1. Get confidence_score (direct mapping)
        confidence = llm_response.get('confidence_score', 0.0)
        
        # 2. Get the affected file
        try:
            # Get the file path from the context
            file_path = llm_response['context_used']['error_info']['file']
            affected = [file_path]
        except (KeyError, TypeError):
            affected = []
            
        # 3. Create the fix suggestion (merge explanation and new_contents)
        explanation = llm_response.get('explanation', 'No explanation provided.')
        try:
            # Get the new code content (assuming new_contents is a list)
            fix_code = llm_response.get('new_contents', [''])[0].strip()
            suggestion = f"{explanation} | Suggested fix: `{fix_code}`"
        except (IndexError, TypeError):
            suggestion = explanation
            
        suggestions = [suggestion]

        # 4.Assign default values for fields not present in the llm_response
        # We cannot know "risk_level" or "breaking_changes" 
        # from the fix JSON, so we assign defaults.
        
        if confidence > 0.9:
            risk = 'low'
        elif confidence < 0.5:
            risk = 'high'
        else:  # Confidence is between 0.5 and 0.9 (inclusive)
            risk = 'medium'
        breaking = [] # Assume no breaking changes
        tests = ['Recommend writing a unit test for the fixed line of code.'] # Default test recommendation

        # --- Create and return the ImpactAnalysis object ---
        return ImpactAnalysis(
            risk_level=risk,
            affected_files=affected,
            fix_suggestions=suggestions,
            breaking_changes=breaking,
            test_recommendations=tests,
            confidence_score=confidence
        )

@dataclass
class ClassField:
    """Schema information for a class field/attribute"""
    name: str
    data_type: str
    visibility: str = "public"


@dataclass
class MethodParameter:
    """Schema information for a method parameter"""
    name: str
    data_type: str


@dataclass
class ClassMethod:
    """Schema information for a class method"""
    name: str
    parameters: List[MethodParameter]
    return_type: str
    visibility: str = "public"


@dataclass
class ClassDefinition:
    """Schema definition for a class within the codebase"""
    name: str
    file_path: str
    fields: List[ClassField]
    methods: List[ClassMethod]
    parent_class: Optional[str] = None

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
    parsed_errors: List[ErrorInfo]
    
    # Function Analysis
    affected_functions: List[FunctionContext]

    # Dependency Analysis
    affected_dependents: List[Dependent]

    # Class Structure Index
    class_definitions: List[ClassDefinition]
    
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
        parsed_errors=[],
        
        # Function Analysis
        affected_functions=[],
        
        # Dependency Analysis
        affected_dependents=[],
        class_definitions=[],
        
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
            "parsed_errors": [
                {
                    "type": error.error_type,
                    "file": error.file_path,
                    "line": error.line_number,
                    "column": error.column_number,
                    "variable": error.variable_or_symbol
                }
                for error in state["parsed_errors"]
            ]
        },
        "affected_functions": [
            {
                "signature": func.signature,
                "file": func.file_path,
                "language": func.language,
                "parameters": func.parameters,
                "implementation": func.implementation,
                "start": func.start_line,
                "end": func.end_line,
            }
            for func in state["affected_functions"]
        ],
        "dependencies": [
            {
                "file_path": dependent.file_path,
                "dependent_files": dependent.dependent_files,
                "dependent_files_count": dependent.dependent_files_count,
                
                "import_dependencies": [
                    {
                        "import_name": dep.import_name,
                        "resolved_path": dep.resolved_path,
                        "line_number": dep.line_number
                    } for dep in dependent.import_dependencies
                ],
                "import_dependencies_count": dependent.import_dependencies_count,
                
                "usage_contexts": [
                    {
                        "file_path": usage.file_path,
                        "line_number": usage.line_number,
                        "context_before": usage.context_before,
                        "context_after": usage.context_after,
                        "usage_type": usage.usage_type,
                        "score": usage.score
                    } for usage in dependent.usage_contexts[:5] 
                ],
                "usage_contexts_count": dependent.usage_contexts_count
            }
            for dependent in state.get("affected_dependents", [])
        ],
        "impact_analysis": {
            "risk_level": state["impact_analysis"].risk_level if state["impact_analysis"] else "unknown",
            "affected_files": state["impact_analysis"].affected_files if state["impact_analysis"] else [],
            "fix_suggestions": state["impact_analysis"].fix_suggestions if state["impact_analysis"] else [],
            "breaking_changes": state["impact_analysis"].breaking_changes if state["impact_analysis"] else [],
            "test_recommendations": state["impact_analysis"].test_recommendations if state["impact_analysis"] else [],
            "confidence_score": state["impact_analysis"].confidence_score if state["impact_analysis"] else 0.0
        },
        "class_definitions": [
            {
                "name": class_def.name,
                "file_path": class_def.file_path,
                "parent_class": class_def.parent_class,
                "fields": [
                    {
                        "name": field.name,
                        "data_type": field.data_type,
                        "visibility": field.visibility
                    }
                    for field in class_def.fields
                ],
                "methods": [
                    {
                        "name": method.name,
                        "parameters": [
                            {"name": param.name, "data_type": param.data_type}
                            for param in method.parameters
                        ],
                        "return_type": method.return_type,
                        "visibility": method.visibility
                    }
                    for method in class_def.methods
                ]
            }
            for class_def in state.get("class_definitions", [])
        ],
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
