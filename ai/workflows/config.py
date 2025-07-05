"""
Configuration system for LangGraph Error Analysis Workflow

Provides comprehensive configuration for security, performance, and language support.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import os

@dataclass
class SecurityConfig:
    """Security configuration for code analysis"""
    enable_sandboxing: bool = True
    max_memory_mb: int = 512  # Maximum memory for AST parsing
    max_execution_time_seconds: int = 300  # 5 minutes max workflow time
    sensitive_patterns: List[str] = field(default_factory=lambda: [
        r'password\s*=\s*["\'].*["\']',
        r'api_key\s*=\s*["\'].*["\']',
        r'secret\s*=\s*["\'].*["\']',
        r'token\s*=\s*["\'].*["\']',
        r'private_key\s*=\s*["\'].*["\']'
    ])
    redaction_placeholder: str = "[REDACTED]"
    
@dataclass
class PerformanceConfig:
    """Performance configuration for workflow optimization"""
    max_ast_file_size_mb: int = 10  # Skip AST parsing for files larger than this
    max_concurrent_nodes: int = 3
    cache_ttl_seconds: int = 3600  # 1 hour
    desired_cache_hit_rate: float = 0.8  # 80% cache hit rate target
    max_dependency_depth: int = 3  # Maximum depth for dependency analysis
    max_files_per_search: int = 50

@dataclass
class LanguageConfig:
    """Language-specific configuration"""
    supported_languages: List[str] = field(default_factory=lambda: [
        'python', 'java', 'javascript', 'typescript', 'rust'
    ])
    tree_sitter_parsers: Dict[str, str] = field(default_factory=lambda: {
        'java': 'tree-sitter-java',
        'javascript': 'tree-sitter-javascript', 
        'typescript': 'tree-sitter-typescript',
        'rust': 'tree-sitter-rust'
    })
    ast_languages: List[str] = field(default_factory=lambda: ['python'])
    fallback_to_regex: bool = True

@dataclass
class MetricsConfig:
    """Metrics and monitoring configuration"""
    enable_metrics: bool = True
    metrics_export_interval_seconds: int = 60
    track_node_performance: bool = True
    track_cache_performance: bool = True
    track_memory_usage: bool = True
    export_to_prometheus: bool = False
    metrics_retention_days: int = 7

@dataclass
class WorkflowConfig:
    """Main configuration for Error Analysis Workflow"""
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    
    # LLM Configuration
    primary_model: str = "google_gemini"
    model_temperature: float = 0.1  # Low temperature for consistent results
    max_tokens: int = 2048
    
    # Retry Configuration
    max_retries_per_node: int = 2
    enable_llm_fallback: bool = True
    enable_simple_fallback: bool = True
    
    # Few-shot Examples
    enable_few_shot: bool = True
    few_shot_examples_path: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'WorkflowConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Security settings
        sandboxing_env = os.getenv("WORKFLOW_ENABLE_SANDBOXING")
        if sandboxing_env:
            config.security.enable_sandboxing = sandboxing_env.lower() == "true"
        
        memory_env = os.getenv("WORKFLOW_MAX_MEMORY_MB")
        if memory_env:
            config.security.max_memory_mb = int(memory_env)
        
        execution_time_env = os.getenv("WORKFLOW_MAX_EXECUTION_TIME")
        if execution_time_env:
            config.security.max_execution_time_seconds = int(execution_time_env)
            
        # Performance settings
        cache_ttl_env = os.getenv("WORKFLOW_CACHE_TTL")
        if cache_ttl_env:
            config.performance.cache_ttl_seconds = int(cache_ttl_env)
        
        cache_hit_rate_env = os.getenv("WORKFLOW_DESIRED_CACHE_HIT_RATE")
        if cache_hit_rate_env:
            config.performance.desired_cache_hit_rate = float(cache_hit_rate_env)
            
        # LLM settings
        primary_model_env = os.getenv("WORKFLOW_PRIMARY_MODEL")
        if primary_model_env:
            config.primary_model = primary_model_env
        
        model_temp_env = os.getenv("WORKFLOW_MODEL_TEMPERATURE")
        if model_temp_env:
            config.model_temperature = float(model_temp_env)
            
        return config
    
    @classmethod
    def from_file(cls, config_path: str) -> 'WorkflowConfig':
        """Load configuration from YAML file"""
        import yaml
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        # Convert nested dict to dataclass instances
        security_config = SecurityConfig(**config_data.get('security', {}))
        performance_config = PerformanceConfig(**config_data.get('performance', {}))
        language_config = LanguageConfig(**config_data.get('language', {}))
        metrics_config = MetricsConfig(**config_data.get('metrics', {}))
        
        return cls(
            security=security_config,
            performance=performance_config,
            language=language_config,
            metrics=metrics_config,
            **{k: v for k, v in config_data.items() 
               if k not in ['security', 'performance', 'language', 'metrics']}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'security': self.security.__dict__,
            'performance': self.performance.__dict__,
            'language': self.language.__dict__,
            'metrics': self.metrics.__dict__,
            'primary_model': self.primary_model,
            'model_temperature': self.model_temperature,
            'max_tokens': self.max_tokens,
            'max_retries_per_node': self.max_retries_per_node,
            'enable_llm_fallback': self.enable_llm_fallback,
            'enable_simple_fallback': self.enable_simple_fallback,
            'enable_few_shot': self.enable_few_shot,
            'few_shot_examples_path': self.few_shot_examples_path
        }
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if self.security.max_memory_mb < 64:
            issues.append("Security: max_memory_mb should be at least 64MB")
            
        if self.security.max_execution_time_seconds < 30:
            issues.append("Security: max_execution_time_seconds should be at least 30 seconds")
            
        if self.performance.desired_cache_hit_rate < 0 or self.performance.desired_cache_hit_rate > 1:
            issues.append("Performance: desired_cache_hit_rate must be between 0 and 1")
            
        if self.model_temperature < 0 or self.model_temperature > 1:
            issues.append("LLM: model_temperature must be between 0 and 1")
            
        if self.max_tokens < 512:
            issues.append("LLM: max_tokens should be at least 512")
            
        # Validate supported languages
        valid_languages = {'python', 'java', 'javascript', 'typescript', 'rust', 'c', 'cpp', 'go'}
        for lang in self.language.supported_languages:
            if lang not in valid_languages:
                issues.append(f"Language: '{lang}' is not a supported language")
                
        return issues 