"""
AST-based file editing strategy for syntax-aware code modifications
"""

import ast
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from ..interfaces import (
    EditRequest, EditResult, EditOperationType, EditorInterface,
    FileNotFoundException, ValidationException, OperationMetadata
)
from .base_ast_editor import BaseASTEditor


class ASTEditor(BaseASTEditor):
    """Editor for AST-based code modifications"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.py'}  # Currently only Python
    
    def get_supported_extensions(self) -> set[str]:
        return self.supported_extensions

    async def parse_file(self, file_path: str, content: str) -> Any:
        raise NotImplementedError

    async def transform_ast(self, ast_tree: Any, transformation_config: Dict[str, Any]) -> Any:
        raise NotImplementedError

    async def ast_to_source(self, ast_tree: Any) -> str:
        raise NotImplementedError

    def validate_syntax(self, content: str) -> bool:
        raise NotImplementedError

    def get_language_name(self) -> str:
        raise NotImplementedError

    async def analyze_ast_structure(self, ast_tree: Any) -> Dict[str, Any]:
        raise NotImplementedError

    def supports_operation(self, operation_type: EditOperationType) -> bool:
        """Check if this editor supports the given operation type"""
        return operation_type in self.supported_operations
    
    async def validate_request(self, request: EditRequest) -> bool:
        """Validate if the request can be processed"""
        if not self.supports_operation(request.operation_type):
            raise ValidationException(f"ASTEditor does not support {request.operation_type}")
        
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundException(f"File not found: {request.file_path}")
        
        if not file_path.is_file():
            raise ValidationException(f"Path is not a file: {request.file_path}")
        
        # Check file extension
        if file_path.suffix not in self.supported_extensions:
            raise ValidationException(f"Unsupported file extension: {file_path.suffix}")
        
        # Check if we can read and parse the file
        try:
            with open(file_path, 'r', encoding=request.options.encoding) as f:
                content = f.read()
            
            # Try to parse as Python AST
            ast.parse(content)
            
        except UnicodeDecodeError:
            raise ValidationException(f"Cannot decode file with encoding {request.options.encoding}")
        except PermissionError:
            raise ValidationException(f"No read permission for file: {request.file_path}")
        except SyntaxError as e:
            raise ValidationException(f"Syntax error in file: {e}")
        
        return True
    
    async def edit(self, request: EditRequest) -> EditResult:
        """Edit a file according to the request"""
        start_time = time.time()
        operation_id = OperationMetadata.generate_operation_id()
        
        try:
            await self.validate_request(request)
            
            if request.operation_type == EditOperationType.AST:
                result = await self._edit_ast(request, operation_id)
            else:
                return EditResult.error_result(
                    operation_id, request.file_path, request.operation_type,
                    f"Unsupported operation: {request.operation_type}"
                )
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            return EditResult.error_result(
                operation_id, request.file_path, request.operation_type, str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def _edit_ast(self, request: EditRequest, operation_id: str) -> EditResult:
        """Edit using AST transformations"""
        
        # Read original content
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            original_content = f.read()
        
        if not isinstance(request.content, str):
            raise ValidationException("Content for AST edit must be a string.")

        # Parse AST transformation instructions
        transformation_config = self._parse_transformation_config(str(request.target), request.content)
        
        # Parse the original file
        try:
            tree = ast.parse(original_content)
        except SyntaxError as e:
            raise ValidationException(f"Cannot parse file as valid Python: {e}")
        
        # Apply transformations
        transformer = ASTTransformer(transformation_config)
        modified_tree = transformer.visit(tree)
        
        # Convert back to source code
        try:
            import astor  # Optional dependency for better code generation
            modified_content = astor.to_source(modified_tree)
        except ImportError:
            # Fallback to basic ast unparse (Python 3.9+)
            try:
                modified_content = ast.unparse(modified_tree)
            except AttributeError:
                raise ValidationException("AST editing requires Python 3.9+ or astor library")
        
        # Create backup if requested
        if request.options.create_backup:
            import shutil
            backup_path = f"{request.file_path}.bak"
            shutil.copy2(request.file_path, backup_path)
        
        # Write modified content
        with open(request.file_path, 'w', encoding=request.options.encoding) as f:
            f.write(modified_content)
        
        # Generate diff
        diff = self._generate_diff(original_content, modified_content)
        
        # Count changes
        lines_changed = self._count_changed_lines(diff)
        
        return EditResult.success_result(
            operation_id=operation_id,
            file_path=request.file_path,
            operation_type=request.operation_type,
            diff=diff,
            lines_changed=lines_changed,
            bytes_changed=len(modified_content.encode()) - len(original_content.encode()),
            metadata={
                "transformations_applied": len(transformer.applied_transformations),
                "transformation_config": transformation_config
            }
        )
    
    def _parse_transformation_config(self, target: str, content: str) -> Dict[str, Any]:
        """Parse transformation configuration from request"""
        # target should be a JSON string or specific transformation type
        # content contains the specific transformation parameters
        
        try:
            import json
            if isinstance(target, str) and target.startswith('{'):
                config = json.loads(target)
            else:
                # Simple transformation type
                config = {
                    'type': target,
                    'parameters': content
                }
            
            return config
            
        except json.JSONDecodeError:
            # Fallback to simple string-based config
            return {
                'type': str(target),
                'parameters': content
            }
    
    def _generate_diff(self, original: str, modified: str) -> str:
        """Generate unified diff between original and modified content"""
        import difflib
        
        return '\n'.join(difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile='original',
            tofile='modified',
            lineterm=''
        ))
    
    def _count_changed_lines(self, diff: str) -> int:
        """Count the number of changed lines from diff output"""
        if not diff:
            return 0
        
        changed_lines = 0
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                changed_lines += 1
            elif line.startswith('-') and not line.startswith('---'):
                changed_lines += 1
        
        return changed_lines // 2
    
    async def analyze_ast(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Analyze AST structure of a file (utility method)"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            analyzer = ASTAnalyzer()
            analysis = analyzer.analyze(tree)
            
            return analysis
            
        except Exception as e:
            raise ValidationException(f"Error analyzing AST: {e}")


class ASTTransformer(ast.NodeTransformer):
    """Custom AST transformer for code modifications"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.applied_transformations = []
        
        # Set up transformation handlers
        self.transformation_handlers = {
            'rename_function': self._rename_function,
            'add_import': self._add_import,
            'remove_import': self._remove_import,
            'modify_function_body': self._modify_function_body,
            'add_decorator': self._add_decorator,
            'modify_class': self._modify_class,
        }
    
    def visit(self, node):
        """Visit and potentially transform nodes"""
        transformation_type = self.config.get('type')
        
        if transformation_type in self.transformation_handlers:
            handler = self.transformation_handlers[transformation_type]
            node = handler(node)
        
        return super().visit(node)
    
    def _rename_function(self, node):
        """Rename function/method names"""
        if isinstance(node, ast.FunctionDef):
            old_name = self.config.get('parameters', {}).get('old_name')
            new_name = self.config.get('parameters', {}).get('new_name')
            
            if node.name == old_name:
                node.name = new_name
                self.applied_transformations.append(f"Renamed function {old_name} to {new_name}")
        
        return node
    
    def _add_import(self, node):
        """Add import statements"""
        if isinstance(node, ast.Module):
            import_info = self.config.get('parameters', {})
            module_name = import_info.get('module')
            alias = import_info.get('alias')
            
            if module_name:
                if alias:
                    import_node = ast.ImportFrom(
                        module=module_name,
                        names=[ast.alias(name=alias, asname=None)],
                        level=0
                    )
                else:
                    import_node = ast.Import(
                        names=[ast.alias(name=module_name, asname=None)]
                    )
                
                # Insert at the beginning after docstring
                insert_pos = 0
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Str)):
                    insert_pos = 1
                
                node.body.insert(insert_pos, import_node)
                self.applied_transformations.append(f"Added import: {module_name}")
        
        return node
    
    def _remove_import(self, node):
        """Remove import statements"""
        if isinstance(node, ast.Module):
            module_to_remove = self.config.get('parameters', {}).get('module')
            
            new_body = []
            for stmt in node.body:
                should_remove = False
                
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        if alias.name == module_to_remove:
                            should_remove = True
                            break
                elif isinstance(stmt, ast.ImportFrom):
                    if stmt.module == module_to_remove:
                        should_remove = True
                
                if not should_remove:
                    new_body.append(stmt)
                else:
                    self.applied_transformations.append(f"Removed import: {module_to_remove}")
            
            node.body = new_body
        
        return node
    
    def _modify_function_body(self, node):
        """Modify function body"""
        if isinstance(node, ast.FunctionDef):
            target_function = self.config.get('parameters', {}).get('function_name')
            
            if node.name == target_function:
                # This is a simplified example - in practice, you'd have more
                # sophisticated logic for modifying function bodies
                modification_type = self.config.get('parameters', {}).get('modification_type')
                
                if modification_type == 'add_docstring':
                    docstring = self.config.get('parameters', {}).get('docstring', '')
                    docstring_node = ast.Expr(value=ast.Constant(value=docstring))
                    node.body.insert(0, docstring_node)
                    self.applied_transformations.append(f"Added docstring to {target_function}")
        
        return node
    
    def _add_decorator(self, node):
        """Add decorators to functions/classes"""
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            target_name = self.config.get('parameters', {}).get('target_name')
            decorator_name = self.config.get('parameters', {}).get('decorator')
            
            if node.name == target_name and decorator_name:
                decorator = ast.Name(id=decorator_name, ctx=ast.Load())
                node.decorator_list.append(decorator)
                self.applied_transformations.append(f"Added decorator @{decorator_name} to {target_name}")
        
        return node
    
    def _modify_class(self, node):
        """Modify class definitions"""
        if isinstance(node, ast.ClassDef):
            target_class = self.config.get('parameters', {}).get('class_name')
            
            if node.name == target_class:
                # Example: add a method to the class
                method_info = self.config.get('parameters', {}).get('add_method')
                if method_info:
                    method_name = method_info.get('name')
                    method_body = method_info.get('body', 'pass')
                    
                    # Create a simple method
                    method_node = ast.FunctionDef(
                        name=method_name,
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg='self', annotation=None)],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[]
                        ),
                        body=[ast.Expr(value=ast.Constant(value=method_body))],
                        decorator_list=[],
                        returns=None
                    )
                    
                    node.body.append(method_node)
                    self.applied_transformations.append(f"Added method {method_name} to class {target_class}")
        
        return node


