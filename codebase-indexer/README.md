# Modular Codebase Indexer Framework

A highly modular, plugin-based codebase indexing framework following **Deep Modules with Simple Interfaces** philosophy and **SOLID principles**.

## 🏗️ Architecture Philosophy

This framework is built on the following design principles:

### 1. **Deep Modules with Simple Interfaces** (John Ousterhout)
- **Simple Interfaces**: Each indexer exposes minimal, clean APIs (`index()`, `search()`)
- **Rich Implementation**: Complex logic is hidden inside modules
- **Information Hiding**: Internal implementation details are completely encapsulated

### 2. **Composition over Inheritance**
- Indexers are composed rather than inherited
- Flexible plugin system allows dynamic module combination
- Loose coupling between components

### 3. **SOLID Principles**
- **Single Responsibility**: Each indexer handles one specific indexing method
- **Open/Closed**: Extensible via plugins without modifying core
- **Liskov Substitution**: All indexers are interchangeable
- **Interface Segregation**: Small, focused interfaces (ISP compliant)
- **Dependency Inversion**: Depends on abstractions, not concrete implementations

### 4. **Event-Driven Architecture**
- Components communicate via events for maximum decoupling
- Scalable and extensible through pub/sub pattern
- Easy monitoring and debugging

## 🚀 Features

- **Plugin-Based Architecture**: Auto-discovery and dynamic loading of indexer plugins
- **Event-Driven Communication**: Loose coupling via event bus system
- **Configuration Management**: YAML/JSON configuration with validation
- **Health Monitoring**: Comprehensive health checks and statistics
- **CLI Interface**: Rich command-line interface with beautiful output
- **Parallel Processing**: Concurrent indexing and searching across multiple indexers
- **Type Safety**: Full type hints and Protocol-based interfaces

## 📦 Installation

### Prerequisites
- Python 3.9+
- Poetry (recommended) or pip

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd codebase-indexer

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Using pip

```bash
pip install -e .
```

## 🛠️ Quick Start

### 1. Initialize Configuration

```bash
# Create default configuration
indexer init

# Or specify custom paths
indexer init --config-path my_config.yaml --plugins-dir my_plugins
```

### 2. Start Framework

```bash
# Start with default configuration
indexer start

# Or specify configuration file
indexer start --config-path my_config.yaml
```

### 3. Index Content

```bash
# Index text content
indexer index "def hello(): return 'world'" --content-id "hello_function"

# Index from file
indexer index --file-path myfile.py

# Index with metadata
indexer index "print('hello')" --metadata '{"language": "python", "author": "dev"}'
```

### 4. Search Content

```bash
# Search across all indexers
indexer search "hello"

# Search with specific indexers
indexer search "function" --indexers "trigram_indexer"

# Limit results and format
indexer search "def" --limit 5 --format json
```

### 5. Manage Plugins

```bash
# List available plugins
indexer plugins

# Discover new plugins
indexer plugins --discover

# Check framework status
indexer status
```

## 🔧 Framework Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 MODULAR CODEBASE INDEXER FRAMEWORK                  │
├─────────────────────────────────────────────────────────────────────┤
│                           CORE LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  Event Bus      │  │ Plugin Registry │  │ Module Loader   │      │
│  │   System        │  │    Manager      │  │   Service       │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
├─────────────────────────────────────────────────────────────────────┤
│                        ABSTRACTION LAYER                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  Base Indexer   │  │ Search Provider │  │ Configuration   │      │
│  │   Interface     │  │   Interface     │  │   Interface     │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
├─────────────────────────────────────────────────────────────────────┤
│                         PLUGIN LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ Trigram Module  │  │ Vector Module   │  │  AST Module     │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ Symbol Module   │  │ Graph Module    │  │ Custom Module   │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **IndexerFramework**: Main orchestrator following Deep Modules principle
2. **EventBus**: Pub/sub communication system for loose coupling
3. **PluginRegistry**: Auto-discovery and lifecycle management of plugins
4. **ConfigManager**: Type-safe configuration with validation

## 🔌 Creating Custom Plugins

### Simple Indexer Plugin

