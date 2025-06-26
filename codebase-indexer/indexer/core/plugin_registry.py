"""
Plugin Registry for managing indexer modules.

Implements auto-discovery and lifecycle management of indexer plugins
following Dependency Inversion Principle and Open/Closed Principle.
"""

from typing import Dict, List, Type, Optional, Any
from pathlib import Path
import importlib.util
import inspect
import logging
import asyncio
from .interfaces import IPluginRegistry, IIndexer, IEventBus, EventType
from .event_bus import EventBus


class PluginMetadata:
    """Metadata for a plugin"""
    
    def __init__(self, plugin_class: Type):
        self.name = plugin_class.__name__
        self.module = plugin_class.__module__
        self.docstring = plugin_class.__doc__ or ''
        self.version = getattr(plugin_class, '__version__', '1.0.0')
        self.dependencies = getattr(plugin_class, '__dependencies__', [])
        self.indexer_type = getattr(plugin_class, '__indexer_type__', 'custom')
        self.supported_formats = getattr(plugin_class, '__supported_formats__', ['*'])
        self.requires_config = getattr(plugin_class, '__requires_config__', [])


class PluginRegistry(IPluginRegistry):
    """Plugin registry for managing indexer modules"""
    
    def __init__(self, event_bus: IEventBus):
        self.event_bus = event_bus
        self._plugins: Dict[str, Type] = {}
        self._active_indexers: Dict[str, Any] = {}
        self._plugin_metadata: Dict[str, PluginMetadata] = {}
        self.logger = logging.getLogger(__name__)
        
    async def discover_plugins(self, plugins_dir: str = "plugins") -> List[str]:
        """Auto-discover plugins using introspection"""
        discovered = []
        plugins_path = Path(plugins_dir)
        
        # Create plugins directory if it doesn't exist
        if not plugins_path.exists():
            plugins_path.mkdir(parents=True)
            self.logger.info(f"Created plugins directory: {plugins_dir}")
            return discovered
            
        self.logger.info(f"Discovering plugins in: {plugins_path.absolute()}")
        
        # Scan for plugin files
        for plugin_file in plugins_path.rglob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
                
            try:
                discovered_classes = await self._load_plugin_file(plugin_file)
                discovered.extend(discovered_classes)
                
            except Exception as e:
                self.logger.error(f"Failed to load plugin {plugin_file}: {e}")
                
        await self.event_bus.publish(EventType.PLUGIN_LOADED.value, {
            "count": len(discovered),
            "plugins": discovered
        })
        
        self.logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
        
    async def _load_plugin_file(self, plugin_file: Path) -> List[str]:
        """Load a single plugin file and extract indexer classes"""
        discovered_classes = []
        
        # Dynamic import
        spec = importlib.util.spec_from_file_location(
            plugin_file.stem, plugin_file
        )
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load spec for {plugin_file}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find classes implementing IIndexer
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if self._is_valid_indexer(obj) and obj.__module__ == module.__name__:
                plugin_name = f"{plugin_file.stem}.{name}"
                if self.register_plugin(plugin_name, obj):
                    discovered_classes.append(plugin_name)
                    self.logger.debug(f"Loaded plugin class: {plugin_name}")
                    
        return discovered_classes
        
    def register_plugin(self, plugin_name: str, plugin_class: Type) -> bool:
        """Register plugin class"""
        try:
            if not self._is_valid_indexer(plugin_class):
                raise ValueError(f"Invalid indexer class: {plugin_class}")
                
            self._plugins[plugin_name] = plugin_class
            
            # Extract and store metadata
            metadata = PluginMetadata(plugin_class)
            self._plugin_metadata[plugin_name] = metadata
            
            self.logger.info(f"Registered plugin: {plugin_name} v{metadata.version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register plugin {plugin_name}: {e}")
            return False
            
    def _is_valid_indexer(self, cls: Type) -> bool:
        """Check if class implements required indexer interface"""
        # Check if class has required methods using duck typing
        required_methods = ['index', 'search']
        has_methods = all(
            hasattr(cls, method) and callable(getattr(cls, method)) 
            for method in required_methods
        )
        
        # Check if it's not an abstract class
        is_concrete = not inspect.isabstract(cls)
        
        return has_methods and is_concrete
        
    async def create_indexer(self, plugin_name: str, config: Dict) -> Optional[Any]:
        """Create indexer instance from plugin"""
        if plugin_name not in self._plugins:
            self.logger.error(f"Plugin not found: {plugin_name}")
            return None
            
        try:
            plugin_class = self._plugins[plugin_name]
            metadata = self._plugin_metadata[plugin_name]
            
            # Validate required configuration
            if not self._validate_config_requirements(metadata, config):
                self.logger.error(f"Configuration validation failed for {plugin_name}")
                return None
            
            # Create instance with dependency injection
            instance = await self._create_instance(plugin_class, config)
            
            if instance:
                # Store active instance
                instance_id = id(instance)
                self._active_indexers[f"{plugin_name}_{instance_id}"] = instance
                
                await self.event_bus.publish(EventType.INDEXER_CREATED.value, {
                    "plugin_name": plugin_name,
                    "instance_id": instance_id,
                    "metadata": metadata.__dict__
                })
                
                self.logger.info(f"Created indexer instance: {plugin_name}")
                
            return instance
            
        except Exception as e:
            self.logger.error(f"Failed to create indexer {plugin_name}: {e}")
            await self.event_bus.publish(EventType.ERROR_OCCURRED.value, {
                "error": str(e),
                "context": f"create_indexer:{plugin_name}"
            })
            return None
            
    async def _create_instance(self, plugin_class: Type, config: Dict) -> Optional[Any]:
        """Create plugin instance with proper dependency injection"""
        try:
            # Check constructor signature for dependency injection
            sig = inspect.signature(plugin_class.__init__)
            params = sig.parameters
            
            # Prepare constructor arguments
            kwargs = {}
            
            # Inject standard dependencies
            if 'config' in params:
                kwargs['config'] = config
            if 'event_bus' in params:
                kwargs['event_bus'] = self.event_bus
                
            # Create instance
            instance = plugin_class(**kwargs)
            
            # Initialize if the instance has an initialize method
            if hasattr(instance, 'initialize') and callable(instance.initialize):
                init_result = instance.initialize()
                if asyncio.iscoroutine(init_result):
                    await init_result
                    
            return instance
            
        except Exception as e:
            self.logger.error(f"Failed to instantiate {plugin_class.__name__}: {e}")
            return None
            
    def _validate_config_requirements(self, metadata: PluginMetadata, config: Dict) -> bool:
        """Validate that required configuration is provided"""
        for required_key in metadata.requires_config:
            if required_key not in config:
                self.logger.error(
                    f"Missing required configuration key '{required_key}' "
                    f"for plugin {metadata.name}"
                )
                return False
        return True
        
    def get_available_plugins(self) -> Dict[str, Dict]:
        """Get list of available plugins with metadata"""
        return {
            name: {
                'name': metadata.name,
                'version': metadata.version,
                'docstring': metadata.docstring,
                'indexer_type': metadata.indexer_type,
                'supported_formats': metadata.supported_formats,
                'dependencies': metadata.dependencies,
                'requires_config': metadata.requires_config
            }
            for name, metadata in self._plugin_metadata.items()
        }
        
    def get_active_indexers(self) -> Dict[str, Any]:
        """Get currently active indexer instances"""
        return self._active_indexers.copy()
        
    async def destroy_indexer(self, instance_key: str) -> bool:
        """Destroy an active indexer instance"""
        if instance_key not in self._active_indexers:
            return False
            
        try:
            instance = self._active_indexers[instance_key]
            
            # Call cleanup if available
            if hasattr(instance, 'shutdown') and callable(instance.shutdown):
                shutdown_result = instance.shutdown()
                if asyncio.iscoroutine(shutdown_result):
                    await shutdown_result
                    
            # Remove from active instances
            del self._active_indexers[instance_key]
            
            await self.event_bus.publish(EventType.INDEXER_DESTROYED.value, {
                "instance_key": instance_key,
                "instance_id": id(instance)
            })
            
            self.logger.info(f"Destroyed indexer instance: {instance_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to destroy indexer {instance_key}: {e}")
            return False
            
    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (useful for development)"""
        if plugin_name not in self._plugins:
            return False
            
        try:
            # Remove existing plugin
            del self._plugins[plugin_name]
            del self._plugin_metadata[plugin_name]
            
            # Destroy any active instances of this plugin
            to_destroy = [
                key for key in self._active_indexers.keys() 
                if key.startswith(plugin_name)
            ]
            for key in to_destroy:
                await self.destroy_indexer(key)
                
            self.logger.info(f"Reloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            return False 