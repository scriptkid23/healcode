# 📝 Editor Module - Tài Liệu Chi Tiết

**Editor Module** là hệ thống chỉnh sửa file an toàn với concurrent access, backup management và nhiều editing strategies.

---

## 🎯 MỤC ĐÍCH

Editor Module giải quyết bài toán: **"Làm sao edit code an toàn trong production?"**

### ✅ Các Tính Năng Chính

1. **Multiple Editing Strategies** - 4 cách edit khác nhau:
   - Line Editor: Edit specific lines
   - Pattern Editor: Find & replace với regex
   - AST Editor: Syntax-aware editing
   - Range Editor: Edit nhiều dòng liên tiếp

2. **Concurrent Access Control** - Thread-safe với file locking

3. **Automatic Backups** - Tự động backup & rollback

4. **Memory Efficient** - Xử lý file lớn hiệu quả

5. **Async Support** - API async hoàn toàn

---

## 🚀 QUICK START

### Cài Đặt

```bash
pip install in-place portalocker
pip install astor aiofiles  # Optional
```

### Sử Dụng Cơ Bản

```python
import asyncio
from editor import EditorService, EditorConfig, EditOptions

async def main():
    # 1. Initialize editor
    config = EditorConfig(
        backup_enabled=True,
        backup_directory="./backups"
    )
    editor = EditorService(config)
    
    # 2. Edit một dòng
    result = await editor.edit_line(
        file_path="example.py",
        line_number=5,
        new_content="    print('Hello, World!')"
    )
    
    # 3. Kiểm tra kết quả
    if result.success:
        print(f"✅ Success! Operation ID: {result.operation_id}")
        print(f"Lines changed: {result.lines_changed}")
        print(f"Backup created at: {result.backup_path}")
    else:
        print(f"❌ Failed: {result.error}")

asyncio.run(main())
```

---

## 📖 4 EDITING STRATEGIES

### 1️⃣ LINE EDITOR - Edit Specific Lines

**Use case**: Sửa một hoặc nhiều dòng cụ thể

```python
# Edit single line
result = await editor.edit_line(
    file_path="app.py",
    line_number=10,
    new_content="def new_function():"
)

# Edit multiple lines
result = await editor.edit_lines(
    file_path="app.py",
    line_numbers=[5, 10, 15],
    new_contents=[
        "# Line 5 new content",
        "# Line 10 new content",
        "# Line 15 new content"
    ]
)
```

**Features**:
- ✅ Edit by line number (1-indexed)
- ✅ Batch edit nhiều dòng
- ✅ Preserve file encoding
- ✅ Validate line numbers

---

### 2️⃣ RANGE EDITOR - Edit Line Ranges

**Use case**: Thay thế nhiều dòng liên tiếp

```python
# Replace lines 5-10
result = await editor.edit_range(
    file_path="app.py",
    start_line=5,
    end_line=10,
    new_content="""def refactored_function():
    # New implementation
    pass
"""
)
```

**Features**:
- ✅ Replace range of lines
- ✅ Insert multi-line content
- ✅ Automatic indentation handling

---

### 3️⃣ PATTERN EDITOR - Regex Find & Replace

**Use case**: Find & replace với patterns

```python
# Replace function names
result = await editor.edit_pattern(
    file_path="app.py",
    pattern=r"def old_function\(",
    replacement="def new_function("
)

# Replace with regex groups
result = await editor.edit_pattern(
    file_path="app.py",
    pattern=r"print\((.*)\)",
    replacement=r"logger.info(\1)"
)

# Search before editing
from editor.strategies import PatternEditor
pattern_editor = PatternEditor()
matches = await pattern_editor.search_pattern(
    "app.py",
    r"class\s+(\w+)"
)
print(f"Found {len(matches)} classes")
```

**Features**:
- ✅ Regex pattern matching
- ✅ Capture groups support
- ✅ Case-sensitive/insensitive
- ✅ Preview matches before edit
- ✅ Pattern compilation caching

---

### 4️⃣ AST EDITOR - Syntax-Aware Editing

**Use case**: Python code refactoring

