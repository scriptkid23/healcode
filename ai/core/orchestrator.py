from typing import Dict, Any, List
from dataclasses import dataclass
import logging
from datetime import datetime
import json

from .context_store import ContextStore
from .adapters.base import LLMAdapter, ModelResponse

@dataclass
class OrchestratorConfig:
    primary_model: str
    fallback_models: List[str]
    context_retention_hours: int = 24

class Orchestrator:
    def __init__(self, tenant_id: str, config: OrchestratorConfig, context_store: ContextStore, model_adapters: Dict[str, LLMAdapter]):
        self.tenant_id = tenant_id
        self.config = config
        self.context_store = context_store
        self.model_adapters = model_adapters
        self.logger = logging.getLogger(f"orchestrator.{tenant_id}")

    async def process(self, user_input: str, workflow_type: str = "general", **kwargs) -> ModelResponse:
        await self.context_store.set("last_user_input", user_input)
        full_context = await self.context_store.get_all()
        messages = await self._build_messages(user_input, full_context, workflow_type)
        response = await self._execute_with_failover(messages, **kwargs)
        await self.context_store.set("last_ai_response", response.content)
        return response

    async def _build_messages(self, user_input: str, context: Dict[str, Any], workflow_type: str) -> List[Dict[str, str]]:
        messages = []
        system_prompt = f"You are an AI assistant. Workflow: {workflow_type}. Context: {json.dumps(context)}"
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_input})
        return messages

    async def _execute_with_failover(self, messages: List[Dict[str, str]], **kwargs) -> ModelResponse:
        # Try primary model
        primary = self.model_adapters.get(self.config.primary_model)
        if primary and await primary.health_check():
            return await primary.complete(messages, **kwargs)
        # Fallback
        for name in self.config.fallback_models:
            adapter = self.model_adapters.get(name)
            if adapter and await adapter.health_check():
                return await adapter.complete(messages, **kwargs)
        raise Exception("All models failed") 