"""
Editor factory for selecting appropriate editing strategies
"""

from pathlib import Path
from typing import Optional, Dict, List, Type
from ..interfaces import EditorInterface, ValidationException

# Import all available editors
from .ast_editor import ASTEditor
from .line_editor import LineEditor  
from .pattern_editor import PatternEditor
from .javascript_editor import JavaScriptEditor, TypeScriptEditor
from .rust_editor import RustEditor


class EditorFactory:
    """Factory for creating appropriate editor instances"""
    
    def __init__(self):
        self._ast_editors: Dict[str, Type[EditorInterface]] = {}
        self._fallback_editors: List[Type[EditorInterface]] = []
        self._register_default_editors()
    
    def _register_default_editors(self):
        """Register default editors"""
        # AST editors for specific languages
        self.register_ast_editor(ASTEditor, {'.py'})
        self.register_ast_editor(JavaScriptEditor, {'.js', '.jsx', '.mjs'})
        self.register_ast_editor(TypeScriptEditor, {'.ts', '.tsx'})
        self.register_ast_editor(RustEditor, {'.rs'})
        
        # Fallback editors (work with any text file)
        self.register_fallback_editor(LineEditor)
        self.register_fallback_editor(PatternEditor)
    
    def register_ast_editor(self, editor_class: Type[EditorInterface], extensions: set):
        """Register an AST editor for specific file extensions"""
        for ext in extensions:
            self._ast_editors[ext] = editor_class
    
    def register_fallback_editor(self, editor_class: Type[EditorInterface]):
        """Register a fallback editor that works with any file"""
        self._fallback_editors.append(editor_class)
    
    def get_ast_editor(self, file_path: str) -> Optional[EditorInterface]:
        """Get AST editor for a file based on its extension"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in self._ast_editors:
            editor_class = self._ast_editors[file_ext]
            return editor_class()
        
        return None
    
    def get_fallback_editors(self) -> List[EditorInterface]:
        """Get all fallback editors"""
        return [editor_class() for editor_class in self._fallback_editors]
    
    def get_editor(self, file_path: str, preferred_type: Optional[str] = None) -> EditorInterface:
        """
        Get the most appropriate editor for a file
        
        Args:
            file_path: Path to the file
            preferred_type: Preferred editor type ('ast', 'line', 'pattern')
        
        Returns:
            EditorInterface instance
        
        Raises:
            ValidationException: If no suitable editor is found
        """
        file_path_obj = Path(file_path)
        file_ext = file_path_obj.suffix.lower()
        
        # If user prefers AST editing and we have an AST editor for this file type
        if preferred_type == 'ast' or preferred_type is None:
            ast_editor = self.get_ast_editor(file_path)
            if ast_editor:
                return ast_editor
        
        # Fall back to general-purpose editors
        if preferred_type == 'line':
            return LineEditor()
        elif preferred_type == 'pattern':
            return PatternEditor()
        elif preferred_type is None:
            # Auto-select: prefer AST if available, otherwise line editor
            ast_editor = self.get_ast_editor(file_path)
            if ast_editor:
                return ast_editor
            return LineEditor()
        
        raise ValidationException(f"No suitable editor found for {file_path}")
    
    def get_supported_languages(self) -> Dict[str, List[str]]:
        """Get mapping of supported languages to their file extensions"""
        language_map = {}
        
        for ext, editor_class in self._ast_editors.items():
            editor_instance = editor_class()
            lang_name = getattr(editor_instance, 'get_language_name', lambda: None)()
            if lang_name:
                if lang_name not in language_map:
                    language_map[lang_name] = []
                language_map[lang_name].append(ext)
        
        return language_map
    
    def get_editor_capabilities(self, file_path: str) -> Dict[str, bool]:
        """Get capabilities of editors for a specific file"""
        capabilities = {
            'ast_editing': False,
            'line_editing': True,  # Always available
            'pattern_editing': True,  # Always available
            'syntax_validation': False,
            'semantic_analysis': False
        }
        
        # Check if AST editing is available
        ast_editor = self.get_ast_editor(file_path)
        if ast_editor:
            capabilities['ast_editing'] = True
            capabilities['syntax_validation'] = True
            capabilities['semantic_analysis'] = True
        
        return capabilities


class LanguageRegistry:
    """Registry for language-specific information and parsers"""
    
    def __init__(self):
        self._languages = {
            'Python': {
                'extensions': ['.py', '.pyw', '.pyi'],
                'parser_type': 'ast',
                'parser_library': 'ast',
                'formatter': 'black',
                'linter': 'flake8'
            },
            'JavaScript': {
                'extensions': ['.js', '.jsx', '.mjs'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-javascript',
                'formatter': 'prettier',
                'linter': 'eslint'
            },
            'TypeScript': {
                'extensions': ['.ts', '.tsx'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-typescript',
                'formatter': 'prettier',
                'linter': 'tslint'
            },
            'Rust': {
                'extensions': ['.rs'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-rust',
                'formatter': 'rustfmt',
                'linter': 'clippy'
            },
            'Go': {
                'extensions': ['.go'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-go',
                'formatter': 'gofmt',
                'linter': 'golint'
            },
            'Java': {
                'extensions': ['.java'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-java',
                'formatter': 'google-java-format',
                'linter': 'checkstyle'
            },
            'C++': {
                'extensions': ['.cpp', '.cxx', '.cc', '.c++', '.hpp', '.hxx', '.h++'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-cpp',
                'formatter': 'clang-format',
                'linter': 'clang-tidy'
            },
            'C': {
                'extensions': ['.c', '.h'],
                'parser_type': 'tree-sitter',
                'parser_library': 'tree-sitter-c',
                'formatter': 'clang-format',
                'linter': 'clang-tidy'
            }
        }
    
    def get_language_info(self, file_path: str) -> Optional[Dict]:
        """Get language information for a file"""
        file_ext = Path(file_path).suffix.lower()
        
        for lang_name, lang_info in self._languages.items():
            if file_ext in lang_info['extensions']:
                return {
                    'name': lang_name,
                    **lang_info
                }
        
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language names"""
        return list(self._languages.keys())
    
    def register_language(self, name: str, config: Dict):
        """Register a new language"""
        required_fields = ['extensions', 'parser_type', 'parser_library']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        self._languages[name] = config
    
    def get_extension_to_language_map(self) -> Dict[str, str]:
        """Get mapping from file extension to language name"""
        ext_map = {}
        for lang_name, lang_info in self._languages.items():
            for ext in lang_info['extensions']:
                ext_map[ext] = lang_name
        return ext_map


# Global instances
editor_factory = EditorFactory()
language_registry = LanguageRegistry()


def get_editor_for_file(file_path: str, preferred_type: Optional[str] = None) -> EditorInterface:
    """Convenience function to get editor for a file"""
    return editor_factory.get_editor(file_path, preferred_type)


def get_language_info(file_path: str) -> Optional[Dict]:
    """Convenience function to get language info for a file"""
    return language_registry.get_language_info(file_path)


def get_supported_languages() -> Dict[str, List[str]]:
    """Convenience function to get supported languages and their extensions"""
    return editor_factory.get_supported_languages()


def register_custom_editor(editor_class: Type[EditorInterface], extensions: set):
    """Convenience function to register a custom editor"""
    editor_factory.register_ast_editor(editor_class, extensions)


def register_custom_language(name: str, config: Dict):
    """Convenience function to register a custom language"""
    language_registry.register_language(name, config) 