class ASTAnalyzer(ast.NodeVisitor):
    """Analyzer for extracting information from AST"""
    
    def __init__(self):
        self.analysis = {
            'functions': [],
            'classes': [],
            'imports': [],
            'globals': [],
            'complexity': 0
        }
    
    def analyze(self, tree):
        """Analyze the AST and return information"""
        self.visit(tree)
        return self.analysis
    
    def visit_FunctionDef(self, node):
        """Visit function definitions"""
        self.analysis['functions'].append({
            'name': node.name,
            'line': node.lineno,
            'args': [arg.arg for arg in node.args.args],
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'docstring': self._get_docstring(node)
        })
        self.analysis['complexity'] += 1
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Visit class definitions"""
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        self.analysis['classes'].append({
            'name': node.name,
            'line': node.lineno,
            'methods': methods,
            'bases': [self._get_name(base) for base in node.bases],
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'docstring': self._get_docstring(node)
        })
        self.analysis['complexity'] += len(methods) + 1
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """Visit import statements"""
        for alias in node.names:
            self.analysis['imports'].append({
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
                'line': node.lineno
            })
    
    def visit_ImportFrom(self, node):
        """Visit from-import statements"""
        for alias in node.names:
            self.analysis['imports'].append({
                'type': 'from_import',
                'module': node.module,
                'name': alias.name,
                'alias': alias.asname,
                'line': node.lineno
            })
    
    def _get_decorator_name(self, decorator):
        """Get decorator name as string"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_name(decorator.value)}.{decorator.attr}"
        return str(decorator)
    
    def _get_name(self, node):
        """Get name from various node types"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)
    
    def _get_docstring(self, node):
        """Extract docstring from function/class"""
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Str)):
            return node.body[0].value.s
        return None 