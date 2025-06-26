"""
Configuration management for the modular indexer framework.

Provides structured configuration with validation and type safety.
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import json
import yaml
import logging


class ConfigFormat(Enum):
    """Supported configuration file formats"""
    JSON = "json"
    YAML = "yaml"
    YML = "yml"


@dataclass
class IndexerConfig:
    """Configuration for individual indexer"""
    name: str
    plugin_name: str
    enabled: bool = True
    priority: int = 0
    settings: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.name:
            raise ValueError("Indexer name cannot be empty")
        if not self.plugin_name:
            raise ValueError("Plugin name cannot be empty")
        if self.priority < 0:
            raise ValueError("Priority must be non-negative")


@dataclass 
class EventBusConfig:
    """Configuration for event bus"""
    max_queue_size: int = 1000
    max_history: int = 1000
    handler_timeout: float = 30.0
    
    def __post_init__(self):
        if self.max_queue_size <= 0:
            raise ValueError("Queue size must be positive")
        if self.handler_timeout <= 0:
            raise ValueError("Handler timeout must be positive")


@dataclass
class PluginConfig:
    """Configuration for plugin system"""
    plugins_dir: str = "plugins"
    auto_discover: bool = True
    reload_on_change: bool = False
    max_concurrent_indexers: int = 10
    
    def __post_init__(self):
        if self.max_concurrent_indexers <= 0:
            raise ValueError("Max concurrent indexers must be positive")


@dataclass
class LoggingConfig:
    """Configuration for logging"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class FrameworkConfig:
    """Overall framework configuration"""
    plugins: PluginConfig = field(default_factory=PluginConfig)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    indexers: List[IndexerConfig] = field(default_factory=list)
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def get_indexer_config(self, name: str) -> Optional[IndexerConfig]:
        """Get configuration for specific indexer"""
        for indexer in self.indexers:
            if indexer.name == name:
                return indexer
        return None
    
    def add_indexer(self, indexer_config: IndexerConfig) -> None:
        """Add indexer configuration"""
        # Remove existing config with same name
        self.indexers = [idx for idx in self.indexers if idx.name != indexer_config.name]
        self.indexers.append(indexer_config)
    
    def remove_indexer(self, name: str) -> bool:
        """Remove indexer configuration"""
        original_count = len(self.indexers)
        self.indexers = [idx for idx in self.indexers if idx.name != name]
        return len(self.indexers) < original_count


class ConfigManager:
    """Configuration management with validation and file operations"""
    
    def __init__(self):
        self._config: Optional[FrameworkConfig] = None
        self.logger = logging.getLogger(__name__)
        
    def load_from_file(self, config_path: Union[str, Path]) -> FrameworkConfig:
        """Load configuration from file"""
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        self.logger.info(f"Loading configuration from: {path.absolute()}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                    
            config = self._parse_config(data)
            validation_errors = self.validate_config(config)
            
            if validation_errors:
                error_msg = "Configuration validation failed:\n" + "\n".join(validation_errors)
                raise ValueError(error_msg)
                
            self._config = config
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
            
    def save_to_file(
        self, 
        config: FrameworkConfig, 
        config_path: Union[str, Path], 
        format: ConfigFormat = ConfigFormat.YAML
    ) -> None:
        """Save configuration to file"""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self._config_to_dict(config)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                if format in [ConfigFormat.YAML, ConfigFormat.YML]:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
            self.logger.info(f"Configuration saved to: {path.absolute()}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
            
    def _parse_config(self, data: Dict[str, Any]) -> FrameworkConfig:
        """Parse configuration data into structured objects"""
        # Parse plugin configuration
        plugin_data = data.get('plugins', {})
        plugin_config = PluginConfig(**plugin_data)
        
        # Parse event bus configuration
        event_bus_data = data.get('event_bus', {})
        event_bus_config = EventBusConfig(**event_bus_data)
        
        # Parse logging configuration
        logging_data = data.get('logging', {})
        logging_config = LoggingConfig(**logging_data)
        
        # Parse indexer configurations
        indexer_configs = []
        for indexer_data in data.get('indexers', []):
            indexer_config = IndexerConfig(**indexer_data)
            indexer_configs.append(indexer_config)
            
        # Create framework config
        framework_config = FrameworkConfig(
            plugins=plugin_config,
            event_bus=event_bus_config,
            logging=logging_config,
            indexers=indexer_configs,
            custom_settings=data.get('custom_settings', {})
        )
        
        return framework_config
        
    def _config_to_dict(self, config: FrameworkConfig) -> Dict[str, Any]:
        """Convert configuration objects to dictionary"""
        return {
            'plugins': asdict(config.plugins),
            'event_bus': asdict(config.event_bus),
            'logging': asdict(config.logging),
            'indexers': [asdict(indexer) for indexer in config.indexers],
            'custom_settings': config.custom_settings
        }
        
    def validate_config(self, config: FrameworkConfig) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        try:
            # Validate plugins directory
            plugins_path = Path(config.plugins.plugins_dir)
            if not plugins_path.exists() and not config.plugins.auto_discover:
                errors.append(f"Plugins directory does not exist: {config.plugins.plugins_dir}")
                
            # Validate indexer configurations
            indexer_names = set()
            for indexer_config in config.indexers:
                # Check for duplicate names
                if indexer_config.name in indexer_names:
                    errors.append(f"Duplicate indexer name: {indexer_config.name}")
                indexer_names.add(indexer_config.name)
                
                # Validate dependencies
                for dep in indexer_config.dependencies:
                    if dep not in indexer_names and dep != indexer_config.name:
                        # Note: This is a simple check, proper dependency resolution
                        # would be done at runtime
                        pass
                        
            # Validate logging configuration
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if config.logging.level.upper() not in valid_log_levels:
                errors.append(f"Invalid log level: {config.logging.level}")
                
            if config.logging.file_path:
                log_path = Path(config.logging.file_path)
                try:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create log directory: {e}")
                    
        except Exception as e:
            errors.append(f"Configuration validation error: {e}")
            
        return errors
        
    def create_default_config(self) -> FrameworkConfig:
        """Create a default configuration"""
        default_config = FrameworkConfig(
            indexers=[
                IndexerConfig(
                    name="trigram_indexer",
                    plugin_name="trigram.TrigramIndexer",
                    enabled=True,
                    priority=1,
                    settings={
                        "trigram_size": 3,
                        "case_sensitive": False
                    }
                ),
                IndexerConfig(
                    name="ast_indexer", 
                    plugin_name="ast.ASTIndexer",
                    enabled=True,
                    priority=2,
                    settings={
                        "supported_languages": ["python", "javascript", "java"]
                    }
                )
            ]
        )
        return default_config
        
    def get_current_config(self) -> Optional[FrameworkConfig]:
        """Get currently loaded configuration"""
        return self._config
        
    def reload_config(self, config_path: Union[str, Path]) -> FrameworkConfig:
        """Reload configuration from file"""
        return self.load_from_file(config_path)
        
    def merge_config(self, base_config: FrameworkConfig, override_config: Dict[str, Any]) -> FrameworkConfig:
        """Merge override configuration into base configuration"""
        # Convert base config to dict
        base_dict = self._config_to_dict(base_config)
        
        # Deep merge override into base
        merged_dict = self._deep_merge(base_dict, override_config)
        
        # Parse back to structured config
        return self._parse_config(merged_dict)
        
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result 