# Multi-Language AST Editor Strategies

Hệ thống này cung cấp các strategy để chỉnh sửa mã nguồn AST-aware cho nhiều ngôn ngữ lập trình khác nhau.

## Kiến trúc

### Base Classes

- **`BaseASTEditor`**: Abstract base class cho tất cả AST editors
- **`TreeSitterEditor`**: Base class cho editors sử dụng Tree-sitter parser

### Language-specific Editors

- **`ASTEditor`**: Python AST editor (sử dụng module `ast` built-in)
- **`JavaScriptEditor`**: JavaScript editor (sử dụng Tree-sitter)
- **`TypeScriptEditor`**: TypeScript editor (sử dụng Tree-sitter)
- **`RustEditor`**: Rust editor (sử dụng Tree-sitter)

### Factory và Registry

- **`EditorFactory`**: Factory để chọn editor phù hợp dựa trên file extension
- **`LanguageRegistry`**: Registry lưu thông tin về các ngôn ngữ được hỗ trợ

## Cài đặt Dependencies

### Base dependencies
```bash
pip install tree-sitter
```

### Language-specific parsers
```bash
# JavaScript
pip install tree-sitter-javascript

# TypeScript  
pip install tree-sitter-typescript

# Rust
pip install tree-sitter-rust

# Python (optional, for better code generation)
pip install astor
```

## Sử dụng cơ bản

### 1. Tự động chọn editor

```python
from editor.strategies import get_editor_for_file
from editor.interfaces import EditRequest, EditOperationType, EditOptions

# Tự động chọn editor dựa trên file extension
editor = get_editor_for_file("calculator.py")
print(f"Selected: {editor.__class__.__name__}")  # ASTEditor

editor = get_editor_for_file("app.js") 
print(f"Selected: {editor.__class__.__name__}")  # JavaScriptEditor
```

### 2. Phân tích AST

```python
# Phân tích cấu trúc AST
analysis = await editor.analyze_ast("calculator.py")
print(f"Functions: {analysis['functions']}")
print(f"Classes: {analysis['classes']}")
print(f"Complexity: {analysis['complexity']}")
```

### 3. Biến đổi AST

```python
# Tạo edit request
request = EditRequest(
    file_path="calculator.py",
    operation_type=EditOperationType.AST,
    target='{"type": "rename_function"}',
    content='{"old_name": "old_func", "new_name": "new_func"}',
    options=EditOptions(create_backup=True)
)

# Thực hiện biến đổi
result = await editor.edit(request)
if result.success:
    print(f"✓ Transformation completed: {result.lines_changed} lines changed")
else:
    print(f"✗ Error: {result.error}")
```

## Các loại biến đổi hỗ trợ

### Python (ASTEditor)
- `rename_function`: Đổi tên function
- `add_import`: Thêm import statement
- `remove_import`: Xóa import statement
- `modify_function_body`: Sửa đổi function body
- `add_decorator`: Thêm decorator
- `modify_class`: Sửa đổi class

### JavaScript/TypeScript
- `rename_function`: Đổi tên function
- `add_import`: Thêm import statement
- `remove_import`: Xóa import statement
- `add_export`: Thêm export statement
- `modify_function`: Sửa đổi function
- `add_method`: Thêm method vào class
- `rename_variable`: Đổi tên variable

### Rust
- `rename_function`: Đổi tên function
- `add_use`: Thêm use statement
- `remove_use`: Xóa use statement
- `add_mod`: Thêm module declaration
- `modify_function`: Sửa đổi function
- `add_impl_method`: Thêm method vào impl block
- `rename_variable`: Đổi tên variable
- `add_derive`: Thêm derive attribute
- `modify_struct`: Sửa đổi struct
- `add_trait_impl`: Thêm trait implementation

## Mở rộng hỗ trợ ngôn ngữ mới

### 1. Tạo Editor class mới

```python
from editor.strategies.base_ast_editor import TreeSitterEditor

class GoEditor(TreeSitterEditor):
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.go'}
    
    def get_supported_extensions(self):
        return self.supported_extensions
    
    def get_language_name(self):
        return "Go"
    
    def get_tree_sitter_language(self):
        import tree_sitter_go
        return tree_sitter_go.language()
    
    async def transform_ast(self, tree, transformation_config):
        # Implement Go-specific transformations
        pass
    
    async def ast_to_source(self, tree):
        # Convert AST back to Go source code
        pass
    
    async def analyze_ast_structure(self, tree):
        # Analyze Go AST structure
        pass
```

### 2. Đăng ký editor mới

```python
from editor.strategies import register_custom_editor, register_custom_language

# Đăng ký editor
register_custom_editor(GoEditor, {'.go'})

# Đăng ký thông tin ngôn ngữ
register_custom_language('Go', {
    'extensions': ['.go'],
    'parser_type': 'tree-sitter',
    'parser_library': 'tree-sitter-go',
    'formatter': 'gofmt',
    'linter': 'golint'
})
```

## Ví dụ hoàn chính

Xem file `editor/examples/multi_language_example.py` để có ví dụ chi tiết về:
- Tự động phát hiện ngôn ngữ
- Chọn editor phù hợp
- Phân tích AST
- Thực hiện biến đổi
- Mở rộng hỗ trợ ngôn ngữ mới

## Chạy ví dụ

```bash
cd editor/examples
python multi_language_example.py
```

## Lưu ý

1. **Tree-sitter parsers**: Các parser Tree-sitter cần được cài đặt riêng cho từng ngôn ngữ
2. **AST to Source**: Tree-sitter không hỗ trợ chuyển đổi AST về source code. Hiện tại sử dụng source gốc với manual edits
3. **Production use**: Để sử dụng trong production, nên tích hợp với các tool chuyên biệt như Babel (JS/TS) hoặc rustfmt (Rust)
4. **Error handling**: Luôn kiểm tra `result.success` và xử lý `result.error` khi thực hiện biến đổi

## Roadmap

- [ ] Hỗ trợ Go, Java, C/C++
- [ ] Tích hợp với language servers
- [ ] Semantic refactoring
- [ ] Better source code generation
- [ ] Plugin system cho custom transformations 