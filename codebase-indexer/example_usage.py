#!/usr/bin/env python3
"""
Example usage of the Modular Codebase Indexer Framework.

This script demonstrates the key features and philosophy of the framework:
- Deep Modules with Simple Interfaces
- Plugin-based architecture
- Event-driven communication
- SOLID principles in action
"""

import asyncio
import logging
from pathlib import Path

# Import the framework components
from indexer.core.framework import IndexerFramework
from indexer.core.config import ConfigManager

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Demonstrate the modular indexer framework.
    
    This example shows how the Deep Modules principle provides a simple
    interface that hides complex implementation details.
    """
    
    print("🚀 Modular Codebase Indexer Framework Demo")
    print("=" * 50)
    
    # 1. Load configuration (demonstrates configuration management)
    print("\n📋 Loading Configuration...")
    config_manager = ConfigManager()
    
    try:
        # Try to load existing config, create default if not found
        if Path("indexer_config.yaml").exists():
            config = config_manager.load_from_file("indexer_config.yaml")
            print("✅ Loaded configuration from indexer_config.yaml")
        else:
            config = config_manager.create_default_config()
            print("✅ Created default configuration")
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        return
    
    # 2. Initialize framework (demonstrates Deep Module principle)
    print("\n🏗️  Initializing Framework...")
    framework = IndexerFramework(config)
    
    try:
        success = await framework.initialize()
        if not success:
            print("❌ Framework initialization failed")
            return
        print("✅ Framework initialized successfully")
        
        # Show framework status
        health = await framework.health_check()
        print(f"📊 Status: {health['status']}")
        print(f"🔌 Active Indexers: {len(health['active_indexers'])}")
        print(f"📦 Available Plugins: {health['available_plugins']}")
        
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return
    
    # 3. Index sample content (demonstrates simple interface)
    print("\n📝 Indexing Sample Content...")
    
    sample_contents = [
        {
            "content": "def authenticate_user(username, password):\n    return verify_credentials(username, password)",
            "metadata": {"id": "auth_function", "type": "function", "language": "python"}
        },
        {
            "content": "class UserManager:\n    def __init__(self):\n        self.users = {}",
            "metadata": {"id": "user_class", "type": "class", "language": "python"}
        },
        {
            "content": "// Function to validate email format\nfunction validateEmail(email) {\n    return /\\S+@\\S+\\.\\S+/.test(email);\n}",
            "metadata": {"id": "email_validator", "type": "function", "language": "javascript"}
        },
        {
            "content": "CREATE TABLE users (id INT PRIMARY KEY, username VARCHAR(50), email VARCHAR(100));",
            "metadata": {"id": "users_table", "type": "schema", "language": "sql"}
        }
    ]
    
    for i, item in enumerate(sample_contents, 1):
        try:
            # Simple interface hiding complex indexing logic
            results = await framework.index_content(
                item["content"], 
                item["metadata"]
            )
            
            success_count = sum(1 for r in results.values() if r.success)
            print(f"✅ Content {i}: {success_count}/{len(results)} indexers succeeded")
            
        except Exception as e:
            print(f"❌ Content {i}: Indexing failed - {e}")
    
    # 4. Demonstrate search capabilities (demonstrates composition)
    print("\n🔍 Searching Content...")
    
    search_queries = [
        "authenticate",
        "user",
        "email",
        "function",
        "class"
    ]
    
    for query in search_queries:
        try:
            # Simple search interface hiding complex orchestration
            results = await framework.search(query, limit=3)
            
            print(f"\n🔎 Query: '{query}'")
            print(f"📊 Found {results.total_count} results in {results.execution_time:.3f}s")
            
            for result in results.results[:2]:  # Show top 2
                content_preview = result['content'][:60] + "..." if len(result['content']) > 60 else result['content']
                print(f"   📄 {result['id']}: {content_preview}")
                print(f"      Score: {result['score']:.3f} | Source: {result.get('_source_indexer', 'unknown')}")
                
        except Exception as e:
            print(f"❌ Search '{query}' failed: {e}")
    
    # 5. Show statistics (demonstrates monitoring capabilities)
    print("\n📈 Framework Statistics...")
    stats = framework.get_statistics()
    for key, value in stats.items():
        print(f"   {key.replace('_', ' ').title()}: {value}")
    
    # 6. Demonstrate plugin system (demonstrates extensibility)
    print("\n🔌 Plugin Information...")
    plugins = framework.plugin_registry.get_available_plugins()
    for name, info in plugins.items():
        print(f"   📦 {name}")
        print(f"      Version: {info['version']}")
        print(f"      Type: {info['indexer_type']}")
        print(f"      Formats: {', '.join(info['supported_formats'])}")
    
    # 7. Health check (demonstrates monitoring)
    print("\n🏥 Health Check...")
    health = await framework.health_check()
    
    print(f"   Overall Status: {health['status']}")
    print(f"   Uptime: {health['uptime']:.2f} seconds")
    
    # Component health
    for component, status in health['components'].items():
        if isinstance(status, dict):
            component_status = status.get('status', 'unknown')
            print(f"   {component.title()}: {component_status}")
    
    # 8. Cleanup (demonstrates proper resource management)
    print("\n🧹 Shutting Down...")
    try:
        await framework.shutdown()
        print("✅ Framework shutdown complete")
    except Exception as e:
        print(f"❌ Shutdown error: {e}")
    
    print("\n🎉 Demo Complete!")
    print("\nKey Architectural Principles Demonstrated:")
    print("• Deep Modules: Simple interface (index/search) with rich implementation")
    print("• Composition: Multiple indexers working together")
    print("• Event-Driven: Loose coupling via event bus")
    print("• SOLID: Single responsibility, open/closed, interface segregation")
    print("• Plugin System: Extensible without modifying core")


def run_advanced_example():
    """
    Run advanced example showing event handling and custom operations.
    """
    
    async def event_listener(event):
        """Example event listener showing event-driven architecture"""
        event_type = event.get('type')
        data = event.get('data', {})
        
        if event_type == 'content_indexed':
            print(f"🎉 Content indexed: {data.get('content_id')} ({data.get('content_length')} chars)")
        elif event_type == 'search_performed':
            print(f"🔍 Search performed: '{data.get('query')}' ({data.get('result_count')} results)")
    
    async def advanced_demo():
        print("\n🚀 Advanced Framework Demo - Event Handling")
        print("=" * 50)
        
        # Create framework
        framework = IndexerFramework()
        await framework.initialize()
        
        # Subscribe to events (demonstrates event-driven architecture)
        await framework.event_bus.subscribe('content_indexed', event_listener)
        await framework.event_bus.subscribe('search_performed', event_listener)
        
        # Index content (will trigger events)
        await framework.index_content(
            "async def process_data(data):\n    return await transform(data)",
            {"id": "async_function", "language": "python"}
        )
        
        # Search (will trigger events)
        await framework.search("async")
        
        # Give events time to process
        await asyncio.sleep(0.1)
        
        await framework.shutdown()
        print("✅ Advanced demo complete")
    
    return asyncio.run(advanced_demo())


if __name__ == "__main__":
    # Run the main demo
    asyncio.run(main())
    
    # Uncomment to run advanced demo
    # run_advanced_example() 