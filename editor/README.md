# HealCode Editor Module

A comprehensive file editing system with concurrent access, backup management, and multiple editing strategies for safe code modifications.

## Features

- **Multiple Editing Strategies**: Line-specific, pattern-based (regex), and AST-based editing
- **Concurrent Access Control**: Thread-safe operations with file locking using `portalocker`
- **Automatic Backups**: Create and manage backups with rollback capabilities
- **Memory Efficient**: Uses `in_place` library for large files with `fileinput` fallback
- **Diff Generation**: Track changes with unified diff format
- **Operation Tracking**: Monitor active operations and operation history
- **Async Support**: Fully asynchronous API with timeout handling
- **Validation**: File path, size, and syntax validation
- **Extensible**: Plugin-based architecture for adding new editing strategies

## Installation

### Required Dependencies

```bash
pip install in-place portalocker
```

### Optional Dependencies (for enhanced functionality)

```bash
pip install astor  # Better AST code generation
pip install aiofiles  # Async file operations
```

## Quick Start

```python
import asyncio
from editor import EditorService, EditorConfig

async def main():
    # Initialize editor service
    config = EditorConfig(
        backup_enabled=True,
        backup_directory="./backups"
    )
    editor = EditorService(config)
    
    # Edit a specific line
    result = await editor.edit_line(
        file_path="example.py",
        line_number=5,
        new_content="    print('Hello, HealCode!')"
    )
    
    if result.success:
        print(f"Edit successful! Operation ID: {result.operation_id}")
        print(f"Lines changed: {result.lines_changed}")
    else:
        print(f"Edit failed: {result.error}")

asyncio.run(main())
```

## Editing Strategies

### 1. Line Editor
Edit specific lines or ranges of lines.

```python
# Edit single line
result = await editor.edit_line("file.py", 10, "new content")

# Edit range of lines  
result = await editor.edit_range("file.py", 5, 8, "replacement\ncontent\nhere")
```

### 2. Pattern Editor
Use regex patterns for find-and-replace operations.

```python
# Replace function names
result = await editor.edit_pattern(
    "file.py", 
    r"def old_function\(",
    "def new_function("
)

# Search patterns before editing
matches = await pattern_editor.search_pattern("file.py", r"class\s+(\w+)")
```

### 3. AST Editor
Syntax-aware editing for Python code.

```python
# Rename function using AST
ast_config = {
    "type": "rename_function",
    "parameters": {
        "old_name": "old_func",
        "new_name": "new_func"
    }
}

result = await editor.edit_file(EditRequest(
    file_path="file.py",
    operation_type=EditOperationType.AST,
    target=str(ast_config),
    content=""
))
```

## Configuration

```python
from editor import EditorConfig

config = EditorConfig(
    # Backup settings
    backup_enabled=True,
    backup_directory="./backups",
    backup_retention_days=7,
    max_backup_size_mb=100,
    
    # Concurrency settings
    max_concurrent_operations=10,
    lock_timeout_seconds=30,
    operation_timeout_seconds=60,
    
    # File restrictions
    allowed_extensions=['.py', '.js', '.ts', '.json', '.yaml', '.yml'],
    max_file_size_mb=50,
    allowed_base_paths=["/safe/directory"],
    
    # Validation
    validate_syntax=True
)
```

## API Reference

### EditorService

#### Core Methods

```python
async def edit_file(request: EditRequest) -> EditResult
async def edit_line(file_path: str, line_number: int, new_content: str, options: EditOptions = None) -> EditResult
async def edit_range(file_path: str, start_line: int, end_line: int, new_content: str, options: EditOptions = None) -> EditResult
async def edit_pattern(file_path: str, pattern: str, replacement: str, options: EditOptions = None) -> EditResult
async def rollback(rollback_request: RollbackRequest) -> RollbackResult
```

#### Monitoring Methods

```python
async def get_operation_status(operation_id: str) -> Optional[Dict[str, Any]]
async def list_active_operations() -> List[Dict[str, Any]]
async def cleanup_old_backups()
```

### Data Models

#### EditRequest
```python
@dataclass
class EditRequest:
    file_path: str
    operation_type: EditOperationType
    target: Union[int, range, str]  # line number, range, or pattern
    content: str
    options: EditOptions = field(default_factory=EditOptions)
```

