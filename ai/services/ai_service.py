from typing import Dict, Any, Optional
from ai.core.context_store import ContextStore
from ai.core.orchestrator import Orchestrator, OrchestratorConfig
from ai.core.adapters.xai import XaiAdapter, ModelConfig as XaiModelConfig
from ai.core.adapters.google_gemini import GoogleGeminiAdapter, ModelConfig as GeminiModelConfig
# from ai.core.adapters.openai import OpenAIAdapter, ModelConfig as OpenAIModelConfig  # Uncomment if you add OpenAI

class AIService:
    def __init__(self, tenant_id: str, redis_url: str, model_configs: Dict[str, Dict[str, Any]], primary_model: str = "xai"):
        import redis.asyncio as redis
        redis_client = redis.from_url(redis_url)
        self.context_store = ContextStore(tenant_id, redis_client)
        adapters = {}
        for name, cfg in model_configs.items():
            if name == "xai":
                adapters[name] = XaiAdapter(XaiModelConfig(**cfg))
            elif name == "google_gemini":
                adapters[name] = GoogleGeminiAdapter(GeminiModelConfig(**cfg))
            # elif name == "openai":
            #     adapters[name] = OpenAIAdapter(OpenAIModelConfig(**cfg))
        config = OrchestratorConfig(primary_model=primary_model, fallback_models=[k for k in model_configs if k != primary_model])
        self.orchestrator = Orchestrator(tenant_id, config, self.context_store, adapters)

    async def debug_and_fix(self, error_message: str, code_context: Optional[str] = None, project_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if code_context:
            await self.context_store.set("code_context", code_context)
        if project_info:
            await self.context_store.set("project_info", project_info)
        await self.context_store.set("error_message", error_message)
        prompt = f"Debug this error: {error_message}\nContext: {code_context}\nProject: {project_info}"
        response = await self.orchestrator.process(prompt, workflow_type="debug")
        await self.context_store.set("debug_analysis", response.content)
        return {
            "analysis": response.content,
            "model_used": response.model_name,
            "latency": response.latency
        }

    async def chat(self, user_message: str) -> dict:
        """
        Send a user message to the primary model and return the full raw response from the AI model.
        """
        await self.context_store.set("user_message", user_message)
        response = await self.orchestrator.process(user_message, workflow_type="chat")
        # Return the full metadata/raw response from the model
        return response.metadata.get("raw", {})

    def decode_gemini_response(self, response: dict) -> str:
        """
        Extract the text output from a Gemini response dict.
        """
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "" 