```python
import json
from editor import EditRequest, EditOperationType

# Rename function using AST
ast_config = {
    "type": "rename_function",
    "parameters": {
        "old_name": "calculate_total",
        "new_name": "compute_sum"
    }
}

result = await editor.edit_file(EditRequest(
    file_path="app.py",
    operation_type=EditOperationType.AST,
    target=json.dumps(ast_config),
    content=""
))

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

# Rename class
ast_config = {
    "type": "rename_class",
    "parameters": {
        "old_name": "OldClass",
        "new_name": "NewClass"
    }
}
```

**Supported AST Operations**:
- ✅ Rename functions/classes/variables
- ✅ Add/remove imports
- ✅ Add/remove decorators
- ✅ Modify function signatures
- ✅ Safe refactoring (preserves syntax)

---

## ⚙️ CONFIGURATION

### EditorConfig - Tất Cả Settings

```python
from editor import EditorConfig

config = EditorConfig(
    # 💾 BACKUP SETTINGS
    backup_enabled=True,              # Enable auto-backup
    backup_directory="./backups",     # Backup location
    backup_retention_days=7,          # Keep backups for 7 days
    max_backup_size_mb=100,           # Max backup size
    
    # 🔒 CONCURRENCY SETTINGS
    max_concurrent_operations=10,     # Max parallel edits
    lock_timeout_seconds=30,          # File lock timeout
    operation_timeout_seconds=60,     # Operation timeout
    
    # 📁 FILE RESTRICTIONS
    allowed_extensions=[              # Allowed file types
        '.py', '.js', '.ts', '.json',
        '.yaml', '.yml', '.txt', '.md'
    ],
    max_file_size_mb=50,              # Max file size
    allowed_base_paths=[              # Restrict to directories
        "/safe/directory",
        "/another/safe/path"
    ],
    
    # ✅ VALIDATION
    validate_syntax=True               # Validate Python syntax after edit
)

editor = EditorService(config)
```

---

## 📊 EDIT OPTIONS

### Per-Operation Options

```python
from editor import EditOptions

options = EditOptions(
    create_backup=True,          # Create backup for this operation
    validate_syntax=True,        # Validate syntax after edit
    encoding="utf-8",            # File encoding
    timeout_seconds=30,          # Operation timeout
    preserve_permissions=True,   # Keep file permissions
    atomic_operation=True        # Use atomic file operations
)

result = await editor.edit_line(
    file_path="app.py",
    line_number=10,
    new_content="new content",
    options=options
)
```

---

## 🔄 BACKUP & ROLLBACK

### Automatic Backup

```python
# Edit với backup enabled
result = await editor.edit_line(
    file_path="app.py",
    line_number=10,
    new_content="new content",
    options=EditOptions(create_backup=True)
)

print(f"Backup created at: {result.backup_path}")
print(f"Operation ID: {result.operation_id}")
```

### Rollback Operation

```python
from editor.interfaces import RollbackRequest

# Rollback by operation ID
rollback_request = RollbackRequest(
    operation_id="abc-123-def-456",
    force=False  # Set True to force even if file modified
)

result = await editor.rollback(rollback_request)

if result.success:
    print(f"✅ Rollback successful!")
    print(f"Restored from: {result.restored_from_backup}")
else:
    print(f"❌ Rollback failed: {result.error}")
```

### Cleanup Old Backups

```python
# Automatically cleanup backups older than retention_days
await editor.cleanup_old_backups()
```

---

## 📈 MONITORING & TRACKING

### Get Operation Status

```python
# Start operation
result = await editor.edit_file(large_file_request)

# Monitor status
status = await editor.get_operation_status(result.operation_id)

print(f"Operation: {status['operation_id']}")
print(f"Status: {status['status']}")
print(f"Started: {status['started_at']}")
print(f"Duration: {status['duration_seconds']}s")
```

### List Active Operations

```python
# Get all active operations
active_ops = await editor.list_active_operations()

for op in active_ops:
    print(f"Active: {op['operation_id']}")
    print(f"  File: {op['file_path']}")
    print(f"  Type: {op['operation_type']}")
    print(f"  Duration: {op['duration_seconds']}s")
```

---

## 📦 BATCH OPERATIONS

### Process Multiple Files

