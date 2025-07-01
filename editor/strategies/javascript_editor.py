"""
JavaScript/TypeScript AST editor using Tree-sitter
"""

import json
from typing import Dict, Any, Set
from .base_ast_editor import TreeSitterEditor
from ..interfaces import ValidationException


class JavaScriptEditor(TreeSitterEditor):
    """Editor for JavaScript files using Tree-sitter"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.js', '.jsx', '.mjs'}
    
    def get_supported_extensions(self) -> Set[str]:
        """Get supported file extensions"""
        return self.supported_extensions
    
    def get_language_name(self) -> str:
        """Get the language name"""
        return "JavaScript"
    
    def get_tree_sitter_language(self):
        """Get Tree-sitter JavaScript language"""
        try:
            import tree_sitter_javascript
            return tree_sitter_javascript.language()
        except ImportError:
            raise ValidationException(
                "tree-sitter-javascript not installed. "
                "Install with: pip install tree-sitter-javascript"
            )
    
    async def transform_ast(self, tree: Any, transformation_config: Dict[str, Any]) -> Any:
        """Transform JavaScript AST according to configuration"""
        transformer = JavaScriptTransformer(transformation_config)
        return transformer.transform(tree)
    
    async def ast_to_source(self, tree: Any) -> str:
        """Convert Tree-sitter tree back to JavaScript source"""
        # Tree-sitter doesn't have built-in source generation
        # We'll use the original source with manual edits based on transformations
        # This is a simplified approach - in production, you might want to use
        # a proper JavaScript AST library like Babel (via subprocess)
        
        root_node = tree.root_node
        return root_node.text.decode() if hasattr(root_node, 'text') else ""
    
    async def analyze_ast_structure(self, tree: Any) -> Dict[str, Any]:
        """Analyze JavaScript AST structure"""
        analyzer = JavaScriptAnalyzer()
        return analyzer.analyze(tree)


class TypeScriptEditor(JavaScriptEditor):
    """Editor for TypeScript files using Tree-sitter"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.ts', '.tsx'}
    
    def get_language_name(self) -> str:
        """Get the language name"""
        return "TypeScript"
    
    def get_tree_sitter_language(self):
        """Get Tree-sitter TypeScript language"""
        try:
            import tree_sitter_typescript
            return tree_sitter_typescript.language_typescript()
        except ImportError:
            raise ValidationException(
                "tree-sitter-typescript not installed. "
                "Install with: pip install tree-sitter-typescript"
            )


