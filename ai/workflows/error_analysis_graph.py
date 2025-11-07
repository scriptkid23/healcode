"""
LangGraph Error Analysis Workflow

Main workflow implementation using LangGraph for comprehensive error analysis
with security, caching, retry mechanisms, and multi-language support.
"""

import asyncio
import os
import time
import uuid
import json
import re
import warnings
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import psutil
import traceback

USING_MOCK_LANGGRAPH = False

try:
    from langgraph import StateGraph, END
except ImportError:
    USING_MOCK_LANGGRAPH = True
    warnings.warn(
        "LangGraph not installed; falling back to mock implementation. "
        "Install langgraph via `pip install langgraph` for production use.",
        RuntimeWarning,
    )

    # Fallback for development - create mock classes
    class StateGraph:
        def __init__(self, state_schema=None):
            self.nodes = {}
            self.edges = []
            self.entry_point = None
            
        def add_node(self, name: str, func):
            self.nodes[name] = func
            
        def add_edge(self, from_node: str, to_node: str):
            self.edges.append((from_node, to_node))
            
        def set_entry_point(self, node: str):
            self.entry_point = node
            
        def compile(self):
            return MockCompiledGraph(self)
    
    class MockCompiledGraph:
        def __init__(self, graph):
            self.graph = graph
            
        async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
            # Simple sequential execution for development
            current_state = state.copy()
            
            # Execute nodes in order
            for node_name in ['parse_error', 'parse_file', 'find_dependencies', 'analyze_impact']:
                if node_name in self.graph.nodes:
                    try:
                        current_state = await self.graph.nodes[node_name](current_state)
                    except Exception as e:
                        current_state['error'] = str(e)
                        break
            
            return current_state
    
    END = "__END__"

from ai.workflows.state import AnalysisState, create_initial_state, state_to_json_output, NodeMetrics, ImpactAnalysis
from ai.workflows.config import WorkflowConfig
from ai.workflows.enhanced_parsers import MultiLanguageFunctionAnalyzer
from ai.workflows.enhanced_zoekt_manager import EnhancedZoektSearchManager
from ai.workflows.few_shot_examples import FewShotExampleManager
from ai.core.error_context_collector import ErrorInfo
from ai.services.ai_service import AIService
from indexer.zoekt_client import ZoektClient

class ErrorInputParser:
    """Parse raw error strings into structured ErrorInfo objects."""

    _PATTERN_VARIABLE_ERROR = re.compile(r"(\w+)\s+(\w+)\s+error\s+([^\s]+)\s+(\d+):(\d+)")
    _PATTERN_LOCATION_ERROR = re.compile(r"([^\s:]+):(\d+):(\d+)\s*-\s*.*?(\w+)")
    _PATTERN_STACK_ERROR = re.compile(r"(\w+Error):\s*.*?\s+at\s+([^\s:]+):(\d+):(\d+)")
    _PATTERN_FILE = re.compile(r"([^\s:]+\.[a-zA-Z]+)")
    _PATTERN_LINE = re.compile(r":(\d+)")

    def parse(self, error_input: str) -> ErrorInfo:
        """Parse a raw error string into ErrorInfo."""
        match = self._PATTERN_VARIABLE_ERROR.search(error_input)
        print(match)
        if match:
            return ErrorInfo(
                variable_or_symbol=match.group(1),
                error_type=match.group(2),
                file_path=match.group(3),
                line_number=int(match.group(4)),
                column_number=int(match.group(5)),
            )

        match = self._PATTERN_LOCATION_ERROR.search(error_input)
        if match:
            return ErrorInfo(
                file_path=match.group(1),
                line_number=int(match.group(2)),
                column_number=int(match.group(3)),
                error_type=match.group(4),
                variable_or_symbol="",
            )

        match = self._PATTERN_STACK_ERROR.search(error_input)
        if match:
            return ErrorInfo(
                error_type=match.group(1),
                file_path=match.group(2),
                line_number=int(match.group(3)),
                column_number=int(match.group(4)),
                variable_or_symbol="",
            )

        file_match = self._PATTERN_FILE.search(error_input)
        line_match = self._PATTERN_LINE.search(error_input)
        if file_match and line_match:
            return ErrorInfo(
                file_path=file_match.group(1),
                line_number=int(line_match.group(1)),
                error_type="unknown",
                variable_or_symbol="",
            )

        raise ValueError(f"Unable to parse error input: {error_input}")


