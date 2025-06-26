"""
Editor strategies for different types of file editing operations
"""

from .line_editor import LineEditor
from .pattern_editor import PatternEditor
from .ast_editor import ASTEditor

__all__ = [
    "LineEditor",
    "PatternEditor", 
    "ASTEditor",
] 