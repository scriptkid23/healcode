"""
Editor strategies for different types of file editing operations
"""

from .line_editor import LineEditor
from .pattern_editor import PatternEditor
from .ast_editor import ASTEditor
from .base_ast_editor import BaseASTEditor, TreeSitterEditor
from .javascript_editor import JavaScriptEditor, TypeScriptEditor
from .rust_editor import RustEditor
from .editor_factory import (
    EditorFactory, LanguageRegistry, editor_factory, language_registry,
    get_editor_for_file, get_language_info, get_supported_languages,
    register_custom_editor, register_custom_language
)

__all__ = [
    "LineEditor",
    "PatternEditor", 
    "ASTEditor",
    "BaseASTEditor",
    "TreeSitterEditor",
    "JavaScriptEditor",
    "TypeScriptEditor", 
    "RustEditor",
    "EditorFactory",
    "LanguageRegistry",
    "editor_factory",
    "language_registry",
    "get_editor_for_file",
    "get_language_info", 
    "get_supported_languages",
    "register_custom_editor",
    "register_custom_language",
] 