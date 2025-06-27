import time
import httpx
from .base import LLMAdapter, ModelConfig, ModelResponse

class GoogleGeminiAdapter(LLMAdapter):
    async def complete(self, messages, **kwargs) -> ModelResponse:
        start = time.time()
        # Gemini expects a 'contents' list, each with 'parts' (list of {'text': ...})
        # We'll flatten all user/assistant messages into one 'contents' item with multiple 'parts'
        parts = [{"text": m["content"]} for m in messages]
        payload = {
            "contents": [
                {"parts": parts}
            ]
        }
        headers = {
            "Content-Type": "application/json"
        }
        # API key is passed as a query param in the endpoint
        url = f"{self.config.endpoint}?key={self.config.api_key}"
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            try:
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                print("Gemini API error:", resp.text)
                raise
            latency = time.time() - start
            # Gemini's response: result['candidates'][0]['content']['parts'][0]['text']
            try:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                content = "<no content>"
            return ModelResponse(
                content=content,
                model_name=self.config.name,
                usage={},
                latency=latency,
                metadata={"raw": result}
            )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete([{"role": "user", "content": "ping"}])
            return bool(resp and resp.content)
        except Exception:
            return False 