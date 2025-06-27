import time
import httpx
from .base import LLMAdapter, ModelConfig, ModelResponse

class XaiAdapter(LLMAdapter):
    async def complete(self, messages, **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "model": self.config.name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature)
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(self.config.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            latency = time.time() - start
            return ModelResponse(
                content=result["choices"][0]["message"]["content"],
                model_name=self.config.name,
                usage=result.get("usage", {}),
                latency=latency,
                metadata={"raw": result}
            )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete([{"role": "user", "content": "ping"}])
            return bool(resp and resp.content)
        except Exception:
            return False 