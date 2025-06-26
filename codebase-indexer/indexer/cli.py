"""
Command Line Interface for the Modular Codebase Indexer Framework.

Provides easy-to-use commands for indexing and searching codebases.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
import logging

from .core.framework import IndexerFramework
from .core.config import ConfigManager, FrameworkConfig, IndexerConfig

app = typer.Typer(
    name="indexer",
    help="Modular Codebase Indexer Framework",
    add_completion=False
)
console = Console()


@app.command()
def init(
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path"),
    plugins_dir: str = typer.Option("plugins", help="Plugins directory"),
    force: bool = typer.Option(False, help="Overwrite existing configuration")
):
    """Initialize a new indexer configuration."""
    
    config_file = Path(config_path)
    
    if config_file.exists() and not force:
        console.print(f"[red]Configuration file already exists: {config_path}[/red]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    try:
        # Create default configuration
        config_manager = ConfigManager()
        config = config_manager.create_default_config()
        config.plugins.plugins_dir = plugins_dir
        
        # Save configuration
        config_manager.save_to_file(config, config_path)
        
        console.print(f"[green]✓[/green] Created configuration file: {config_path}")
        console.print(f"[green]✓[/green] Plugins directory: {plugins_dir}")
        
        # Create plugins directory
        Path(plugins_dir).mkdir(parents=True, exist_ok=True)
        
        # Show configuration summary
        _show_config_summary(config)
        
    except Exception as e:
        console.print(f"[red]Failed to initialize configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def start(
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path"),
    daemon: bool = typer.Option(False, help="Run as daemon")
):
    """Start the indexer framework."""
    
    async def _start_framework():
        try:
            # Load configuration
            config_manager = ConfigManager()
            
            if not Path(config_path).exists():
                console.print(f"[red]Configuration file not found: {config_path}[/red]")
                console.print("Run 'indexer init' to create a configuration file")
                return False
                
            config = config_manager.load_from_file(config_path)
            
            # Create and initialize framework
            framework = IndexerFramework(config)
            
            console.print("[blue]Starting Modular Codebase Indexer Framework...[/blue]")
            
            success = await framework.initialize()
            if not success:
                console.print("[red]Failed to initialize framework[/red]")
                return False
                
            # Show startup information
            health = await framework.health_check()
            _show_framework_status(health)
            
            if not daemon:
                console.print("\n[green]Framework started successfully![/green]")
                console.print("Press Ctrl+C to stop...")
                
                try:
                    # Keep running until interrupted
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Shutting down...[/yellow]")
                    
            await framework.shutdown()
            return True
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
    
    success = asyncio.run(_start_framework())
    if not success:
        raise typer.Exit(1)


@app.command()
def index(
    content: str = typer.Argument(..., help="Content to index"),
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path"),
    metadata: Optional[str] = typer.Option(None, help="JSON metadata for the content"),
    content_id: Optional[str] = typer.Option(None, help="Unique ID for the content"),
    file_path: Optional[str] = typer.Option(None, help="Index content from file")
):
    """Index content using the configured indexers."""
    
    async def _index_content():
        try:
            # Load configuration and create framework
            config_manager = ConfigManager()
            config = config_manager.load_from_file(config_path)
            framework = IndexerFramework(config)
            
            # Initialize framework
            await framework.initialize()
            
            # Prepare content and metadata
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content_to_index = f.read()
                content_id = content_id or file_path
            else:
                content_to_index = content
                content_id = content_id or "cli_content"
                
            metadata_dict = {"id": content_id}
            if metadata:
                metadata_dict.update(json.loads(metadata))
                
            # Index content
            console.print(f"[blue]Indexing content (ID: {content_id})...[/blue]")
            
            results = await framework.index_content(content_to_index, metadata_dict)
            
            # Show results
            _show_index_results(results)
            
            await framework.shutdown()
            return True
            
        except Exception as e:
            console.print(f"[red]Indexing failed: {e}[/red]")
            return False
    
    success = asyncio.run(_index_content())
    if not success:
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path"),
    limit: int = typer.Option(10, help="Maximum number of results"),
    indexers: Optional[str] = typer.Option(None, help="Comma-separated list of indexers to use"),
    format: str = typer.Option("table", help="Output format: table, json"),
    merge: bool = typer.Option(True, help="Merge results from multiple indexers")
):
    """Search indexed content."""
    
    async def _search_content():
        try:
            # Load configuration and create framework
            config_manager = ConfigManager()
            config = config_manager.load_from_file(config_path)
            framework = IndexerFramework(config)
            
            # Initialize framework
            await framework.initialize()
            
            # Parse indexer list
            indexer_list = None
            if indexers:
                indexer_list = [name.strip() for name in indexers.split(',')]
                
            # Search
            console.print(f"[blue]Searching for: '{query}'...[/blue]")
            
            results = await framework.search(
                query, 
                limit=limit, 
                indexer_names=indexer_list,
                merge_results=merge
            )
            
            # Show results
            if format == "json":
                if hasattr(results, '__dict__'):
                    # Single SearchResult object
                    print(json.dumps(results.__dict__, indent=2, default=str))
                else:
                    # Dictionary of results
                    print(json.dumps(results, indent=2, default=str))
            else:
                _show_search_results(results, query)
                
            await framework.shutdown()
            return True
            
        except Exception as e:
            console.print(f"[red]Search failed: {e}[/red]")
            return False
    
    success = asyncio.run(_search_content())
    if not success:
        raise typer.Exit(1)


@app.command()
def plugins(
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path"),
    discover: bool = typer.Option(False, help="Discover new plugins")
):
    """List available plugins."""
    
    async def _list_plugins():
        try:
            config_manager = ConfigManager()
            config = config_manager.load_from_file(config_path)
            framework = IndexerFramework(config)
            
            await framework.initialize()
            
            if discover:
                console.print("[blue]Discovering plugins...[/blue]")
                discovered = await framework.plugin_registry.discover_plugins()
                console.print(f"[green]Discovered {len(discovered)} plugins[/green]")
            
            plugins = framework.plugin_registry.get_available_plugins()
            _show_plugins_table(plugins)
            
            await framework.shutdown()
            return True
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
    
    success = asyncio.run(_list_plugins())
    if not success:
        raise typer.Exit(1)


@app.command()
def status(
    config_path: str = typer.Option("indexer_config.yaml", help="Configuration file path")
):
    """Show framework status and health."""
    
    async def _show_status():
        try:
            config_manager = ConfigManager()
            config = config_manager.load_from_file(config_path)
            framework = IndexerFramework(config)
            
            await framework.initialize()
            
            health = await framework.health_check()
            _show_framework_status(health)
            
            stats = framework.get_statistics()
            _show_statistics(stats)
            
            await framework.shutdown()
            return True
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
    
    success = asyncio.run(_show_status())
    if not success:
        raise typer.Exit(1)


# Helper functions for display

def _show_config_summary(config: FrameworkConfig):
    """Show configuration summary."""
    table = Table(title="Configuration Summary")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Plugins Directory", config.plugins.plugins_dir)
    table.add_row("Auto Discover", str(config.plugins.auto_discover))
    table.add_row("Max Concurrent", str(config.plugins.max_concurrent_indexers))
    table.add_row("Event Queue Size", str(config.event_bus.max_queue_size))
    table.add_row("Log Level", config.logging.level)
    table.add_row("Configured Indexers", str(len(config.indexers)))
    
    console.print(table)


def _show_framework_status(health: dict):
    """Show framework health status."""
    status_color = "green" if health["status"] == "healthy" else "red"
    
    panel = Panel(
        f"Status: [{status_color}]{health['status'].upper()}[/{status_color}]\n"
        f"Initialized: {health['initialized']}\n"
        f"Uptime: {health.get('uptime', 0):.2f}s\n"
        f"Active Indexers: {len(health.get('active_indexers', []))}\n"
        f"Available Plugins: {health.get('available_plugins', 0)}",
        title="Framework Status",
        border_style=status_color
    )
    console.print(panel)


def _show_statistics(stats: dict):
    """Show framework statistics."""
    table = Table(title="Framework Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    for key, value in stats.items():
        table.add_row(key.replace('_', ' ').title(), str(value))
    
    console.print(table)


def _show_plugins_table(plugins: dict):
    """Show available plugins in a table."""
    table = Table(title="Available Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Formats", style="green")
    table.add_column("Description", style="white")
    
    for name, info in plugins.items():
        description = info.get('docstring', '').split('\n')[0][:50]
        if len(description) == 50:
            description += "..."
            
        table.add_row(
            name,
            info.get('version', 'Unknown'),
            info.get('indexer_type', 'custom'),
            ', '.join(info.get('supported_formats', [])),
            description
        )
    
    console.print(table)


def _show_index_results(results: dict):
    """Show indexing results."""
    table = Table(title="Indexing Results")
    table.add_column("Indexer", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Message", style="white")
    
    for indexer_name, result in results.items():
        status_color = "green" if result.success else "red"
        status_text = f"[{status_color}]{'SUCCESS' if result.success else 'FAILED'}[/{status_color}]"
        
        table.add_row(
            indexer_name,
            status_text,
            result.message
        )
    
    console.print(table)


def _show_search_results(results, query: str):
    """Show search results."""
    if hasattr(results, 'results'):
        # Single SearchResult object
        search_results = results.results
        total_count = results.total_count
        execution_time = results.execution_time
    else:
        # Dictionary of SearchResult objects
        search_results = []
        total_count = 0
        execution_time = 0
        
        for indexer_name, result in results.items():
            for item in result.results:
                item['_indexer'] = indexer_name
                search_results.append(item)
            total_count += result.total_count
            execution_time = max(execution_time, result.execution_time)
    
    if not search_results:
        console.print(f"[yellow]No results found for: '{query}'[/yellow]")
        return
    
    console.print(f"[green]Found {total_count} results in {execution_time:.2f}s[/green]\n")
    
    table = Table(title=f"Search Results for: '{query}'")
    table.add_column("Score", style="yellow", width=8)
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Content", style="white", width=60)
    table.add_column("Source", style="green", width=15)
    
    for result in search_results[:10]:  # Show top 10
        content_preview = result.get('content', '')[:100]
        if len(content_preview) == 100:
            content_preview += "..."
            
        table.add_row(
            f"{result.get('score', 0):.3f}",
            result.get('id', 'Unknown'),
            content_preview,
            result.get('_source_indexer', result.get('_indexer', 'Unknown'))
        )
    
    console.print(table)


if __name__ == "__main__":
    app() 