class SecurityManager:
    """Handles security aspects of the workflow."""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config.security
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.sensitive_patterns
        ]
    
    def sanitize_content(self, content: str) -> Tuple[str, Dict[str, str]]:
        """
        Sanitize content by redacting sensitive information.
        
        Returns:
            Tuple of (sanitized_content, redaction_mapping)
        """
        if not content:
            return content, {}
        
        redactions: Dict[str, str] = {}
        sanitized = content
        
        for idx, pattern in enumerate(self._compiled_patterns):
            for match in pattern.finditer(sanitized):
                original = match.group(0)
                placeholder = f"{self.config.redaction_placeholder}_{idx}_{len(redactions)}"
                redactions[placeholder] = original
                sanitized = sanitized.replace(original, placeholder)
        
        return sanitized, redactions
    
    def check_memory_usage(self) -> float:
        """Check current memory usage in MB and enforce configured limit."""
        memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        if memory_mb > self.config.max_memory_mb:
            raise MemoryError(
                f"Memory usage ({memory_mb:.1f}MB) exceeds limit "
                f"({self.config.max_memory_mb}MB)"
            )
        return memory_mb


class WorkflowCacheManager:
    """Lightweight in-memory cache with TTL for workflow artifacts."""

    def __init__(self, ttl_seconds: int, max_entries: int = 2048):
        self.ttl_seconds = max(1, ttl_seconds)
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired."""
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None

            value, expires_at = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store value with TTL, evicting the oldest entry if capacity exceeded."""
        async with self._lock:
            expires_at = time.time() + (ttl or self.ttl_seconds)
            self._store[key] = (value, expires_at)

            if len(self._store) > self.max_entries:
                oldest_key = min(self._store.items(), key=lambda item: item[1][1])[0]
                self._store.pop(oldest_key, None)

class MetricsCollector:
    """Collects and manages workflow metrics"""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.enabled = config.metrics.enable_metrics
        
    def record_node_start(self, node_name: str, state: AnalysisState) -> Dict[str, Any]:
        """Record node execution start"""
        if not self.enabled:
            return {}
            
        return {
            'node_name': node_name,
            'start_time': time.time(),
            'memory_before': psutil.Process().memory_info().rss / 1024 / 1024
        }
    
    def record_node_end(self, node_context: Dict[str, Any], 
                       state: AnalysisState, 
                       success: bool, 
                       retry_count: int = 0) -> NodeMetrics:
        """Record node execution end and return metrics"""
        if not self.enabled:
            return NodeMetrics(
                node_name=node_context.get('node_name', 'unknown'),
                execution_time_ms=0,
                memory_usage_mb=0.0,
                cache_hit=False,
                retry_count=retry_count,
                error_count=0 if success else 1
            )
        
        end_time = time.time()
        start_time = node_context.get('start_time', end_time)
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024
        memory_before = node_context.get('memory_before', memory_after)
        
        return NodeMetrics(
            node_name=node_context['node_name'],
            execution_time_ms=int((end_time - start_time) * 1000),
            memory_usage_mb=memory_after - memory_before,
            cache_hit=node_context.get('cache_hit', False),
            retry_count=retry_count,
            error_count=0 if success else 1
        )