#### EditResult
```python
@dataclass
class EditResult:
    success: bool
    operation_id: str
    file_path: str
    operation_type: EditOperationType
    diff: Optional[str] = None
    backup_path: Optional[str] = None
    lines_changed: int = 0
    bytes_changed: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### EditOptions
```python
@dataclass
class EditOptions:
    create_backup: bool = True
    validate_syntax: bool = True
    encoding: str = "utf-8"
    timeout_seconds: int = 30
    preserve_permissions: bool = True
    atomic_operation: bool = True
```

## Advanced Usage

### Rollback Operations

```python
from editor.interfaces import RollbackRequest

# Rollback a previous operation
rollback_request = RollbackRequest(operation_id="some-operation-id")
result = await editor.rollback(rollback_request)

if result.success:
    print(f"Rollback successful: {result.restored_from_backup}")
```

### Custom AST Transformations

```python
# Add import statement
ast_config = {
    "type": "add_import",
    "parameters": {
        "module": "numpy",
        "alias": "np"
    }
}

# Add decorator to function
ast_config = {
    "type": "add_decorator", 
    "parameters": {
        "target_name": "my_function",
        "decorator": "staticmethod"
    }
}
```

### Batch Operations

```python
# Process multiple files concurrently
tasks = []
for file_path in file_list:
    task = editor.edit_pattern(file_path, "old_pattern", "new_pattern")
    tasks.append(task)

results = await asyncio.gather(*tasks)
```

### Operation Monitoring

```python
# Start a long-running operation
result = await editor.edit_file(large_file_request)

# Monitor operation status
status = await editor.get_operation_status(result.operation_id)
print(f"Operation status: {status['status']}")
print(f"Duration: {status['duration_seconds']}s")

# List all active operations
active_ops = await editor.list_active_operations()
for op in active_ops:
    print(f"Active: {op['operation_id']} - {op['operation_type']}")
```

## Error Handling

The editor module provides specific exception types for different error conditions:

```python
from editor.interfaces import (
    EditorException,
    FileNotFoundException,
    FilePermissionException,
    FileLockedException,
    ValidationException,
    BackupException,
    SyntaxValidationException
)

try:
    result = await editor.edit_file(request)
except FileNotFoundException:
    print("File not found")
except FileLockedException:
    print("File is locked by another process")
except ValidationException as e:
    print(f"Validation error: {e}")
except BackupException as e:
    print(f"Backup error: {e}")
```

## Security Considerations

1. **Path Validation**: Prevents directory traversal attacks
2. **File Permission Checks**: Verifies read/write permissions
3. **Size Limits**: Prevents excessive memory usage
4. **Extension Whitelist**: Only allows editing of specific file types
5. **Base Path Restrictions**: Limits editing to allowed directories
6. **Operation Logging**: Tracks all operations for audit purposes

## Performance

- **Memory Efficient**: Uses streaming for large files
- **Concurrent Safe**: Thread-safe with file locking
- **Async Operations**: Non-blocking I/O operations
- **Caching**: Pattern compilation caching for regex operations
- **Timeout Handling**: Prevents hanging operations

## Testing

Run the example script to test functionality:

```bash
python -m editor.example_usage
```

## Integration with HealCode System

The editor module integrates with the broader HealCode system:

```python
# In orchestrator service
async def process_code_improvement(self, request):
    # 1. Search code with INDEX service
    search_results = await self.index_service.search(request.query)
    
    # 2. Get AI improvements
    improvements = await self.ai_service.improve_code(search_results)
    
    # 3. Apply improvements with EDITOR service
    edit_results = []
    for improvement in improvements:
        result = await self.editor_service.edit_file(improvement.edit_request)
        edit_results.append(result)
    
    # 4. Create PR with PR service
    pr_result = await self.pr_service.create_pull_request(edit_results)
    
    return pr_result
```

## Contributing

To add a new editing strategy:

1. Implement the `EditorInterface`
2. Add the strategy to `EditorService.strategies`
3. Add appropriate tests
4. Update documentation

Example:

```python
class MyCustomEditor(EditorInterface):
    def supports_operation(self, operation_type: EditOperationType) -> bool:
        return operation_type == EditOperationType.CUSTOM
    
    async def validate_request(self, request: EditRequest) -> bool:
        # Validation logic
        return True
    
    async def edit(self, request: EditRequest) -> EditResult:
        # Implementation
        pass
```

## License

This module is part of the HealCode project. 