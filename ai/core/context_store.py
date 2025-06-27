import asyncio
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from datetime import datetime
from redis import asyncio as redis  # type: ignore  # May show as unresolved in some editors, but works with redis-py >=4.2.0
import uuid

@dataclass
class ContextEntry:
    key: str
    value: Any
    timestamp: datetime
    ttl: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class ContextStore:
    """
    Context store supporting multi-tenant isolation, Redis persistence, versioning, audit, and memory management.
    """
    def __init__(self, tenant_id: str, redis_client: Optional[redis.Redis] = None, max_size: int = 100_000, default_ttl: int = 3600):
        self.tenant_id = tenant_id
        self.session_id = str(uuid.uuid4())
        self.redis = redis_client or redis.Redis()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._local_cache = {}
        self._audit_log = []

    def _get_key(self, key: str) -> str:
        return f"tenant:{self.tenant_id}:session:{self.session_id}:context:{key}"

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        metadata = metadata or {}
        entry = ContextEntry(key=key, value=value, timestamp=datetime.utcnow(), ttl=ttl or self.default_ttl, metadata=metadata)
        self._local_cache[key] = entry
        redis_key = self._get_key(key)
        serialized = json.dumps(asdict(entry), default=str)
        if ttl:
            await self.redis.setex(redis_key, ttl, serialized)
        else:
            await self.redis.set(redis_key, serialized)
        self._audit_log.append({"action": "set", "key": key, "timestamp": datetime.utcnow(), "metadata": metadata})
        await self._cleanup_if_needed()

    async def get(self, key: str) -> Optional[Any]:
        if key in self._local_cache:
            entry = self._local_cache[key]
            return entry.value
        redis_key = self._get_key(key)
        data = await self.redis.get(redis_key)
        if data:
            entry_dict = json.loads(data)
            entry = ContextEntry(**entry_dict)
            self._local_cache[key] = entry
            return entry.value
        return None

    async def get_all(self) -> Dict[str, Any]:
        context = {}
        pattern = self._get_key("*")
        keys = await self.redis.keys(pattern)
        for redis_key in keys:
            data = await self.redis.get(redis_key)
            if data:
                entry_dict = json.loads(data)
                entry = ContextEntry(**entry_dict)
                actual_key = redis_key.decode().split(":")[-1]
                context[actual_key] = entry.value
        return context

    async def snapshot(self) -> str:
        snapshot_id = str(uuid.uuid4())
        full_context = await self.get_all()
        snapshot = {
            "id": snapshot_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow(),
            "context": full_context,
            "audit_log": self._audit_log
        }
        snapshot_key = f"snapshot:{snapshot_id}"
        await self.redis.setex(snapshot_key, 86400, json.dumps(snapshot, default=str))
        return snapshot_id

    async def _cleanup_if_needed(self):
        if len(self._local_cache) > self.max_size:
            # Simple LRU: remove oldest
            oldest = sorted(self._local_cache.items(), key=lambda x: x[1].timestamp)[:10]
            for k, _ in oldest:
                del self._local_cache[k] 