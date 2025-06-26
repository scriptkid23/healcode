"""
Event Bus implementation for modular communication.

Implements publish/subscribe pattern for loose coupling between indexer modules
following Event-Driven Architecture principles.
"""

import asyncio
from typing import Dict, List, Callable, Any
from collections import defaultdict
import uuid
import logging
from datetime import datetime
from .interfaces import IEventBus, EventType


class EventBus(IEventBus):
    """Central event bus implementing pub/sub pattern"""
    
    def __init__(self, max_queue_size: int = 1000):
        self._subscribers: Dict[str, Dict[str, Callable]] = defaultdict(dict)
        self._event_queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._processor_task = None
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self.logger = logging.getLogger(__name__)
        
    async def start(self) -> None:
        """Start event processing"""
        if not self._running:
            self._running = True
            self._processor_task = asyncio.create_task(self._process_events())
            self.logger.info("Event bus started")
            
    async def stop(self) -> None:
        """Stop event processing"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Event bus stopped")
            
    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to bus"""
        event = {
            'id': str(uuid.uuid4()),
            'type': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'loop_time': asyncio.get_event_loop().time()
        }
        
        try:
            await self._event_queue.put(event)
            self.logger.debug(f"Event published: {event_type}")
        except asyncio.QueueFull:
            self.logger.error(f"Event queue full, dropping event: {event_type}")
            
    async def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe to events"""
        subscription_id = str(uuid.uuid4())
        self._subscribers[event_type][subscription_id] = handler
        self.logger.info(f"Subscribed to {event_type} with ID {subscription_id}")
        return subscription_id
        
    async def unsubscribe(self, event_type: str, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        if event_type in self._subscribers:
            removed = self._subscribers[event_type].pop(subscription_id, None)
            if removed:
                self.logger.info(f"Unsubscribed {subscription_id} from {event_type}")
                return True
        return False
        
    def get_subscriber_count(self, event_type: str = None) -> int:
        """Get number of subscribers for event type or total"""
        if event_type:
            return len(self._subscribers.get(event_type, {}))
        return sum(len(subs) for subs in self._subscribers.values())
        
    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent event history"""
        return self._event_history[-limit:]
        
    async def _process_events(self) -> None:
        """Internal event processor"""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._dispatch_event(event)
                self._add_to_history(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Event processing error: {e}")
                
    async def _dispatch_event(self, event: Dict[str, Any]) -> None:
        """Dispatch event to subscribers"""
        event_type = event['type']
        if event_type in self._subscribers:
            tasks = []
            for subscription_id, handler in self._subscribers[event_type].items():
                task = asyncio.create_task(
                    self._safe_call_handler(handler, event, subscription_id)
                )
                tasks.append(task)
            
            if tasks:
                # Wait for all handlers but don't fail if some handlers fail
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Log any handler exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(
                            f"Handler failed for event {event_type}: {result}"
                        )
                
    async def _safe_call_handler(
        self, handler: Callable, event: Dict[str, Any], subscription_id: str
    ) -> None:
        """Safely call event handler with timeout and error handling"""
        try:
            # Call handler with timeout
            await asyncio.wait_for(handler(event), timeout=30.0)
        except asyncio.TimeoutError:
            self.logger.error(
                f"Handler timeout for subscription {subscription_id}, "
                f"event {event['type']}"
            )
        except Exception as e:
            self.logger.error(
                f"Handler error for subscription {subscription_id}: {e}"
            )
            
    def _add_to_history(self, event: Dict[str, Any]) -> None:
        """Add event to history with size limit"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)


class TypedEventBus(EventBus):
    """Event bus with typed event support"""
    
    async def publish_typed(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Publish typed event"""
        await self.publish(event_type.value, data)
        
    async def subscribe_typed(self, event_type: EventType, handler: Callable) -> str:
        """Subscribe to typed event"""
        return await self.subscribe(event_type.value, handler)
        
    async def unsubscribe_typed(self, event_type: EventType, subscription_id: str) -> bool:
        """Unsubscribe from typed event"""
        return await self.unsubscribe(event_type.value, subscription_id) 