```python
import asyncio

# Edit nhiều files cùng lúc
files = ["app.py", "utils.py", "config.py"]

tasks = []
for file_path in files:
    task = editor.edit_pattern(
        file_path=file_path,
        pattern="old_function",
        replacement="new_function"
    )
    tasks.append(task)

# Run all concurrently
results = await asyncio.gather(*tasks, return_exceptions=True)

# Process results
for i, result in enumerate(results):
    if isinstance(result, Exception):
        print(f"❌ {files[i]} failed: {result}")
    elif result.success:
        print(f"✅ {files[i]} success: {result.lines_changed} lines changed")
    else:
        print(f"⚠️  {files[i]} error: {result.error}")
```

---

## 🛡️ ERROR HANDLING

### Exception Types

```python
from editor.interfaces import (
    EditorException,           # Base exception
    FileNotFoundException,     # File not found
    FilePermissionException,   # Permission denied
    FileLockedException,       # File locked
    ValidationException,       # Validation failed
    BackupException,           # Backup failed
    SyntaxValidationException  # Syntax error after edit
)

try:
    result = await editor.edit_file(request)
    
except FileNotFoundException as e:
    print(f"File not found: {e}")
    
except FileLockedException as e:
    print(f"File locked by another process: {e}")
    # Retry after delay
    await asyncio.sleep(2)
    result = await editor.edit_file(request)
    
except ValidationException as e:
    print(f"Validation failed: {e}")
    # Skip validation
    request.options.validate_syntax = False
    result = await editor.edit_file(request)
    
except SyntaxValidationException as e:
    print(f"Syntax error after edit: {e}")
    # Rollback
    await editor.rollback(RollbackRequest(operation_id=result.operation_id))
    
except BackupException as e:
    print(f"Backup failed: {e}")
    # Continue without backup
    request.options.create_backup = False
    result = await editor.edit_file(request)
    
except EditorException as e:
    print(f"General editor error: {e}")
```

---

## 🔒 SECURITY FEATURES

### 1. Path Validation

```python
# ✅ Safe paths
"/safe/directory/file.py"
"./relative/path.py"

# ❌ Blocked paths
"../../../etc/passwd"        # Directory traversal
"/etc/shadow"                 # Outside allowed_base_paths
```

### 2. Extension Whitelist

```python
config = EditorConfig(
    allowed_extensions=['.py', '.js', '.ts']
)

# ✅ Allowed
await editor.edit_line("app.py", 1, "content")

# ❌ Blocked
await editor.edit_line("script.sh", 1, "content")  # Not in whitelist
```

### 3. File Size Limits

```python
config = EditorConfig(
    max_file_size_mb=50  # Reject files > 50MB
)
```

### 4. Permission Checks

```python
# Automatically checks:
# - File exists
# - Read permission
# - Write permission
# - Execute permission (if needed)
```

---

## 🎨 ADVANCED USAGE

### Custom AST Transformations

```python
# Complex AST transformation
ast_config = {
    "type": "refactor_function",
    "parameters": {
        "target_name": "process_data",
        "changes": {
            "add_type_hints": True,
            "add_docstring": True,
            "convert_to_async": True
        }
    }
}

result = await editor.edit_file(EditRequest(
    file_path="app.py",
    operation_type=EditOperationType.AST,
    target=json.dumps(ast_config),
    content=""
))
```

### Diff Generation

```python
result = await editor.edit_line("app.py", 10, "new content")

# Get unified diff
if result.diff:
    print("Changes:")
    print(result.diff)
    
# Output:
# --- app.py (original)
# +++ app.py (modified)
# @@ -8,1 +8,1 @@
# -old content
# +new content
```

---

## 🔗 INTEGRATION VỚI HEALCODE SYSTEM

### Workflow: AI Analysis → Editor → Git