class ErrorAnalysisWorkflow:
    """
    Main LangGraph workflow for comprehensive error analysis
    
    Implements a 4-node workflow:
    1. parse_error: Parse and extract error information
    2. parse_file: Analyze the target file and function
    3. find_dependencies: Find imports and dependencies
    4. analyze_impact: Perform impact analysis with LLM
    """
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._retry_state_key = "_retry_counts"
        
        self._validate_langgraph_usage()
        
        # Initialize components
        self.security_manager = SecurityManager(config)
        self.metrics_collector = MetricsCollector(config)
        self.cache_manager = WorkflowCacheManager(config.performance.cache_ttl_seconds)
        self.few_shot_manager = FewShotExampleManager(config.few_shot_examples_path)
        self.error_parser = ErrorInputParser()
        
        # Initialize AI service with validation/fallback
        self.ai_service: Optional[AIService] = self._initialize_ai_service(config)
        
        # Initialize search and parsing services (will be set up in setup method)
        self.zoekt_manager: Optional[EnhancedZoektSearchManager] = None
        self.function_analyzer: Optional[MultiLanguageFunctionAnalyzer] = None
        
        # Create the graph
        self.graph = self._create_graph()
        self.compiled_graph = self.graph.compile()
        self._node_registry = {
            "parse_error": self._parse_error_node,
            "parse_file": self._parse_file_node,
            "find_dependencies": self._find_dependencies_node,
            "analyze_impact": self._analyze_impact_node,
        }

    def _validate_langgraph_usage(self) -> None:
        """Ensure we are not accidentally running with the mock graph."""
        allow_mock = getattr(self.config, "allow_mock_langgraph", True)
        if USING_MOCK_LANGGRAPH and not allow_mock:
            raise RuntimeError(
                "LangGraph is not installed and mock usage is disabled. "
                "Install langgraph (`pip install langgraph`) or set "
                "`allow_mock_langgraph=True` in WorkflowConfig for development."
            )

    def _initialize_ai_service(self, config: WorkflowConfig) -> Optional[AIService]:
        """Initialize AI service with validation and graceful fallback."""
        valid_models = {"google_gemini", "openai", "anthropic"}
        env_var_mapping = {
            "google_gemini": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        
        try:
            if config.primary_model not in valid_models:
                raise ValueError(
                    f"Invalid model: {config.primary_model}. "
                    f"Supported models: {sorted(valid_models)}"
                )
            
            env_var = env_var_mapping.get(config.primary_model)
            api_key = config.ai_api_key or (os.environ.get(env_var) if env_var else None)
            if not api_key:
                raise ValueError(
                    f"Missing API key for primary model '{config.primary_model}'. "
                    f"Set `ai_api_key` in WorkflowConfig or export {env_var}."
                )
            
            model_config = {
                config.primary_model: {
                    "name": config.ai_model,
                    "endpoint": config.ai_endpoint,
                    "api_key": api_key,
                }
            }
            
            return AIService(
                tenant_id=config.tenant_id,
                redis_url=config.redis_url,
                model_configs=model_config,
                primary_model=config.primary_model,
            )
        except Exception as exc:
            if config.enable_llm_fallback:
                warnings.warn(
                    f"Failed to initialize AI service: {exc}. "
                    "Continuing with fallback analysis only.",
                    RuntimeWarning,
                )
                return None
            raise RuntimeError(
                "Failed to initialize AI service and fallback is disabled."
            ) from exc
    
    def setup(self, zoekt_client: ZoektClient):
        """Setup the workflow with required dependencies"""
        self.zoekt_manager = EnhancedZoektSearchManager(
            zoekt_client, 
            self.config.performance,
            self.config.security
        )
        
        self.function_analyzer = MultiLanguageFunctionAnalyzer(
            self.config.security,
            self.config.language
        )
    
    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow"""
        graph = StateGraph(AnalysisState)
        
        # Add nodes
        graph.add_node("parse_error", self._parse_error_node)
        graph.add_node("parse_file", self._parse_file_node)
        graph.add_node("find_dependencies", self._find_dependencies_node)
        graph.add_node("analyze_impact", self._analyze_impact_node)
        
        # Add edges
        graph.set_entry_point("parse_error")
        graph.add_edge("parse_error", "parse_file")
        graph.add_edge("parse_file", "find_dependencies")
        graph.add_edge("find_dependencies", "analyze_impact")
        graph.add_edge("analyze_impact", END)
        
        return graph
    
    async def run_analysis(self, error_text: str, workspace_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete error analysis workflow
        
        Args:
            error_text: The error message to analyze
            workspace_path: Optional workspace path for context
            
        Returns:
            JSON-formatted analysis results
        """
        workflow_id = str(uuid.uuid4())
        
        # Create initial state
        initial_state = create_initial_state(
            raw_error=error_text,
            workflow_id=workflow_id,
            config=self.config.to_dict()
        )
        
        # Set workspace path if provided
        if workspace_path:
            initial_state['config_snapshot']['workspace_path'] = workspace_path
        
        try:
            # Execute the workflow
            final_state = await self.compiled_graph.ainvoke(initial_state)
            
            # Update final metrics
            final_state['metrics'].completed_at = time.time()
            final_state['metrics'].total_execution_time_ms = int(
                (final_state['metrics'].completed_at - final_state['metrics'].started_at) * 1000
            )
            
            # Calculate cache hit rate
            total_cache_operations = final_state['cache_hits'] + final_state['cache_misses']
            if total_cache_operations > 0:
                final_state['metrics'].cache_hit_rate = final_state['cache_hits'] / total_cache_operations
            
            # Convert to JSON output
            return state_to_json_output(final_state)
            
        except Exception as e:
            # Handle workflow-level errors
            error_state = initial_state.copy()
            error_state['error'] = f"Workflow failed: {str(e)}"
            error_state['warnings'].append(f"Workflow exception: {traceback.format_exc()}")
            
            return state_to_json_output(error_state)
    
    async def _parse_error_node(self, state: AnalysisState) -> AnalysisState:
        """
        Node 1: Parse the error message and extract structured information
        """
        node_name = "parse_error"
        node_context = self.metrics_collector.record_node_start(node_name, state)
        retry_count = self._get_retry_count(state, node_name)
        
        try:
            # Check cache first
            cache_key = f"parse_error:{hash(state['raw_error'])}"
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                state['parsed_error'] = cached_result
                state['cache_hits'] += 1
                node_context['cache_hit'] = True
                print(123)
            else:
                print(state['raw_error'])
                # Parse the error
                parsed_error = self.error_parser.parse(state['raw_error'])
                print(parsed_error)
                
                # Sanitize sensitive information
                if parsed_error and hasattr(parsed_error, 'context') and parsed_error.context:
                    print(2342)
                    sanitized_context, redactions = self.security_manager.sanitize_content(parsed_error.context)
                    parsed_error.context = sanitized_context
                    
                    if redactions:
                        state['sensitive_data_detected'] = True
                        state['sanitized_content'].update(redactions)
                print(345)
                
                state['parsed_error'] = parsed_error
                state['cache_misses'] += 1
                print(456)
                
                # Cache the result
                await self.cache_manager.set(cache_key, parsed_error)
                state['cache_keys'].append(cache_key)
            
            # Record success metrics
            metrics = self.metrics_collector.record_node_end(node_context, state, True, retry_count)
            state['metrics'].node_metrics.append(metrics)
            self._reset_retry_count(state, node_name)
            
            return state
            
        except Exception as e:
            return await self._handle_node_error(
                state, node_name, str(e), node_context
            )
    
    async def _parse_file_node(self, state: AnalysisState) -> AnalysisState:
        """
        Node 2: Parse the target file and extract function context
        """
        node_name = "parse_file"
        node_context = self.metrics_collector.record_node_start(node_name, state)
        retry_count = self._get_retry_count(state, node_name)
        
        try:
            if not state['parsed_error']:
                raise ValueError("No parsed error information available")
            
            parsed_error = state['parsed_error']
            
            # Check if we have file and line information
            if not parsed_error.file_path or not parsed_error.line_number:
                state['warnings'].append("Insufficient file/line information for function analysis")
                return state
            
            # Check cache
            cache_key = f"parse_file:{parsed_error.file_path}:{parsed_error.line_number}"
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                state['target_function'] = cached_result
                state['cache_hits'] += 1
                node_context['cache_hit'] = True
            else:
                # Read the file
                try:
                    with open(parsed_error.file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                except FileNotFoundError:
                    raise ValueError(f"File not found: {parsed_error.file_path}")
                
                # Check memory usage
                memory_usage = self.security_manager.check_memory_usage()
                if memory_usage > self.config.security.max_memory_mb:
                    raise MemoryError(f"Memory usage {memory_usage}MB exceeds limit")
                
                # Sanitize file content
                sanitized_content, redactions = self.security_manager.sanitize_content(file_content)
                if redactions:
                    state['sensitive_data_detected'] = True
                    state['sanitized_content'].update(redactions)
                
                # Analyze function at target line
                if self.function_analyzer:
                    function_context = self.function_analyzer.analyze_function_at_line(
                        sanitized_content,
                        parsed_error.file_path,
                        parsed_error.line_number
                    )
                    
                    state['target_function'] = function_context
                    state['cache_misses'] += 1
                    
                    # Cache the result
                    await self.cache_manager.set(cache_key, function_context)
                    state['cache_keys'].append(cache_key)
                else:
                    raise ValueError("Function analyzer not initialized")
            
            # Record success metrics
            metrics = self.metrics_collector.record_node_end(node_context, state, True, retry_count)
            state['metrics'].node_metrics.append(metrics)
            self._reset_retry_count(state, node_name)
            
            return state
            
        except Exception as e:
            return await self._handle_node_error(
                state, node_name, str(e), node_context
            )
    
    async def _find_dependencies_node(self, state: AnalysisState) -> AnalysisState:
        """
        Node 3: Find file dependencies and import relationships
        """
        node_name = "find_dependencies"
        node_context = self.metrics_collector.record_node_start(node_name, state)
        retry_count = self._get_retry_count(state, node_name)
        
        try:
            if not state['parsed_error']:
                raise ValueError("No parsed error information available")
            
            parsed_error = state['parsed_error']
            
            if not parsed_error.file_path:
                state['warnings'].append("No file path available for dependency analysis")
                return state
            
            # Check cache
            cache_key = f"dependencies:{parsed_error.file_path}"
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                state['import_dependencies'] = cached_result['import_dependencies']
                state['dependent_files'] = cached_result['dependent_files']
                state['usage_contexts'] = cached_result['usage_contexts']
                state['cache_hits'] += 1
                node_context['cache_hit'] = True
            else:
                if not self.zoekt_manager:
                    raise ValueError("Zoekt manager not initialized")
                
                # Find file imports
                import_dependencies = await self.zoekt_manager.find_file_imports(parsed_error.file_path)
                
                # Extract dependent files
                dependent_files = [dep.file_path for dep in import_dependencies]
                
                # Find usage contexts (simplified for now)
                usage_contexts = []
                if state['target_function']:
                    usage_contexts = await self.zoekt_manager.find_function_usages(
                        state['target_function'].name,
                        parsed_error.file_path
                    )
                
                state['import_dependencies'] = import_dependencies
                state['dependent_files'] = dependent_files
                state['usage_contexts'] = usage_contexts
                state['cache_misses'] += 1
                
                # Cache the result
                cache_data = {
                    'import_dependencies': import_dependencies,
                    'dependent_files': dependent_files,
                    'usage_contexts': usage_contexts
                }
                await self.cache_manager.set(cache_key, cache_data)
                state['cache_keys'].append(cache_key)
            
            # Record success metrics
            metrics = self.metrics_collector.record_node_end(node_context, state, True, retry_count)
            state['metrics'].node_metrics.append(metrics)
            self._reset_retry_count(state, node_name)
            
            return state
            
        except Exception as e:
            return await self._handle_node_error(
                state, node_name, str(e), node_context
            )
    
    async def _analyze_impact_node(self, state: AnalysisState) -> AnalysisState:
        """
        Node 4: Analyze impact using LLM with few-shot examples
        """
        node_name = "analyze_impact"
        node_context = self.metrics_collector.record_node_start(node_name, state)
        retry_count = self._get_retry_count(state, node_name)
        
        try:
            # Prepare context for LLM
            context = self._prepare_llm_context(state)
            
            # Get few-shot examples
            language = None
            if state['target_function']:
                language = state['target_function'].language
            
            few_shot_prompt = self.few_shot_manager.create_few_shot_prompt(
                state['raw_error'],
                context,
                language
            )
            
            # Check cache
            context_hash = hash(json.dumps(context, sort_keys=True, default=str))
            cache_key = f"impact_analysis:{context_hash}"
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                state['impact_analysis'] = cached_result
                state['cache_hits'] += 1
                node_context['cache_hit'] = True
            else:
                # Format the prompt
                formatted_examples = self.few_shot_manager.format_examples_for_prompt(few_shot_prompt.examples)
                
                user_prompt = few_shot_prompt.user_prompt_template.format(
                    error_text=state['raw_error'],
                    context=json.dumps(context, indent=2, default=str)
                )
                
                full_prompt = f"{few_shot_prompt.system_prompt}\n\n{formatted_examples}\n\n{user_prompt}"
                
                # Call LLM if available, otherwise fallback immediately
                try:
                    if not self.ai_service:
                        raise RuntimeError("AI service unavailable")
                    
                    llm_response = await self.ai_service.chat(full_prompt)
                    
                    # Parse LLM response as JSON
                    try:
                        impact_data = json.loads(llm_response)
                        impact_analysis = ImpactAnalysis(**impact_data)
                    except (json.JSONDecodeError, TypeError):
                        # Fallback: create basic impact analysis
                        impact_analysis = ImpactAnalysis(
                            risk_level="medium",
                            affected_files=state['dependent_files'][:5],
                            fix_suggestions=[llm_response[:500]],
                            breaking_changes=[],
                            test_recommendations=["Add unit tests for the fixed function"],
                            confidence_score=0.6
                        )
                    
                    state['impact_analysis'] = impact_analysis
                    state['cache_misses'] += 1
                    
                    # Cache the result
                    await self.cache_manager.set(cache_key, impact_analysis)
                    state['cache_keys'].append(cache_key)
                    
                except Exception as llm_error:
                    # Fallback analysis without LLM
                    state['warnings'].append(f"LLM analysis failed: {str(llm_error)}")
                    impact_analysis = self._create_fallback_analysis(state)
                    state['impact_analysis'] = impact_analysis
            
            # Record success metrics
            metrics = self.metrics_collector.record_node_end(node_context, state, True, retry_count)
            state['metrics'].node_metrics.append(metrics)
            self._reset_retry_count(state, node_name)
            
            return state
            
        except Exception as e:
            return await self._handle_node_error(
                state, node_name, str(e), node_context
            )
    
    def _prepare_llm_context(self, state: AnalysisState) -> Dict[str, Any]:
        """Prepare context for LLM analysis"""
        context = {
            'error_info': {
                'type': state['parsed_error'].error_type if state['parsed_error'] else None,
                'file': state['parsed_error'].file_path if state['parsed_error'] else None,
                'line': state['parsed_error'].line_number if state['parsed_error'] else None,
                'message': state['raw_error']
            },
            'function_context': {
                'name': state['target_function'].name if state['target_function'] else None,
                'signature': state['target_function'].signature if state['target_function'] else None,
                'language': state['target_function'].language if state['target_function'] else None,
                'parameters': state['target_function'].parameters if state['target_function'] else None
            },
            'dependencies': {
                'dependent_files_count': len(state['dependent_files']),
                'dependent_files': state['dependent_files'][:10],  # Limit for context
                'usage_contexts_count': len(state['usage_contexts']),
                'import_types': list(set(dep.import_type for dep in state['import_dependencies']))
            },
            'workflow_context': {
                'workflow_id': state['workflow_id'],
                'sensitive_data_detected': state['sensitive_data_detected'],
                'warnings': state['warnings']
            }
        }
        
        return context
    
    def _create_fallback_analysis(self, state: AnalysisState) -> ImpactAnalysis:
        """Create fallback analysis when LLM fails"""
        # Simple heuristic-based analysis
        dependent_files = state['dependent_files']
        usage_count = len(state['usage_contexts'])
        
        # Determine risk level based on usage
        if usage_count > 10:
            risk_level = "high"
        elif usage_count > 3:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Basic fix suggestions
        fix_suggestions = []
        if state['parsed_error']:
            error_type = state['parsed_error'].error_type
            if "null" in error_type.lower():
                fix_suggestions.append("Add null checks before accessing object properties/methods")
            elif "undefined" in error_type.lower():
                fix_suggestions.append("Ensure variables are properly initialized before use")
            elif "type" in error_type.lower():
                fix_suggestions.append("Check data types and add appropriate type conversions")
        
        return ImpactAnalysis(
            risk_level=risk_level,
            affected_files=dependent_files[:5],
            fix_suggestions=fix_suggestions or ["Review the error context and implement appropriate fixes"],
            breaking_changes=[],
            test_recommendations=["Add unit tests to verify the fix"],
            confidence_score=0.5
        )

    def _get_retry_count(self, state: AnalysisState, node_name: str) -> int:
        """Return current retry count for a node."""
        retry_map = state.setdefault(self._retry_state_key, {})
        return retry_map.get(node_name, 0)

    def _increment_retry_count(self, state: AnalysisState, node_name: str) -> int:
        """Increment and return retry count for a node."""
        retry_map = state.setdefault(self._retry_state_key, {})
        retry_map[node_name] = retry_map.get(node_name, 0) + 1
        return retry_map[node_name]

    def _reset_retry_count(self, state: AnalysisState, node_name: str) -> None:
        """Clear retry count for a node after success or terminal failure."""
        retry_map = state.get(self._retry_state_key)
        if retry_map and node_name in retry_map:
            retry_map.pop(node_name, None)
    
    async def _handle_node_error(self, 
                                state: AnalysisState, 
                                node_name: str, 
                                error_message: str,
                                node_context: Dict[str, Any]) -> AnalysisState:
        """Handle node execution errors with retry logic"""
        
        current_retry = self._get_retry_count(state, node_name)
        
        # Check if we should retry
        if current_retry < self.config.max_retries_per_node:
            attempt_number = current_retry + 1
            state['warnings'].append(
                f"Node {node_name} failed (attempt {attempt_number}): {error_message}"
            )
            
            # Implement retry with exponential backoff
            wait_time = 2 ** current_retry
            await asyncio.sleep(wait_time)
            self._increment_retry_count(state, node_name)
            
            node_func = self._node_registry.get(node_name)
            if not node_func:
                raise ValueError(f"Unknown node '{node_name}' for retry")
            return await node_func(state)
        
        # Max retries reached or no retry configured
        state['error'] = (
            f"Node {node_name} failed after {current_retry + 1} attempts: {error_message}"
        )
        
        # Record failure metrics
        metrics = self.metrics_collector.record_node_end(node_context, state, False, current_retry)
        state['metrics'].node_metrics.append(metrics)
        self._reset_retry_count(state, node_name)
        
        return state
    
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics and configuration"""
        return {
            'config': self.config.to_dict(),
            'few_shot_stats': self.few_shot_manager.get_statistics(),
            'cache_stats': {
                'enabled': True,
                'ttl_seconds': self.config.performance.cache_ttl_seconds
            },
            'supported_languages': self.config.language.supported_languages,
            'security_features': {
                'sandboxing_enabled': self.config.security.enable_sandboxing,
                'max_memory_mb': self.config.security.max_memory_mb,
                'max_execution_time': self.config.security.max_execution_time_seconds
            }
        } 
