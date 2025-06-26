"""
HealCode Editor Module

A comprehensive file editing system with concurrent access, backup management,
and multiple editing strategies for safe code modifications.
"""

from .service import EditorService
from .interfaces import EditRequest, EditResult, EditOptions, RollbackResult, EditOperationType
from .strategies import LineEditor, PatternEditor, ASTEditor

__all__ = [
    "EditorService",
    "EditRequest", 
    "EditResult",
    "EditOptions",
    "RollbackResult",
    "EditOperationType",
    "LineEditor",
    "PatternEditor", 
    "ASTEditor",
]

__version__ = "1.0.0"