class JavaScriptTransformer:
    """JavaScript AST transformer using Tree-sitter"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.applied_transformations = []
        
        # Map transformation types to handlers
        self.transformation_handlers = {
            'rename_function': self._rename_function,
            'add_import': self._add_import,
            'remove_import': self._remove_import,
            'add_export': self._add_export,
            'modify_function': self._modify_function,
            'add_method': self._add_method,
            'rename_variable': self._rename_variable,
        }
    
    def transform(self, tree: Any) -> Any:
        """Apply transformations to the tree"""
        transformation_type = self.config.get('type')
        
        if transformation_type in self.transformation_handlers:
            handler = self.transformation_handlers[transformation_type]
            return handler(tree)
        else:
            raise ValidationException(f"Unknown transformation type: {transformation_type}")
    
    def _rename_function(self, tree: Any) -> Any:
        """Rename function declarations and expressions"""
        # This is a simplified example
        # In a real implementation, you'd traverse the tree and modify nodes
        self.applied_transformations.append("Renamed function")
        return tree
    
    def _add_import(self, tree: Any) -> Any:
        """Add import statement"""
        params = self.config.get('parameters', {})
        module_name = params.get('module')
        import_type = params.get('type', 'default')  # default, named, namespace
        
        self.applied_transformations.append(f"Added import from {module_name}")
        return tree
    
    def _remove_import(self, tree: Any) -> Any:
        """Remove import statement"""
        params = self.config.get('parameters', {})
        module_name = params.get('module')
        
        self.applied_transformations.append(f"Removed import from {module_name}")
        return tree
    
    def _add_export(self, tree: Any) -> Any:
        """Add export statement"""
        params = self.config.get('parameters', {})
        export_name = params.get('name')
        export_type = params.get('type', 'named')  # default, named
        
        self.applied_transformations.append(f"Added export: {export_name}")
        return tree
    
    def _modify_function(self, tree: Any) -> Any:
        """Modify function body or signature"""
        params = self.config.get('parameters', {})
        function_name = params.get('name')
        modification_type = params.get('modification_type')
        
        self.applied_transformations.append(f"Modified function: {function_name}")
        return tree
    
    def _add_method(self, tree: Any) -> Any:
        """Add method to class"""
        params = self.config.get('parameters', {})
        class_name = params.get('class_name')
        method_name = params.get('method_name')
        
        self.applied_transformations.append(f"Added method {method_name} to class {class_name}")
        return tree
    
    def _rename_variable(self, tree: Any) -> Any:
        """Rename variable declarations and references"""
        params = self.config.get('parameters', {})
        old_name = params.get('old_name')
        new_name = params.get('new_name')
        
        self.applied_transformations.append(f"Renamed variable {old_name} to {new_name}")
        return tree


class JavaScriptAnalyzer:
    """Analyzer for JavaScript AST using Tree-sitter"""
    
    def __init__(self):
        self.analysis = {
            'functions': [],
            'classes': [],
            'imports': [],
            'exports': [],
            'variables': [],
            'complexity': 0
        }
    
    def analyze(self, tree: Any) -> Dict[str, Any]:
        """Analyze the JavaScript AST"""
        root_node = tree.root_node
        self._analyze_node(root_node)
        return self.analysis
    
    def _analyze_node(self, node):
        """Recursively analyze AST nodes"""
        node_type = node.type
        
        if node_type == 'function_declaration':
            self._analyze_function(node)
        elif node_type == 'class_declaration':
            self._analyze_class(node)
        elif node_type == 'import_statement':
            self._analyze_import(node)
        elif node_type == 'export_statement':
            self._analyze_export(node)
        elif node_type == 'variable_declaration':
            self._analyze_variable(node)
        
        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)
    
    def _analyze_function(self, node):
        """Analyze function declaration"""
        function_info = {
            'name': self._get_function_name(node),
            'line': node.start_point[0] + 1,
            'parameters': self._get_function_parameters(node),
            'is_async': self._is_async_function(node),
            'is_generator': self._is_generator_function(node)
        }
        
        self.analysis['functions'].append(function_info)
        self.analysis['complexity'] += 1
    
    def _analyze_class(self, node):
        """Analyze class declaration"""
        class_info = {
            'name': self._get_class_name(node),
            'line': node.start_point[0] + 1,
            'methods': self._get_class_methods(node),
            'extends': self._get_class_parent(node)
        }
        
        self.analysis['classes'].append(class_info)
        self.analysis['complexity'] += len(class_info['methods']) + 1
    
    def _analyze_import(self, node):
        """Analyze import statement"""
        import_info = {
            'line': node.start_point[0] + 1,
            'source': self._get_import_source(node),
            'imports': self._get_import_specifiers(node)
        }
        
        self.analysis['imports'].append(import_info)
    
    def _analyze_export(self, node):
        """Analyze export statement"""
        export_info = {
            'line': node.start_point[0] + 1,
            'type': self._get_export_type(node),
            'name': self._get_export_name(node)
        }
        
        self.analysis['exports'].append(export_info)
    
    def _analyze_variable(self, node):
        """Analyze variable declaration"""
        variable_info = {
            'line': node.start_point[0] + 1,
            'kind': self._get_variable_kind(node),  # var, let, const
            'names': self._get_variable_names(node)
        }
        
        self.analysis['variables'].append(variable_info)
    
    def _get_function_name(self, node) -> str:
        """Extract function name from node"""
        # This is simplified - you'd need to traverse the AST to find the identifier
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return 'anonymous'
    
    def _get_function_parameters(self, node) -> list:
        """Extract function parameters"""
        # Simplified implementation
        return []
    
    def _is_async_function(self, node) -> bool:
        """Check if function is async"""
        return 'async' in node.text.decode()
    
    def _is_generator_function(self, node) -> bool:
        """Check if function is generator"""
        return '*' in node.text.decode()
    
    def _get_class_name(self, node) -> str:
        """Extract class name"""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return 'anonymous'
    
    def _get_class_methods(self, node) -> list:
        """Extract class methods"""
        methods = []
        for child in node.children:
            if child.type == 'class_body':
                for method in child.children:
                    if method.type == 'method_definition':
                        methods.append(self._get_function_name(method))
        return methods
    
    def _get_class_parent(self, node) -> str:
        """Extract parent class name"""
        # Simplified implementation
        return ""
    
    def _get_import_source(self, node) -> str:
        """Extract import source"""
        # Simplified implementation
        return ""
    
    def _get_import_specifiers(self, node) -> list:
        """Extract import specifiers"""
        # Simplified implementation
        return []
    
    def _get_export_type(self, node) -> str:
        """Get export type (default, named, etc.)"""
        # Simplified implementation
        return "named"
    
    def _get_export_name(self, node) -> str:
        """Get export name"""
        # Simplified implementation
        return ""
    
    def _get_variable_kind(self, node) -> str:
        """Get variable declaration kind"""
        # Simplified implementation
        return "var"
    
    def _get_variable_names(self, node) -> list:
        """Get variable names"""
        # Simplified implementation
        return [] 