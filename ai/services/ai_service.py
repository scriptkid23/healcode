from typing import Dict, Any, Optional, List
from ai.core.context_store import ContextStore
from ai.core.repo_processor import RepoProcessor

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.schema import Document
import asyncio

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
        self.repo_processor = RepoProcessor()  # Add repo processor instance
        
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


    async def debug_and_fix(self, documents: List[Document], project_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if project_info:
            await self.context_store.set("project_info", project_info)

        all_line_numbers = []
        all_new_contents = []
        metadata = {}

        async def process_doc(doc):
            # Add line numbers to content to help AI accurately identify lines
            start_line = doc.metadata.get("start_line", 1)
            numbered_content = self.repo_processor.add_line_numbers_to_content(
                doc.page_content, start_line
            )
            
            # The prompt uses {code} as the input variable for the repository content.
            result = await self.chain.ainvoke({"code": numbered_content})
            
            if result.get("line_numbers"):
                # AI model now returns absolute line numbers directly since we provided numbered content
                # No conversion needed since the line numbers in the content are already absolute
                absolute_lines = result["line_numbers"]
                
                return absolute_lines, result["new_contents"], result.get("metadata", {})
            return [], [], {}

        tasks = [process_doc(doc) for doc in documents]
        results = await asyncio.gather(*tasks)

        for absolute_lines, new_contents, meta in results:
            all_line_numbers.extend(absolute_lines)
            all_new_contents.extend(new_contents)
            # Combine metadata (simplified: last one wins for now)
            if meta:
                metadata = meta

        final_result = {
            "line_numbers": all_line_numbers,
            "new_contents": all_new_contents,
            "metadata": metadata
        }

        await self.context_store.set("debug_analysis", final_result)
        return final_result

    async def chat(self, user_message: str) -> str:
        """
        Send a user message to the primary model and return the text response.
        """
        assert self.primary_llm is not None
        await self.context_store.set("user_message", user_message)
        response = await self.primary_llm.ainvoke(user_message)
        return response.content 