```python
async def auto_fix_workflow(error_text: str):
    """Complete workflow: Analyze → Edit → Commit"""
    
    # 1. AI Analysis
    from ai.workflows import ErrorAnalysisWorkflow, WorkflowConfig
    
    workflow = ErrorAnalysisWorkflow(WorkflowConfig())
    analysis = await workflow.run_analysis(error_text)
    
    if not analysis['status']['success']:
        return
    
    # 2. Apply Fixes với Editor
    editor = EditorService(EditorConfig(backup_enabled=True))
    
    fix_suggestions = analysis['impact_analysis']['fix_suggestions']
    file_path = analysis['error_info']['parsed_error']['file']
    line_number = analysis['error_info']['parsed_error']['line']
    
    # Apply first suggestion
    result = await editor.edit_line(
        file_path=file_path,
        line_number=line_number,
        new_content=fix_suggestions[0],
        options=EditOptions(create_backup=True)
    )
    
    if not result.success:
        print(f"Edit failed: {result.error}")
        return
    
    # 3. Git Commit
    from gitplugin.core.git_operations import GitOperationsEngine
    
    git = GitOperationsEngine()
    await git.commit_changes(
        workspace="./",
        message=f"AI Fix: {analysis['error_info']['raw_error'][:50]}"
    )
    
    # 4. Create PR
    pr_result = await git.create_pull_request(
        workspace="./",
        title="AI Auto-fix",
        description=f"Fixes: {error_text}",
        target_branch="main"
    )
    
    print(f"✅ Complete! PR created: {pr_result['url']}")
```

### Integration với Queue System

```python
# serve/app.py
from editor import EditorService, EditRequest

@app.post("/api/edit")
async def edit_file_endpoint(request: EditRequest):
    """API endpoint for file editing"""
    
    editor = EditorService()
    result = await editor.edit_file(request)
    
    return {
        "success": result.success,
        "operation_id": result.operation_id,
        "diff": result.diff,
        "backup_path": result.backup_path,
        "error": result.error
    }
```

---

## 📊 EDIT RESULT STRUCTURE

```python
@dataclass
class EditResult:
    success: bool                  # Operation succeeded?
    operation_id: str              # Unique operation ID
    file_path: str                 # File that was edited
    operation_type: EditOperationType  # Type of operation
    diff: Optional[str]            # Unified diff of changes
    backup_path: Optional[str]     # Path to backup file
    lines_changed: int             # Number of lines changed
    bytes_changed: int             # Number of bytes changed
    error: Optional[str]           # Error message if failed
    execution_time_ms: float       # Execution time in ms
    metadata: Dict[str, Any]       # Additional metadata

# Example result
{
    "success": True,
    "operation_id": "abc-123-def-456",
    "file_path": "/path/to/app.py",
    "operation_type": "LINE",
    "diff": "--- app.py\n+++ app.py\n...",
    "backup_path": "./backups/app.py.abc-123.bak",
    "lines_changed": 3,
    "bytes_changed": 142,
    "error": None,
    "execution_time_ms": 25.3,
    "metadata": {
        "original_line": "old content",
        "new_line": "new content"
    }
}
```

---

## 🧪 TESTING

### Run Example

```bash
# Test basic functionality
python -m editor.example_usage

# Test specific strategies
python -m editor.examples.multi_language_example
```

### Unit Test Example

```python
import pytest
from editor import EditorService, EditOptions

@pytest.mark.asyncio
async def test_edit_line():
    """Test line editing"""
    editor = EditorService()
    
    # Create test file
    test_file = "test.py"
    with open(test_file, 'w') as f:
        f.write("line 1\nline 2\nline 3\n")
    
    # Edit line 2
    result = await editor.edit_line(
        file_path=test_file,
        line_number=2,
        new_content="modified line 2"
    )
    
    assert result.success
    assert result.lines_changed == 1
    
    # Verify content
    with open(test_file) as f:
        content = f.read()
    
    assert "modified line 2" in content
```

---

## 🎯 USE CASES THỰC TẾ

### 1. Code Review Auto-fix
```python
async def auto_fix_review_comments(pr_number: int):
    """Auto-fix code review comments"""
    
    comments = get_pr_comments(pr_number)
    
    for comment in comments:
        if "fix:" in comment.body.lower():
            await editor.edit_line(
                file_path=comment.file_path,
                line_number=comment.line_number,
                new_content=extract_fix_from_comment(comment.body)
            )
```

### 2. Refactoring Tool
```python
async def rename_function_everywhere(old_name: str, new_name: str):
    """Rename function across multiple files"""
    
    # Find all Python files
    files = glob.glob("**/*.py", recursive=True)
    
    for file in files:
        await editor.edit_pattern(
            file_path=file,
            pattern=f"def {old_name}\\(",
            replacement=f"def {new_name}("
        )
```

