"""
Trigram Indexer Plugin

A simple but efficient trigram-based text indexer demonstrating
the modular plugin architecture.
"""

import asyncio
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
import re
import logging


class TrigramIndexer:
    """
    Trigram-based text indexer implementation.
    
    Demonstrates Deep Module principle - simple interface with rich internal implementation.
    Follows Single Responsibility Principle - only handles trigram indexing.
    """
    
    # Plugin metadata (used by plugin registry)
    __version__ = "1.0.0"
    __indexer_type__ = "trigram"
    __supported_formats__ = ["text", "*"]
    __requires_config__ = []
    __dependencies__ = []
    
    def __init__(self, config: Dict[str, Any], event_bus: Optional[Any] = None):
        self.config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Configuration with defaults
        self.trigram_size = config.get('trigram_size', 3)
        self.case_sensitive = config.get('case_sensitive', False)
        self.min_word_length = config.get('min_word_length', 2)
        self.max_results = config.get('max_results', 1000)
        
        # Internal state
        self._trigram_index: Dict[str, Set[str]] = defaultdict(set)
        self._content_store: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._index_stats = {
            'total_documents': 0,
            'total_trigrams': 0,
            'last_indexed': None
        }
        
    async def initialize(self) -> bool:
        """Initialize the indexer"""
        try:
            self.logger.info(f"Initializing TrigramIndexer (size={self.trigram_size})")
            
            # Validate configuration
            if self.trigram_size < 1:
                raise ValueError("Trigram size must be at least 1")
                
            self._initialized = True
            
            if self.event_bus:
                await self.event_bus.publish("indexer_created", {
                    "indexer_type": "trigram",
                    "config": self.config
                })
                
            self.logger.info("TrigramIndexer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TrigramIndexer: {e}")
            return False
            
    async def shutdown(self) -> bool:
        """Cleanup resources"""
        try:
            self.logger.info("Shutting down TrigramIndexer")
            
            # Clear indexes to free memory
            self._trigram_index.clear()
            self._content_store.clear()
            
            self._initialized = False
            
            if self.event_bus:
                await self.event_bus.publish("indexer_destroyed", {
                    "indexer_type": "trigram"
                })
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
            
    async def index(self, content: str, metadata: Dict[str, Any]) -> bool:
        """
        Index content using trigrams.
        
        Simple interface hiding complex trigram generation and indexing logic.
        """
        if not self._initialized:
            raise RuntimeError("Indexer not initialized")
            
        try:
            content_id = metadata.get('id') or metadata.get('file_path', f"doc_{len(self._content_store)}")
            
            # Normalize content
            normalized_content = self._normalize_content(content)
            
            # Generate trigrams
            trigrams = self._generate_trigrams(normalized_content)
            
            # Store content and metadata
            self._content_store[content_id] = {
                'content': content,
                'metadata': metadata,
                'trigrams': trigrams,
                'length': len(content)
            }
            
            # Add trigrams to index
            for trigram in trigrams:
                self._trigram_index[trigram].add(content_id)
                
            # Update statistics
            self._index_stats['total_documents'] += 1
            self._index_stats['total_trigrams'] = len(self._trigram_index)
            self._index_stats['last_indexed'] = content_id
            
            self.logger.debug(
                f"Indexed document {content_id} with {len(trigrams)} trigrams"
            )
            
            # Publish indexing event
            if self.event_bus:
                await self.event_bus.publish("content_indexed", {
                    "indexer_type": "trigram",
                    "content_id": content_id,
                    "trigram_count": len(trigrams),
                    "content_length": len(content)
                })
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to index content: {e}")
            return False
            
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search using trigram matching.
        
        Returns ranked results based on trigram overlap.
        """
        if not self._initialized:
            raise RuntimeError("Indexer not initialized")
            
        try:
            # Normalize query
            normalized_query = self._normalize_content(query)
            
            # Generate query trigrams
            query_trigrams = self._generate_trigrams(normalized_query)
            
            if not query_trigrams:
                return []
                
            # Find candidate documents
            candidates = self._find_candidates(query_trigrams)
            
            # Score and rank candidates
            scored_results = self._score_candidates(candidates, query_trigrams, query)
            
            # Sort by score and limit results
            sorted_results = sorted(
                scored_results, 
                key=lambda x: x['score'], 
                reverse=True
            )[:limit]
            
            self.logger.debug(
                f"Search '{query}' found {len(sorted_results)} results "
                f"from {len(candidates)} candidates"
            )
            
            # Publish search event
            if self.event_bus:
                await self.event_bus.publish("search_performed", {
                    "indexer_type": "trigram",
                    "query": query,
                    "result_count": len(sorted_results),
                    "candidate_count": len(candidates)
                })
                
            return sorted_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []
            
    async def health_check(self) -> Dict[str, Any]:
        """Return health status and statistics"""
        return {
            "status": "healthy" if self._initialized else "unhealthy",
            "initialized": self._initialized,
            "config": {
                "trigram_size": self.trigram_size,
                "case_sensitive": self.case_sensitive,
                "min_word_length": self.min_word_length
            },
            "statistics": self._index_stats.copy(),
            "memory_usage": {
                "trigram_count": len(self._trigram_index),
                "document_count": len(self._content_store)
            }
        }
        
    # Private implementation methods (Deep Module internals)
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for indexing"""
        if not self.case_sensitive:
            content = content.lower()
            
        # Remove extra whitespace and normalize
        content = re.sub(r'\s+', ' ', content.strip())
        
        return content
        
    def _generate_trigrams(self, content: str) -> Set[str]:
        """Generate trigrams from content"""
        trigrams = set()
        
        # Split into words and filter by length
        words = [
            word for word in re.findall(r'\w+', content)
            if len(word) >= self.min_word_length
        ]
        
        # Generate trigrams from each word
        for word in words:
            if len(word) >= self.trigram_size:
                for i in range(len(word) - self.trigram_size + 1):
                    trigram = word[i:i + self.trigram_size]
                    trigrams.add(trigram)
            else:
                # For words shorter than trigram size, use the whole word
                trigrams.add(word)
                
        # Also generate trigrams from the full text (character-level)
        clean_content = re.sub(r'[^\w\s]', '', content)
        if len(clean_content) >= self.trigram_size:
            for i in range(len(clean_content) - self.trigram_size + 1):
                if clean_content[i:i + self.trigram_size].strip():
                    trigrams.add(clean_content[i:i + self.trigram_size])
                    
        return trigrams
        
    def _find_candidates(self, query_trigrams: Set[str]) -> Set[str]:
        """Find candidate documents that match any query trigrams"""
        candidates = set()
        
        for trigram in query_trigrams:
            if trigram in self._trigram_index:
                candidates.update(self._trigram_index[trigram])
                
        return candidates
        
    def _score_candidates(
        self, 
        candidates: Set[str], 
        query_trigrams: Set[str], 
        original_query: str
    ) -> List[Dict[str, Any]]:
        """Score candidate documents based on trigram overlap"""
        results = []
        
        for content_id in candidates:
            if content_id not in self._content_store:
                continue
                
            doc_data = self._content_store[content_id]
            doc_trigrams = doc_data['trigrams']
            
            # Calculate trigram overlap score
            overlap = len(query_trigrams.intersection(doc_trigrams))
            trigram_score = overlap / len(query_trigrams) if query_trigrams else 0
            
            # Boost score for exact text matches
            text_match_score = 0
            normalized_content = self._normalize_content(doc_data['content'])
            normalized_query = self._normalize_content(original_query)
            
            if normalized_query in normalized_content:
                text_match_score = 1.0
            elif any(word in normalized_content for word in normalized_query.split()):
                text_match_score = 0.5
                
            # Combined score
            final_score = (trigram_score * 0.7) + (text_match_score * 0.3)
            
            # Create result object
            result = {
                'id': content_id,
                'score': final_score,
                'content': doc_data['content'],
                'metadata': doc_data['metadata'],
                'match_info': {
                    'trigram_overlap': overlap,
                    'trigram_score': trigram_score,
                    'text_match_score': text_match_score,
                    'total_trigrams': len(doc_trigrams)
                }
            }
            
            results.append(result)
            
        return results 