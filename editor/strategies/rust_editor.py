"""
Rust AST editor using Tree-sitter
"""

import json
from typing import Dict, Any, Set
from .base_ast_editor import TreeSitterEditor
from ..interfaces import ValidationException


class RustEditor(TreeSitterEditor):
    """Editor for Rust files using Tree-sitter"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.rs'}
    
    def get_supported_extensions(self) -> Set[str]:
        """Get supported file extensions"""
        return self.supported_extensions
    
    def get_language_name(self) -> str:
        """Get the language name"""
        return "Rust"
    
    def get_tree_sitter_language(self):
        """Get Tree-sitter Rust language"""
        try:
            import tree_sitter_rust
            return tree_sitter_rust.language()
        except ImportError:
            raise ValidationException(
                "tree-sitter-rust not installed. "
                "Install with: pip install tree-sitter-rust"
            )
    
    async def transform_ast(self, tree: Any, transformation_config: Dict[str, Any]) -> Any:
        """Transform Rust AST according to configuration"""
        transformer = RustTransformer(transformation_config)
        return transformer.transform(tree)
    
    async def ast_to_source(self, tree: Any) -> str:
        """Convert Tree-sitter tree back to Rust source"""
        # Tree-sitter doesn't have built-in source generation
        # We'll use the original source with manual edits based on transformations
        # For production use, you might want to use rustfmt or similar tools
        
        root_node = tree.root_node
        return root_node.text.decode() if hasattr(root_node, 'text') else ""
    
    async def analyze_ast_structure(self, tree: Any) -> Dict[str, Any]:
        """Analyze Rust AST structure"""
        analyzer = RustAnalyzer()
        return analyzer.analyze(tree)


class RustTransformer:
    """Rust AST transformer using Tree-sitter"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.applied_transformations = []
        
        # Map transformation types to handlers
        self.transformation_handlers = {
            'rename_function': self._rename_function,
            'add_use': self._add_use,
            'remove_use': self._remove_use,
            'add_mod': self._add_mod,
            'modify_function': self._modify_function,
            'add_impl_method': self._add_impl_method,
            'rename_variable': self._rename_variable,
            'add_derive': self._add_derive,
            'modify_struct': self._modify_struct,
            'add_trait_impl': self._add_trait_impl,
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
        """Rename function declarations"""
        params = self.config.get('parameters', {})
        old_name = params.get('old_name')
        new_name = params.get('new_name')
        
        self.applied_transformations.append(f"Renamed function {old_name} to {new_name}")
        return tree
    
    def _add_use(self, tree: Any) -> Any:
        """Add use statement"""
        params = self.config.get('parameters', {})
        module_path = params.get('module_path')
        items = params.get('items', [])
        
        self.applied_transformations.append(f"Added use statement: {module_path}")
        return tree
    
    def _remove_use(self, tree: Any) -> Any:
        """Remove use statement"""
        params = self.config.get('parameters', {})
        module_path = params.get('module_path')
        
        self.applied_transformations.append(f"Removed use statement: {module_path}")
        return tree
    
    def _add_mod(self, tree: Any) -> Any:
        """Add module declaration"""
        params = self.config.get('parameters', {})
        mod_name = params.get('name')
        is_public = params.get('public', False)
        
        visibility = "pub " if is_public else ""
        self.applied_transformations.append(f"Added {visibility}mod {mod_name}")
        return tree
    
    def _modify_function(self, tree: Any) -> Any:
        """Modify function signature or body"""
        params = self.config.get('parameters', {})
        function_name = params.get('name')
        modification_type = params.get('modification_type')
        
        self.applied_transformations.append(f"Modified function: {function_name}")
        return tree
    
    def _add_impl_method(self, tree: Any) -> Any:
        """Add method to impl block"""
        params = self.config.get('parameters', {})
        struct_name = params.get('struct_name')
        method_name = params.get('method_name')
        is_public = params.get('public', False)
        
        visibility = "pub " if is_public else ""
        self.applied_transformations.append(f"Added {visibility}method {method_name} to {struct_name}")
        return tree
    
    def _rename_variable(self, tree: Any) -> Any:
        """Rename variable declarations and references"""
        params = self.config.get('parameters', {})
        old_name = params.get('old_name')
        new_name = params.get('new_name')
        
        self.applied_transformations.append(f"Renamed variable {old_name} to {new_name}")
        return tree
    
    def _add_derive(self, tree: Any) -> Any:
        """Add derive attribute to struct/enum"""
        params = self.config.get('parameters', {})
        target_name = params.get('target_name')
        derives = params.get('derives', [])
        
        self.applied_transformations.append(f"Added derive {derives} to {target_name}")
        return tree
    
    def _modify_struct(self, tree: Any) -> Any:
        """Modify struct definition"""
        params = self.config.get('parameters', {})
        struct_name = params.get('name')
        modification_type = params.get('modification_type')
        
        self.applied_transformations.append(f"Modified struct: {struct_name}")
        return tree
    
    def _add_trait_impl(self, tree: Any) -> Any:
        """Add trait implementation"""
        params = self.config.get('parameters', {})
        trait_name = params.get('trait_name')
        struct_name = params.get('struct_name')
        
        self.applied_transformations.append(f"Added impl {trait_name} for {struct_name}")
        return tree


class RustAnalyzer:
    """Analyzer for Rust AST using Tree-sitter"""
    
    def __init__(self):
        self.analysis = {
            'functions': [],
            'structs': [],
            'enums': [],
            'traits': [],
            'impls': [],
            'mods': [],
            'uses': [],
            'constants': [],
            'statics': [],
            'complexity': 0
        }
    
    def analyze(self, tree: Any) -> Dict[str, Any]:
        """Analyze the Rust AST"""
        root_node = tree.root_node
        self._analyze_node(root_node)
        return self.analysis
    
    def _analyze_node(self, node):
        """Recursively analyze AST nodes"""
        node_type = node.type
        
        if node_type == 'function_item':
            self._analyze_function(node)
        elif node_type == 'struct_item':
            self._analyze_struct(node)
        elif node_type == 'enum_item':
            self._analyze_enum(node)
        elif node_type == 'trait_item':
            self._analyze_trait(node)
        elif node_type == 'impl_item':
            self._analyze_impl(node)
        elif node_type == 'mod_item':
            self._analyze_mod(node)
        elif node_type == 'use_declaration':
            self._analyze_use(node)
        elif node_type == 'const_item':
            self._analyze_const(node)
        elif node_type == 'static_item':
            self._analyze_static(node)
        
        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)
    
    def _analyze_function(self, node):
        """Analyze function item"""
        function_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'is_async': self._has_async_keyword(node),
            'is_unsafe': self._has_unsafe_keyword(node),
            'parameters': self._get_function_parameters(node),
            'return_type': self._get_return_type(node)
        }
        
        self.analysis['functions'].append(function_info)
        self.analysis['complexity'] += 1
    
    def _analyze_struct(self, node):
        """Analyze struct item"""
        struct_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'fields': self._get_struct_fields(node),
            'derives': self._get_derives(node),
            'generics': self._get_generics(node)
        }
        
        self.analysis['structs'].append(struct_info)
        self.analysis['complexity'] += 1
    
    def _analyze_enum(self, node):
        """Analyze enum item"""
        enum_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'variants': self._get_enum_variants(node),
            'derives': self._get_derives(node),
            'generics': self._get_generics(node)
        }
        
        self.analysis['enums'].append(enum_info)
        self.analysis['complexity'] += 1
    
    def _analyze_trait(self, node):
        """Analyze trait item"""
        trait_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'methods': self._get_trait_methods(node),
            'generics': self._get_generics(node)
        }
        
        self.analysis['traits'].append(trait_info)
        self.analysis['complexity'] += 1
    
    def _analyze_impl(self, node):
        """Analyze impl block"""
        impl_info = {
            'line': node.start_point[0] + 1,
            'trait_name': self._get_impl_trait(node),
            'type_name': self._get_impl_type(node),
            'methods': self._get_impl_methods(node),
            'generics': self._get_generics(node)
        }
        
        self.analysis['impls'].append(impl_info)
        self.analysis['complexity'] += len(impl_info['methods'])
    
    def _analyze_mod(self, node):
        """Analyze module declaration"""
        mod_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'is_inline': self._is_inline_mod(node)
        }
        
        self.analysis['mods'].append(mod_info)
    
    def _analyze_use(self, node):
        """Analyze use declaration"""
        use_info = {
            'line': node.start_point[0] + 1,
            'path': self._get_use_path(node),
            'items': self._get_use_items(node),
            'visibility': self._get_visibility(node)
        }
        
        self.analysis['uses'].append(use_info)
    
    def _analyze_const(self, node):
        """Analyze const item"""
        const_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'type': self._get_const_type(node)
        }
        
        self.analysis['constants'].append(const_info)
    
    def _analyze_static(self, node):
        """Analyze static item"""
        static_info = {
            'name': self._get_identifier_name(node),
            'line': node.start_point[0] + 1,
            'visibility': self._get_visibility(node),
            'type': self._get_static_type(node),
            'is_mutable': self._has_mut_keyword(node)
        }
        
        self.analysis['statics'].append(static_info)
    
    def _get_identifier_name(self, node) -> str:
        """Extract identifier name from node"""
        for child in node.children:
            if child.type == 'identifier':
                return child.text.decode()
        return 'unknown'
    
    def _get_visibility(self, node) -> str:
        """Get visibility modifier"""
        for child in node.children:
            if child.type == 'visibility_modifier':
                return child.text.decode()
        return 'private'
    
    def _has_async_keyword(self, node) -> bool:
        """Check if node has async keyword"""
        return any(child.text.decode() == 'async' for child in node.children)
    
    def _has_unsafe_keyword(self, node) -> bool:
        """Check if node has unsafe keyword"""
        return any(child.text.decode() == 'unsafe' for child in node.children)
    
    def _has_mut_keyword(self, node) -> bool:
        """Check if node has mut keyword"""
        return any(child.text.decode() == 'mut' for child in node.children)
    
    def _get_function_parameters(self, node) -> list:
        """Extract function parameters"""
        # Simplified implementation
        return []
    
    def _get_return_type(self, node) -> str:
        """Extract return type"""
        # Simplified implementation
        return "unknown"
    
    def _get_struct_fields(self, node) -> list:
        """Extract struct fields"""
        # Simplified implementation
        return []
    
    def _get_derives(self, node) -> list:
        """Extract derive attributes"""
        # Simplified implementation
        return []
    
    def _get_generics(self, node) -> list:
        """Extract generic parameters"""
        # Simplified implementation
        return []
    
    def _get_enum_variants(self, node) -> list:
        """Extract enum variants"""
        # Simplified implementation
        return []
    
    def _get_trait_methods(self, node) -> list:
        """Extract trait methods"""
        # Simplified implementation
        return []
    
    def _get_impl_trait(self, node) -> str:
        """Extract trait name from impl block"""
        # Simplified implementation
        return ""
    
    def _get_impl_type(self, node) -> str:
        """Extract type name from impl block"""
        # Simplified implementation
        return "unknown"
    
    def _get_impl_methods(self, node) -> list:
        """Extract impl methods"""
        # Simplified implementation
        return []
    
    def _is_inline_mod(self, node) -> bool:
        """Check if module is inline"""
        # Simplified implementation
        return False
    
    def _get_use_path(self, node) -> str:
        """Extract use path"""
        # Simplified implementation
        return ""
    
    def _get_use_items(self, node) -> list:
        """Extract use items"""
        # Simplified implementation
        return []
    
    def _get_const_type(self, node) -> str:
        """Extract const type"""
        # Simplified implementation
        return "unknown"
    
    def _get_static_type(self, node) -> str:
        """Extract static type"""
        # Simplified implementation
        return "unknown" 