### 3. Config Update
```python
async def update_config_value(key: str, value: str):
    """Update configuration file"""
    
    await editor.edit_pattern(
        file_path="config.yaml",
        pattern=f"{key}:.*",
        replacement=f"{key}: {value}"
    )
```

---

## 📚 API REFERENCE QUICK

```python
# Main Methods
await editor.edit_file(request: EditRequest) -> EditResult
await editor.edit_line(file_path, line_number, new_content) -> EditResult
await editor.edit_lines(file_path, line_numbers, new_contents) -> EditResult
await editor.edit_range(file_path, start_line, end_line, new_content) -> EditResult
await editor.edit_pattern(file_path, pattern, replacement) -> EditResult
await editor.rollback(request: RollbackRequest) -> RollbackResult

# Monitoring
await editor.get_operation_status(operation_id) -> Dict
await editor.list_active_operations() -> List[Dict]
await editor.cleanup_old_backups()
```

---

## 💡 BEST PRACTICES

### ✅ DO's

1. **Always use backup for production**
   ```python
   options = EditOptions(create_backup=True)
   ```

2. **Validate syntax after edit**
   ```python
   options = EditOptions(validate_syntax=True)
   ```

3. **Use appropriate strategy**
   - Line editor for simple changes
   - Pattern editor for multiple replacements
   - AST editor for refactoring

4. **Handle errors properly**
   ```python
   try:
       result = await editor.edit_file(request)
   except FileLockedException:
       # Retry logic
   ```

5. **Monitor long operations**
   ```python
   status = await editor.get_operation_status(op_id)
   ```

### ❌ DON'Ts

1. **Don't edit without validation**
   ```python
   # Bad
   options = EditOptions(validate_syntax=False)
   ```

2. **Don't ignore errors**
   ```python
   # Bad
   result = await editor.edit_file(request)
   # Forgot to check result.success
   ```

3. **Don't edit files too large**
   - Set reasonable max_file_size_mb
   - Use streaming for very large files

4. **Don't run too many concurrent operations**
   - Respect max_concurrent_operations limit

---

## 🔧 TROUBLESHOOTING

### Issue: File Locked

```python
# Solution: Retry with backoff
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await editor.edit_file(request)
        break
    except FileLockedException:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
```

### Issue: Syntax Error After Edit

```python
# Solution: Rollback
try:
    result = await editor.edit_file(request)
except SyntaxValidationException:
    await editor.rollback(RollbackRequest(
        operation_id=result.operation_id
    ))
```

### Issue: Too Many Concurrent Operations

```python
# Solution: Increase semaphore or batch process
config = EditorConfig(
    max_concurrent_operations=20  # Increase limit
)
```

---

## 📦 FILE STRUCTURE

```
editor/
├── __init__.py              # Package exports
├── service.py               # Main EditorService
├── interfaces.py            # Data models & interfaces
├── strategies/              # Editing strategies
│   ├── __init__.py
│   ├── base_ast_editor.py   # AST base classes
│   ├── ast_editor.py        # Python AST editor
│   ├── line_editor.py       # Line/Range editor
│   ├── pattern_editor.py    # Regex editor
│   └── editor_factory.py    # Strategy factory
├── examples/                # Usage examples
│   └── multi_language_example.py
└── README.md               # Documentation
```

---

## 🎓 SUMMARY

**Editor Module** = **Safe File Editing System**

**Key Features**:
- ✅ 4 editing strategies (Line, Range, Pattern, AST)
- ✅ Concurrent access control với file locking
- ✅ Automatic backups & rollback
- ✅ Async API với timeout handling
- ✅ Security: path validation, permission checks
- ✅ Performance: memory efficient, concurrent operations

**Use Cases**:
- Auto-fix bugs từ AI analysis
- Code refactoring
- Config updates
- Batch file processing
- CI/CD automated edits

**Integration**:
- Works với AI Workflows
- Integrates với Git Plugin
- API endpoints ready
- Queue system compatible

---

**Created**: November 2024  
**Version**: 1.0.0  
**Language**: Tiếng Việt 🇻🇳

