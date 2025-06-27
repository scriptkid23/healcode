"""
Modular Codebase Indexer Framework

A pluggable architecture for codebase analysis and indexing
following Deep Modules with Simple Interfaces philosophy.
"""

__version__ = "1.0.0"
__author__ = "HealCode Team"

# Public API exports - keeping interface minimal (Deep Module principle)
from .zoekt_client import ZoektClient

__all__ = [
    "ZoektClient",
]
