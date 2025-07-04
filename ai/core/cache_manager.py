import asyncio
import json
import pickle
import gzip
import hashlib
import time
from typing import Any, Optional, Dict, List, Union
from dataclasses import asdict
import redis.asyncio as redis

from .error_context_collector import EnhancedContext, ErrorInfo, FunctionContext, UsageContext

class CacheStats:
    """Cache performance statistics"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
        self.total_size_cached = 0
        self.avg_response_time = 0.0
        
    def record_hit(self, response_time: float):
        self.hits += 1
        self.total_requests += 1
        self._update_avg_response_time(response_time)
        
    def record_miss(self, response_time: float):
        self.misses += 1
        self.total_requests += 1
        self._update_avg_response_time(response_time)
        
    def _update_avg_response_time(self, response_time: float):
        self.avg_response_time = (
            (self.avg_response_time * (self.total_requests - 1) + response_time) / 
            self.total_requests
        )
        
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total_requests': self.total_requests,
            'hit_rate': self.hit_rate,
            'avg_response_time_ms': self.avg_response_time * 1000,
            'total_size_cached_bytes': self.total_size_cached
        }

class CacheManager:
    """Redis-based intelligent caching with compression and version awareness"""
    
    def __init__(self, 
                 redis_client: redis.Redis,
                 tenant_id: str,
                 default_ttl: int = 3600,  # 1 hour
                 compression_threshold: int = 1024,  # Compress if > 1KB
                 max_cache_size: int = 100 * 1024 * 1024):  # 100MB max
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.default_ttl = default_ttl
        self.compression_threshold = compression_threshold
        self.max_cache_size = max_cache_size
        self.stats = CacheStats()
        
        # Cache key prefixes
        self.context_prefix = f"healcode:context:{tenant_id}:"
        self.metadata_prefix = f"healcode:meta:{tenant_id}:"
        self.stats_key = f"healcode:stats:{tenant_id}"
        
    async def get(self, cache_key: str) -> Optional[EnhancedContext]:
        """Get enhanced context from cache"""
        start_time = time.time()
        
        try:
            full_key = self.context_prefix + cache_key
            
            # Get cached data
            cached_data = await self.redis.get(full_key)
            
            response_time = time.time() - start_time
            
            if cached_data is None:
                self.stats.record_miss(response_time)
                return None
            
            # Deserialize
            enhanced_context = await self._deserialize_context(cached_data)
            
            # Update access time
            await self._update_access_time(cache_key)
            
            self.stats.record_hit(response_time)
            return enhanced_context
            
        except Exception as e:
            print(f"Cache get failed for key {cache_key}: {e}")
            self.stats.record_miss(time.time() - start_time)
            return None
    
    async def set(self, 
                  cache_key: str, 
                  enhanced_context: EnhancedContext, 
                  ttl: Optional[int] = None) -> bool:
        """Set enhanced context in cache with optional TTL"""
        
        try:
            full_key = self.context_prefix + cache_key
            ttl = ttl or self.default_ttl
            
            # Serialize context
            serialized_data = await self._serialize_context(enhanced_context)
            
            # Check cache size limits
            if len(serialized_data) > self.max_cache_size // 10:  # Single item can't be > 10% of total
                print(f"Context too large to cache: {len(serialized_data)} bytes")
                return False
            
            # Store in Redis with TTL
            await self.redis.setex(full_key, ttl, serialized_data)
            
            # Store metadata
            await self._store_metadata(cache_key, enhanced_context, len(serialized_data))
            
            # Update stats
            self.stats.total_size_cached += len(serialized_data)
            
            return True
            
        except Exception as e:
            print(f"Cache set failed for key {cache_key}: {e}")
            return False
    
    async def invalidate(self, cache_key: str) -> bool:
        """Invalidate specific cache entry"""
        try:
            full_key = self.context_prefix + cache_key
            meta_key = self.metadata_prefix + cache_key
            
            # Get size before deletion for stats
            metadata = await self.redis.get(meta_key)
            if metadata:
                meta_dict = json.loads(metadata)
                self.stats.total_size_cached -= meta_dict.get('size', 0)
            
            # Delete from Redis
            deleted_count = await self.redis.delete(full_key, meta_key)
            
            return deleted_count > 0
            
        except Exception as e:
            print(f"Cache invalidation failed for key {cache_key}: {e}")
            return False
    
    async def invalidate_file(self, file_path: str) -> int:
        """Invalidate all cache entries related to a specific file"""
        try:
            # Find all keys related to this file
            pattern = self.context_prefix + f"*{file_path.replace('/', ':').replace('.', '_')}*"
            keys = await self.redis.keys(pattern)
            
            if not keys:
                return 0
            
            # Delete all matching keys
            deleted_count = await self.redis.delete(*keys)
            
            # Also delete corresponding metadata
            meta_keys = [key.replace(self.context_prefix, self.metadata_prefix) for key in keys]
            await self.redis.delete(*meta_keys)
            
            return deleted_count
            
        except Exception as e:
            print(f"File cache invalidation failed for {file_path}: {e}")
            return 0
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries and update stats"""
        try:
            cleaned_count = 0
            
            # Get all metadata keys to check for orphaned entries
            meta_pattern = self.metadata_prefix + "*"
            meta_keys = await self.redis.keys(meta_pattern)
            
            for meta_key in meta_keys:
                cache_key = meta_key.replace(self.metadata_prefix, self.context_prefix)
                
                # Check if corresponding cache entry exists
                exists = await self.redis.exists(cache_key)
                if not exists:
                    # Remove orphaned metadata
                    await self.redis.delete(meta_key)
                    cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            print(f"Cache cleanup failed: {e}")
            return 0
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information"""
        try:
            # Get Redis info
            redis_info = await self.redis.info('memory')
            
            # Get our cache stats
            cache_stats = self.stats.to_dict()
            
            # Count our keys
            context_keys = await self.redis.keys(self.context_prefix + "*")
            meta_keys = await self.redis.keys(self.metadata_prefix + "*")
            
            return {
                'tenant_id': self.tenant_id,
                'cache_stats': cache_stats,
                'redis_memory_used': redis_info.get('used_memory_human', 'unknown'),
                'context_entries': len(context_keys),
                'metadata_entries': len(meta_keys),
                'default_ttl': self.default_ttl,
                'compression_threshold': self.compression_threshold,
                'max_cache_size': self.max_cache_size
            }
            
        except Exception as e:
            print(f"Failed to get cache info: {e}")
            return {'error': str(e)}
    
    async def _serialize_context(self, enhanced_context: EnhancedContext) -> bytes:
        """Serialize enhanced context with optional compression"""
        
        # Convert to dictionary for JSON serialization
        context_dict = self._context_to_dict(enhanced_context)
        
        # Serialize to JSON
        json_data = json.dumps(context_dict, default=str)
        
        # Convert to bytes
        data_bytes = json_data.encode('utf-8')
        
        # Compress if above threshold
        if len(data_bytes) > self.compression_threshold:
            data_bytes = gzip.compress(data_bytes)
            # Add compression marker
            data_bytes = b'GZIP:' + data_bytes
        
        return data_bytes
    
    async def _deserialize_context(self, data: bytes) -> EnhancedContext:
        """Deserialize enhanced context with decompression support"""
        
        # Check for compression marker
        if data.startswith(b'GZIP:'):
            data = gzip.decompress(data[5:])  # Remove marker and decompress
        
        # Decode JSON
        json_data = data.decode('utf-8')
        context_dict = json.loads(json_data)
        
        # Convert back to EnhancedContext
        return self._dict_to_context(context_dict)
    
    def _context_to_dict(self, enhanced_context: EnhancedContext) -> Dict[str, Any]:
        """Convert EnhancedContext to dictionary for serialization"""
        
        def convert_obj(obj):
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return obj
        
        result = {
            'original_error': convert_obj(enhanced_context.original_error),
            'target_function': convert_obj(enhanced_context.target_function) if enhanced_context.target_function else None,
            'usage_contexts': [convert_obj(usage) for usage in enhanced_context.usage_contexts],
            'dependency_info': enhanced_context.dependency_info,
            'summary': enhanced_context.summary,
            'processing_time_ms': enhanced_context.processing_time_ms,
            'cache_hit': enhanced_context.cache_hit
        }
        
        return result
    
    def _dict_to_context(self, context_dict: Dict[str, Any]) -> EnhancedContext:
        """Convert dictionary back to EnhancedContext"""
        
        # Reconstruct ErrorInfo
        error_dict = context_dict['original_error']
        original_error = ErrorInfo(
            error_type=error_dict['error_type'],
            variable_or_symbol=error_dict['variable_or_symbol'],
            file_path=error_dict['file_path'],
            line_number=error_dict['line_number'],
            column_number=error_dict.get('column_number'),
            repository=error_dict.get('repository')
        )
        
        # Reconstruct FunctionContext
        target_function = None
        if context_dict['target_function']:
            func_dict = context_dict['target_function']
            target_function = FunctionContext(
                name=func_dict['name'],
                signature=func_dict['signature'],
                implementation=func_dict['implementation'],
                start_line=func_dict['start_line'],
                end_line=func_dict['end_line'],
                file_path=func_dict['file_path'],
                language=func_dict['language'],
                documentation=func_dict.get('documentation'),
                parameters=func_dict.get('parameters')
            )
        
        # Reconstruct UsageContexts
        usage_contexts = []
        for usage_dict in context_dict['usage_contexts']:
            usage_context = UsageContext(
                file_path=usage_dict['file_path'],
                line_number=usage_dict['line_number'],
                context_before=usage_dict['context_before'],
                context_after=usage_dict['context_after'],
                usage_type=usage_dict['usage_type'],
                score=usage_dict['score']
            )
            usage_contexts.append(usage_context)
        
        # Reconstruct EnhancedContext
        return EnhancedContext(
            original_error=original_error,
            target_function=target_function,
            usage_contexts=usage_contexts,
            dependency_info=context_dict['dependency_info'],
            summary=context_dict.get('summary'),
            processing_time_ms=context_dict['processing_time_ms'],
            cache_hit=context_dict['cache_hit']
        )
    
    async def _store_metadata(self, 
                            cache_key: str, 
                            enhanced_context: EnhancedContext, 
                            size: int):
        """Store metadata about cached entry"""
        
        metadata = {
            'cache_key': cache_key,
            'size': size,
            'created_at': time.time(),
            'file_path': enhanced_context.original_error.file_path,
            'function_name': enhanced_context.target_function.name if enhanced_context.target_function else None,
            'usage_count': len(enhanced_context.usage_contexts),
            'processing_time_ms': enhanced_context.processing_time_ms
        }
        
        meta_key = self.metadata_prefix + cache_key
        await self.redis.setex(
            meta_key, 
            self.default_ttl + 300,  # Metadata lives 5 minutes longer 
            json.dumps(metadata)
        )
    
    async def _update_access_time(self, cache_key: str):
        """Update last access time for cache entry"""
        meta_key = self.metadata_prefix + cache_key
        
        try:
            metadata_json = await self.redis.get(meta_key)
            if metadata_json:
                metadata = json.loads(metadata_json)
                metadata['last_accessed'] = time.time()
                
                # Update metadata with new access time
                await self.redis.setex(
                    meta_key,
                    self.default_ttl + 300,
                    json.dumps(metadata)
                )
        except Exception as e:
            print(f"Failed to update access time for {cache_key}: {e}")
    
    async def generate_versioned_key(self, 
                                   base_key: str, 
                                   file_paths: List[str]) -> str:
        """Generate cache key that includes file version information"""
        
        # Create hash of file modification times (if available)
        version_data = []
        
        for file_path in file_paths:
            try:
                # In production, you would get actual file modification time
                # For now, we'll use file path as part of version
                version_data.append(f"{file_path}:{hash(file_path)}")
            except Exception:
                version_data.append(file_path)
        
        version_hash = hashlib.md5(":".join(version_data).encode()).hexdigest()[:8]
        
        return f"{base_key}:v{version_hash}"
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache statistics"""
        
        try:
            # Store current stats in Redis for persistence
            await self.redis.setex(
                self.stats_key,
                86400,  # 24 hours
                json.dumps(self.stats.to_dict())
            )
            
            # Get comprehensive stats
            cache_info = await self.get_cache_info()
            cache_info['detailed_stats'] = self.stats.to_dict()
            
            return cache_info
            
        except Exception as e:
            print(f"Failed to get cache statistics: {e}")
            return {'error': str(e)}
    
    async def warm_cache_for_error(self, error_input: str) -> bool:
        """Pre-warm cache for common error patterns"""
        # This could be implemented to pre-cache common error patterns
        # For now, it's a placeholder for future enhancement
        return True
        
    async def close(self):
        """Clean up resources"""
        try:
            # Save final stats
            await self.redis.setex(
                self.stats_key,
                86400,
                json.dumps(self.stats.to_dict())
            )
            
            # Close Redis connection
            await self.redis.close()
            
        except Exception as e:
            print(f"Error closing cache manager: {e}") 