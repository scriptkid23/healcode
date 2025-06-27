from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class ModelResponse:
    content: str
    model_name: str
    usage: Dict[str, int]
    latency: float
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelConfig:
    name: str
    endpoint: str
    api_key: str
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: float = 30.0
    retry_attempts: int = 3

class LLMAdapter(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> ModelResponse:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass 