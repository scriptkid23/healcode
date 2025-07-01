"""
Base AST editor for language-agnostic AST operations
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Set, List

from ..interfaces import (
    EditRequest, EditResult, EditOperationType, EditorInterface,
    FileNotFoundException, ValidationException, OperationMetadata
)


class BaseASTEditor(EditorInterface, ABC):
    """Base class for AST-based file editors"""
    
    def __init__(self):
        self.supported_operations = {EditOperationType.AST}
        self.supported_extensions: Set[str] = set()
        self._parser = None
    
    def supports_operation(self, operation_type: EditOperationType) -> bool:
        """Check if this editor supports the given operation type"""
        return operation_type in self.supported_operations
    
    @abstractmethod
    def get_supported_extensions(self) -> Set[str]:
        """Get supported file extensions for this editor"""
        pass
    
    @abstractmethod
    async def parse_file(self, file_path: str, content: str) -> Any:
        """Parse file content into AST"""
        pass
    
    @abstractmethod
    async def transform_ast(self, ast_tree: Any, transformation_config: Dict[str, Any]) -> Any:
        """Transform AST according to configuration"""
        pass
    
    @abstractmethod
    async def ast_to_source(self, ast_tree: Any) -> str:
        """Convert AST back to source code"""
        pass
    
    @abstractmethod
    def validate_syntax(self, content: str) -> bool:
        """Validate syntax of the content"""
        pass
    
    async def validate_request(self, request: EditRequest) -> bool:
        """Validate if the request can be processed"""
        if not self.supports_operation(request.operation_type):
            raise ValidationException(f"{self.__class__.__name__} does not support {request.operation_type}")
        
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundException(f"File not found: {request.file_path}")
        
        if not file_path.is_file():
            raise ValidationException(f"Path is not a file: {request.file_path}")
        
        # Check file extension
        supported_extensions = self.get_supported_extensions()
        if file_path.suffix not in supported_extensions:
            raise ValidationException(f"Unsupported file extension: {file_path.suffix}")
        
        # Check if we can read and parse the file
        try:
            with open(file_path, 'r', encoding=request.options.encoding) as f:
                content = f.read()
            
            # Validate syntax
            if request.options.validate_syntax:
                if not self.validate_syntax(content):
                    raise ValidationException("File contains syntax errors")
            
        except UnicodeDecodeError:
            raise ValidationException(f"Cannot decode file with encoding {request.options.encoding}")
        except PermissionError:
            raise ValidationException(f"No read permission for file: {request.file_path}")
        
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
        
        # Parse AST transformation instructions
        transformation_config = self._parse_transformation_config(str(request.target), request.content)
        
        # Parse the original file
        try:
            ast_tree = await self.parse_file(request.file_path, original_content)
        except Exception as e:
            raise ValidationException(f"Cannot parse file: {e}")
        
        # Apply transformations
        try:
            modified_ast = await self.transform_ast(ast_tree, transformation_config)
        except Exception as e:
            raise ValidationException(f"AST transformation failed: {e}")
        
        # Convert back to source code
        try:
            modified_content = await self.ast_to_source(modified_ast)
        except Exception as e:
            raise ValidationException(f"Failed to convert AST to source: {e}")
        
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
                "language": self.get_language_name(),
                "transformation_config": transformation_config
            }
        )
    
    def _parse_transformation_config(self, target: str, content: str) -> Dict[str, Any]:
        """Parse transformation configuration from request"""
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
    
    @abstractmethod
    def get_language_name(self) -> str:
        """Get the name of the programming language this editor handles"""
        pass
    
    async def analyze_ast(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Analyze AST structure of a file (utility method)"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            ast_tree = await self.parse_file(file_path, content)
            analysis = await self.analyze_ast_structure(ast_tree)
            
            return analysis
            
        except Exception as e:
            raise ValidationException(f"Error analyzing AST: {e}")
    
    @abstractmethod
    async def analyze_ast_structure(self, ast_tree: Any) -> Dict[str, Any]:
        """Analyze AST structure and return information"""
        pass


class TreeSitterEditor(BaseASTEditor):
    """Base class for Tree-sitter based editors"""
    
    def __init__(self):
        super().__init__()
        self._tree_sitter_language = None
        self._parser = None
    
    @abstractmethod
    def get_tree_sitter_language(self):
        """Get Tree-sitter language object"""
        pass
    
    async def parse_file(self, file_path: str, content: str) -> Any:
        """Parse file using Tree-sitter"""
        if not self._parser:
            try:
                import tree_sitter  # type: ignore
                self._parser = tree_sitter.Parser()  # type: ignore
                self._parser.set_language(self.get_tree_sitter_language())  # type: ignore
            except ImportError:
                raise ValidationException("tree-sitter not installed. Install with: pip install tree-sitter")
        
        tree = self._parser.parse(content.encode())
        return tree
    
    def validate_syntax(self, content: str) -> bool:
        """Validate syntax using Tree-sitter"""
        try:
            tree = self._parser.parse(content.encode()) if self._parser else None
            return tree is not None and not tree.root_node.has_error
        except Exception:
            return False 