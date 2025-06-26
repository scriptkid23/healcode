"""
Main framework orchestration for the modular codebase indexer.

This is the central orchestrator that coordinates all framework components
following the Deep Modules with Simple Interfaces philosophy.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import time

from .interfaces import (
    IIndexer, IEventBus, IPluginRegistry, IStateful, IHealthCheckable,
    IndexResult, SearchResult, EventType
)
from .event_bus import TypedEventBus
from .plugin_registry import PluginRegistry
from .config import FrameworkConfig, ConfigManager, IndexerConfig


class IndexerFramework(IStateful, IHealthCheckable):
    """
    Main framework class orchestrating all indexer components.
    
    Follows Deep Modules principle - simple interface with rich implementation.
    Provides the main entry point for all indexer operations.
    """
    
    def __init__(self, config: Optional[FrameworkConfig] = None):
        self.config = config or self._create_default_config()
        
        # Core components
        self.event_bus: IEventBus = TypedEventBus(
            max_queue_size=self.config.event_bus.max_queue_size
        )
        self.plugin_registry: IPluginRegistry = PluginRegistry(self.event_bus)
        self.config_manager = ConfigManager()
        
        # Runtime state
        self._active_indexers: Dict[str, IIndexer] = {}
        self._initialized = False
        self._startup_time: Optional[float] = None
        
        # Logging setup
        self.logger = self._setup_logging()
        
        # Statistics
        self._stats = {
            'total_indexed': 0,
            'total_searches': 0,
            'indexer_count': 0,
            'plugin_count': 0
        }
        
    async def initialize(self) -> bool:
        """Initialize the framework and all components"""
        if self._initialized:
            self.logger.warning("Framework already initialized")
            return True
            
        start_time = time.time()
        self.logger.info("Initializing Modular Codebase Indexer Framework")
        
        try:
            # Start event bus
            await self.event_bus.start()
            
            # Register event handlers
            await self._register_event_handlers()
            
            # Discover and load plugins
            await self._load_plugins()
            
            # Initialize configured indexers
            await self._initialize_indexers()
            
            self._startup_time = time.time() - start_time
            self._initialized = True
            
            self.logger.info(
                f"Framework initialized successfully in {self._startup_time:.2f}s"
            )
            
            # Publish initialization event
            await self.event_bus.publish(EventType.INDEXER_CREATED.value, {
                "framework_initialized": True,
                "startup_time": self._startup_time,
                "indexer_count": len(self._active_indexers),
                "plugin_count": len(self.plugin_registry.get_available_plugins())
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Framework initialization failed: {e}")
            await self.shutdown()
            return False
            
    async def shutdown(self) -> bool:
        """Shutdown framework and cleanup resources"""
        if not self._initialized:
            return True
            
        self.logger.info("Shutting down framework")
        
        try:
            # Shutdown active indexers
            for name, indexer in self._active_indexers.items():
                if hasattr(indexer, 'shutdown'):
                    try:
                        await indexer.shutdown()
                    except Exception as e:
                        self.logger.error(f"Error shutting down indexer {name}: {e}")
                        
            self._active_indexers.clear()
            
            # Stop event bus
            await self.event_bus.stop()
            
            self._initialized = False
            self.logger.info("Framework shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
            
    async def index_content(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        indexer_names: Optional[List[str]] = None
    ) -> Dict[str, IndexResult]:
        """
        Index content using specified or all active indexers.
        
        Simple interface hiding complex orchestration logic (Deep Module principle).
        """
        if not self._initialized:
            raise RuntimeError("Framework not initialized")
            
        # Determine which indexers to use
        target_indexers = self._get_target_indexers(indexer_names)
        
        if not target_indexers:
            raise ValueError("No active indexers available")
            
        self.logger.debug(f"Indexing content with {len(target_indexers)} indexers")
        
        # Execute indexing in parallel
        results = {}
        tasks = []
        
        for name, indexer in target_indexers.items():
            task = asyncio.create_task(
                self._safe_index(name, indexer, content, metadata)
            )
            tasks.append((name, task))
            
        # Wait for all indexing operations
        for name, task in tasks:
            try:
                result = await task
                results[name] = result
            except Exception as e:
                self.logger.error(f"Indexing failed for {name}: {e}")
                results[name] = IndexResult(
                    success=False,
                    content_id="",
                    message=str(e),
                    metadata={}
                )
                
        # Update statistics
        self._stats['total_indexed'] += sum(1 for r in results.values() if r.success)
        
        # Publish indexing event
        await self.event_bus.publish(EventType.CONTENT_INDEXED.value, {
            "content_length": len(content),
            "indexer_count": len(target_indexers),
            "success_count": sum(1 for r in results.values() if r.success),
            "metadata": metadata
        })
        
        return results
        
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        indexer_names: Optional[List[str]] = None,
        merge_results: bool = True
    ) -> Union[SearchResult, Dict[str, SearchResult]]:
        """
        Search across specified or all active indexers.
        
        Returns merged results by default, or per-indexer results if merge_results=False.
        """
        if not self._initialized:
            raise RuntimeError("Framework not initialized")
            
        target_indexers = self._get_target_indexers(indexer_names)
        
        if not target_indexers:
            raise ValueError("No active indexers available")
            
        start_time = time.time()
        self.logger.debug(f"Searching '{query}' with {len(target_indexers)} indexers")
        
        # Execute searches in parallel
        search_results = {}
        tasks = []
        
        for name, indexer in target_indexers.items():
            task = asyncio.create_task(
                self._safe_search(name, indexer, query, limit)
            )
            tasks.append((name, task))
            
        # Wait for all search operations
        for name, task in tasks:
            try:
                results = await task
                search_results[name] = SearchResult(
                    query=query,
                    results=results,
                    total_count=len(results),
                    execution_time=0,  # Individual timing would need modification
                    metadata={"indexer": name}
                )
            except Exception as e:
                self.logger.error(f"Search failed for {name}: {e}")
                search_results[name] = SearchResult(
                    query=query,
                    results=[],
                    total_count=0,
                    execution_time=0,
                    metadata={"indexer": name, "error": str(e)}
                )
                
        execution_time = time.time() - start_time
        
        # Update statistics
        self._stats['total_searches'] += 1
        
        # Publish search event
        await self.event_bus.publish(EventType.SEARCH_PERFORMED.value, {
            "query": query,
            "indexer_count": len(target_indexers),
            "execution_time": execution_time,
            "total_results": sum(r.total_count for r in search_results.values())
        })
        
        if merge_results:
            return self._merge_search_results(search_results, query, execution_time)
        else:
            return search_results
            
    async def add_indexer(self, indexer_config: IndexerConfig) -> bool:
        """Add and initialize a new indexer at runtime"""
        if not self._initialized:
            raise RuntimeError("Framework not initialized")
            
        try:
            # Create indexer instance
            indexer = await self.plugin_registry.create_indexer(
                indexer_config.plugin_name, 
                indexer_config.settings
            )
            
            if indexer:
                self._active_indexers[indexer_config.name] = indexer
                self._stats['indexer_count'] = len(self._active_indexers)
                
                self.logger.info(f"Added indexer: {indexer_config.name}")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to add indexer {indexer_config.name}: {e}")
            return False
            
    async def remove_indexer(self, name: str) -> bool:
        """Remove an active indexer"""
        if name not in self._active_indexers:
            return False
            
        try:
            indexer = self._active_indexers[name]
            
            # Shutdown indexer if possible
            if hasattr(indexer, 'shutdown'):
                await indexer.shutdown()
                
            del self._active_indexers[name]
            self._stats['indexer_count'] = len(self._active_indexers)
            
            self.logger.info(f"Removed indexer: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove indexer {name}: {e}")
            return False
            
    async def health_check(self) -> Dict[str, Any]:
        """Return comprehensive health status"""
        health = {
            "status": "healthy" if self._initialized else "unhealthy",
            "initialized": self._initialized,
            "startup_time": self._startup_time,
            "uptime": time.time() - (self._startup_time or 0) if self._startup_time else 0,
            "components": {},
            "statistics": self._stats.copy(),
            "active_indexers": list(self._active_indexers.keys()),
            "available_plugins": len(self.plugin_registry.get_available_plugins())
        }
        
        # Check component health
        try:
            # Event bus health
            health["components"]["event_bus"] = {
                "status": "healthy",
                "subscriber_count": self.event_bus.get_subscriber_count()
            }
            
            # Plugin registry health
            health["components"]["plugin_registry"] = {
                "status": "healthy",
                "plugin_count": len(self.plugin_registry.get_available_plugins()),
                "active_indexer_count": len(self.plugin_registry.get_active_indexers())
            }
            
            # Individual indexer health
            indexer_health = {}
            for name, indexer in self._active_indexers.items():
                if hasattr(indexer, 'health_check'):
                    try:
                        indexer_health[name] = await indexer.health_check()
                    except Exception as e:
                        indexer_health[name] = {"status": "unhealthy", "error": str(e)}
                else:
                    indexer_health[name] = {"status": "unknown"}
                    
            health["components"]["indexers"] = indexer_health
            
        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)
            
        return health
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get framework statistics"""
        return {
            **self._stats.copy(),
            "uptime": time.time() - (self._startup_time or 0) if self._startup_time else 0,
            "initialized": self._initialized
        }
        
    # Private methods
    
    def _create_default_config(self) -> FrameworkConfig:
        """Create default configuration"""
        config_manager = ConfigManager()
        return config_manager.create_default_config()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("indexer.framework")
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.config.logging.level.upper()),
            format=self.config.logging.format
        )
        
        # Add file handler if specified
        if self.config.logging.file_path:
            file_handler = logging.FileHandler(self.config.logging.file_path)
            file_handler.setFormatter(logging.Formatter(self.config.logging.format))
            logger.addHandler(file_handler)
            
        return logger
        
    async def _register_event_handlers(self) -> None:
        """Register framework event handlers"""
        await self.event_bus.subscribe(
            EventType.ERROR_OCCURRED.value, 
            self._handle_error_event
        )
        
    async def _handle_error_event(self, event: Dict[str, Any]) -> None:
        """Handle error events"""
        error_data = event.get('data', {})
        self.logger.error(f"Framework error: {error_data}")
        
    async def _load_plugins(self) -> None:
        """Discover and load plugins"""
        discovered = await self.plugin_registry.discover_plugins(
            self.config.plugins.plugins_dir
        )
        self._stats['plugin_count'] = len(discovered)
        self.logger.info(f"Loaded {len(discovered)} plugins")
        
    async def _initialize_indexers(self) -> None:
        """Initialize configured indexers"""
        for indexer_config in self.config.indexers:
            if indexer_config.enabled:
                try:
                    indexer = await self.plugin_registry.create_indexer(
                        indexer_config.plugin_name,
                        indexer_config.settings
                    )
                    
                    if indexer:
                        self._active_indexers[indexer_config.name] = indexer
                        self.logger.info(f"Initialized indexer: {indexer_config.name}")
                    else:
                        self.logger.error(f"Failed to create indexer: {indexer_config.name}")
                        
                except Exception as e:
                    self.logger.error(
                        f"Error initializing indexer {indexer_config.name}: {e}"
                    )
                    
        self._stats['indexer_count'] = len(self._active_indexers)
        
    def _get_target_indexers(self, indexer_names: Optional[List[str]]) -> Dict[str, IIndexer]:
        """Get target indexers for operation"""
        if indexer_names:
            return {
                name: indexer for name, indexer in self._active_indexers.items()
                if name in indexer_names
            }
        return self._active_indexers.copy()
        
    async def _safe_index(
        self, 
        name: str, 
        indexer: IIndexer, 
        content: str, 
        metadata: Dict[str, Any]
    ) -> IndexResult:
        """Safely execute indexing with error handling"""
        try:
            success = await indexer.index(content, metadata)
            return IndexResult(
                success=success,
                content_id=metadata.get('id', ''),
                message="Success" if success else "Failed",
                metadata={"indexer": name}
            )
        except Exception as e:
            return IndexResult(
                success=False,
                content_id=metadata.get('id', ''),
                message=str(e),
                metadata={"indexer": name, "error": True}
            )
            
    async def _safe_search(
        self, 
        name: str, 
        indexer: IIndexer, 
        query: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Safely execute search with error handling"""
        try:
            return await indexer.search(query, limit)
        except Exception as e:
            self.logger.error(f"Search error in {name}: {e}")
            return []
            
    def _merge_search_results(
        self, 
        search_results: Dict[str, SearchResult], 
        query: str, 
        execution_time: float
    ) -> SearchResult:
        """Merge results from multiple indexers"""
        all_results = []
        total_count = 0
        
        for indexer_name, result in search_results.items():
            # Add indexer source to each result
            for item in result.results:
                item['_source_indexer'] = indexer_name
                all_results.append(item)
            total_count += result.total_count
            
        # Simple relevance-based sorting (can be enhanced)
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return SearchResult(
            query=query,
            results=all_results,
            total_count=total_count,
            execution_time=execution_time,
            metadata={
                "merged_from": list(search_results.keys()),
                "individual_counts": {
                    name: result.total_count 
                    for name, result in search_results.items()
                }
            }
        ) 