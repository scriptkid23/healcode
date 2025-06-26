"""
Core interfaces for the modular codebase indexer framework.

Following Interface Segregation Principle (ISP) and using Protocol
for structural typing (Duck Typing) to maintain flexibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncGenerator, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum
import asyncio


# Event System Interfaces
class IEventBus(ABC):
    """Central event bus for module communication"""
    
    @abstractmethod
    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event to the bus"""
        pass
    
    @abstractmethod
    async def subscribe(self, event_type: str, handler: callable) -> str:
        """Subscribe to events of specific type"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        pass


# Plugin Registry Interface
class IPluginRegistry(ABC):
    """Plugin registry for managing indexer modules"""
    
    @abstractmethod
    def register_plugin(self, plugin_name: str, plugin_class: type) -> bool:
        """Register a new indexer plugin"""
        pass
    
    @abstractmethod
    async def discover_plugins(self) -> List[str]:
        """Auto-discover available plugins"""
        pass
    
    @abstractmethod
    async def create_indexer(self, plugin_name: str, config: Dict) -> Optional['IIndexer']:
        """Create indexer instance from plugin"""
        pass


# Configuration Interfaces - ISP Compliant
class IConfigurable(ABC):
    """Interface for configurable components"""
    
    @abstractmethod
    def load_config(self, config: Dict[str, Any]) -> bool:
        """Load configuration"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        pass


class IStateful(ABC):
    """Interface for stateful components"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize component state"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup component state"""
        pass


class IHealthCheckable(ABC):
    """Interface for health monitoring"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return health status"""
        pass


# Primary Indexer Interfaces using Protocol for structural typing
@runtime_checkable
class IIndexer(Protocol):
    """Primary indexer interface - kept minimal (Deep Module principle)"""
    
    async def index(self, content: str, metadata: Dict[str, Any]) -> bool:
        """Index content with metadata"""
        ...
    
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search indexed content"""
        ...


@runtime_checkable  
class IBatchIndexer(Protocol):
    """Interface for batch operations"""
    
    async def index_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch index multiple items"""
        ...


@runtime_checkable
class IStreamIndexer(Protocol):
    """Interface for streaming operations"""
    
    async def index_stream(self, content_stream: AsyncGenerator) -> AsyncGenerator:
        """Stream-based indexing"""
        ...


@runtime_checkable
class IUpdateable(Protocol):
    """Interface for updateable indexes"""
    
    async def update(self, content_id: str, content: str) -> bool:
        """Update existing indexed content"""
        ...
    
    async def remove(self, content_id: str) -> bool:
        """Remove content from index"""
        ...


# Search Provider Interface
@runtime_checkable
class ISearchProvider(Protocol):
    """Interface for search providers"""
    
    async def query(self, query_text: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute search query"""
        ...
    
    async def suggest(self, partial_query: str) -> List[str]:
        """Provide query suggestions"""
        ...


# Result Types
@dataclass
class IndexResult:
    """Result of indexing operation"""
    success: bool
    content_id: str
    message: str
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    """Search operation result"""
    query: str
    results: List[Dict[str, Any]]
    total_count: int
    execution_time: float
    metadata: Dict[str, Any]


class IndexerType(Enum):
    """Types of indexers available"""
    TRIGRAM = "trigram"
    VECTOR = "vector"
    AST = "ast"
    SYMBOL = "symbol"
    GRAPH = "graph"
    CUSTOM = "custom"


class EventType(Enum):
    """Event types for the event bus"""
    INDEXER_CREATED = "indexer_created"
    INDEXER_DESTROYED = "indexer_destroyed"
    CONTENT_INDEXED = "content_indexed"
    SEARCH_PERFORMED = "search_performed"
    PLUGIN_LOADED = "plugin_loaded"
    ERROR_OCCURRED = "error_occurred" 