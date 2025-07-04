from typing import Dict, Any, Optional, List
from ai.core.context_store import ContextStore
# from ai.core.orchestrator import Orchestrator, OrchestratorConfig # Removing orchestrator
# from ai.core.adapters.xai import XaiAdapter, ModelConfig as XaiModelConfig # No longer used
# from ai.core.adapters.google_gemini import GoogleGeminiAdapter, ModelConfig as GeminiModelConfig # No longer used
# from ai.core.adapters.openai import OpenAIAdapter, ModelConfig as OpenAIModelConfig  # Uncomment if you add OpenAI

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from ai.prompts.code_analysis import CodeFix, CODE_FIX_PROMPT_TEMPLATE


class CodeFixMetadata(BaseModel):
    total_lines_analyzed: int = Field(description="The total number of lines in the merged document that were analyzed.")
    processing_time_ms: int = Field(description="The time in milliseconds it took the model to process the request.")
    model_used: str = Field(description="The name of the language model that was used to generate the suggestions.")

class NoIssuesFound(BaseModel):
    message: str = Field(default="No issues found.", description="A message indicating that no issues were found in the code.")

class AIService:
    def __init__(self, tenant_id: str, redis_url: str, model_configs: Dict[str, Dict[str, Any]], primary_model: str = "google_gemini"):
        import redis.asyncio as redis
        redis_client = redis.from_url(redis_url)
        self.context_store = ContextStore(tenant_id, redis_client)
        
        self.llms = {}
        for name, cfg in model_configs.items():
            api_key = cfg.get("api_key")
            if not api_key:
                raise ValueError(f"API key for model '{name}' not found in config.")

            if name == "google_gemini":
                self.llms[name] = ChatGoogleGenerativeAI(model=cfg.get("name", "gemini-1.5-flash-latest"), google_api_key=api_key)
            elif name == "openai":
                self.llms[name] = ChatOpenAI(model=cfg.get("name", "gpt-4"), api_key=api_key)
            elif name == "anthropic":
                self.llms[name] = ChatAnthropic(
                    model_name=cfg.get("name", "claude-2"), 
                    api_key=api_key,
                    timeout=cfg.get("timeout", 30.0),
                    stop=[]
                )

        self.primary_llm = self.llms.get(primary_model)
        if not self.primary_llm:
            raise ValueError(f"Primary model '{primary_model}' not found in configured models.")

        # Define parser with Pydantic schema
        self.parser = JsonOutputParser(pydantic_object=CodeFix)

        # Create prompt template
        self.prompt = PromptTemplate(
            template=CODE_FIX_PROMPT_TEMPLATE,
            input_variables=["code"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        # Chain and invoke
        self.chain = self.prompt | self.primary_llm | self.parser


    async def debug_and_fix(self, repo_content: str, project_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if project_info:
            await self.context_store.set("project_info", project_info)

        # The prompt uses {code} as the input variable for the repository content.
        result = await self.chain.ainvoke({"code": repo_content})
        
        await self.context_store.set("debug_analysis", result)
        return result

    async def chat(self, user_message: str) -> str:
        """
        Send a user message to the primary model and return the text response.
        """
        assert self.primary_llm is not None
        await self.context_store.set("user_message", user_message)
        response = await self.primary_llm.ainvoke(user_message)
        return response.content

    def decode_gemini_response(self, response: dict) -> str:
        """
        Extract the text output from a Gemini response dict.
        """
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "" 