```python
# plugins/my_indexer.py

class MyCustomIndexer:
    """Custom indexer following the framework interface"""
    
    # Plugin metadata
    __version__ = "1.0.0"
    __indexer_type__ = "custom"
    __supported_formats__ = ["text"]
    __requires_config__ = ["api_key"]  # Required config keys
    __dependencies__ = []  # Python package dependencies
    
    def __init__(self, config: dict, event_bus=None):
        self.config = config
        self.event_bus = event_bus
        # Initialize your indexer here
        
    async def initialize(self) -> bool:
        """Initialize the indexer"""
        # Perform any setup here
        return True
        
    async def shutdown(self) -> bool:
        """Cleanup resources"""
        # Cleanup here
        return True
        
    async def index(self, content: str, metadata: dict) -> bool:
        """Index content - REQUIRED METHOD"""
        # Your indexing logic here
        return True
        
    async def search(self, query: str, limit: int = 10) -> list:
        """Search content - REQUIRED METHOD"""
        # Your search logic here
        return []
        
    async def health_check(self) -> dict:
        """Return health status - OPTIONAL"""
        return {"status": "healthy"}
```

### Plugin Configuration

Add your plugin to the configuration file:

```yaml
indexers:
  - name: "my_custom_indexer"
    plugin_name: "my_indexer.MyCustomIndexer"
    enabled: true
    priority: 10
    settings:
      api_key: "your-api-key"
      custom_setting: "value"
    dependencies: []
```

## 📝 Configuration

The framework uses YAML configuration files. Here's the structure:

```yaml
plugins:
  plugins_dir: "plugins"           # Plugin discovery directory
  auto_discover: true              # Auto-discover plugins
  max_concurrent_indexers: 10      # Max parallel indexers

event_bus:
  max_queue_size: 1000            # Event queue size
  handler_timeout: 30.0           # Handler timeout in seconds

logging:
  level: "INFO"                   # Log level
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file_path: null                 # Optional log file

indexers:
  - name: "trigram_indexer"       # Unique indexer name
    plugin_name: "trigram.TrigramIndexer"  # Plugin class
    enabled: true                 # Enable/disable
    priority: 1                   # Execution priority
    settings:                     # Plugin-specific settings
      trigram_size: 3
      case_sensitive: false
    dependencies: []              # Required dependencies
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=indexer

# Run specific test
poetry run pytest tests/test_framework.py -v
```

### Example Test

```python
import asyncio
from indexer import IndexerFramework, FrameworkConfig

async def test_basic_functionality():
    # Create framework with default config
    framework = IndexerFramework()
    
    # Initialize
    await framework.initialize()
    
    # Index some content
    result = await framework.index_content(
        "def hello(): return 'world'",
        {"id": "test_function", "language": "python"}
    )
    
    # Search
    search_results = await framework.search("hello")
    
    # Cleanup
    await framework.shutdown()
    
    assert len(search_results.results) > 0

# Run test
asyncio.run(test_basic_functionality())
```

## 🔍 Available Indexers

### Trigram Indexer
- **Type**: Text-based similarity search
- **Use Case**: Fast substring and fuzzy matching
- **Configuration**:
  - `trigram_size`: Size of trigrams (default: 3)
  - `case_sensitive`: Case sensitivity (default: false)
  - `min_word_length`: Minimum word length (default: 2)

## 🎯 Use Cases

### Code Search Engines
```python
# Index your entire codebase
for file_path in codebase_files:
    with open(file_path) as f:
        content = f.read()
    await framework.index_content(content, {"file_path": file_path})

# Search for functions
results = await framework.search("def authenticate")
```

### Documentation Indexing
```python
# Index documentation
await framework.index_content(
    doc_content, 
    {"type": "documentation", "section": "api"}
)

# Search documentation
results = await framework.search("authentication guide")
```

### Multi-Modal Search
```python
# Combine multiple indexers for comprehensive search
results = await framework.search(
    "user authentication",
    indexer_names=["trigram_indexer", "ast_indexer", "vector_indexer"]
)
```

## 🚀 Performance

- **Parallel Indexing**: Multiple indexers work concurrently
- **Event-Driven**: Non-blocking communication
- **Memory Efficient**: Plugin-based loading
- **Scalable**: Horizontal scaling through multiple instances

## 🛣️ Roadmap

### Planned Indexers
- **AST Indexer**: Code structure and symbol indexing
- **Vector Indexer**: Semantic search using embeddings
- **Symbol Indexer**: Function/class/variable indexing
- **Graph Indexer**: Code relationship and dependency indexing

### Framework Enhancements
- REST API server
- Persistent storage backends
- Distributed indexing
- Real-time file watching
- Integration with popular editors

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the design principles
4. Add tests for new functionality
5. Submit a pull request

### Plugin Development Guidelines
- Follow the Interface Segregation Principle
- Keep interfaces minimal and focused
- Implement proper error handling
- Add comprehensive logging
- Include health check methods
- Document configuration options

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by John Ousterhout's "A Philosophy of Software Design"
- Built following SOLID principles and clean architecture patterns
- Event-driven architecture inspired by modern microservices patterns 