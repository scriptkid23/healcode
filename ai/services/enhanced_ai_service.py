from typing import Dict, Any, Optional, List
import time
import redis.asyncio as redis

from ai.core.context_store import ContextStore
from ai.core.repo_processor import RepoProcessor
from ai.core.error_context_collector import ErrorContextCollector
from ai.core.function_analyzer import FunctionAnalyzer
from ai.core.zoekt_search_manager import ZoektSearchManager
from ai.core.context_summarizer import ContextSummarizer
from ai.core.cache_manager import CacheManager

from indexer.zoekt_client import ZoektClient

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.schema import Document
import asyncio

from ai.prompts.code_analysis import CodeFix, CODE_FIX_PROMPT_TEMPLATE


class EnhancedCodeFix(BaseModel):
    """Enhanced code fix with context information"""
    line_numbers: List[int] = Field(description="A list of absolute line numbers that need to be fixed")
    new_contents: List[str] = Field(description="A list of corrected code lines")
    explanation: str = Field(description="Explanation of why these fixes are needed based on context analysis")
    confidence_score: float = Field(description="Confidence score (0-1) based on context quality")
    context_used: Dict[str, Any] = Field(description="Summary of context that was used for analysis")

class EnhancedAIService:
    """AI Service with enhanced context collection and analysis capabilities"""
    
    def __init__(self, 
                 tenant_id: str, 
                 redis_url: str, 
                 model_configs: Dict[str, Dict[str, Any]], 
                 zoekt_endpoint: str = "http://127.0.0.1:6070/api/search",
                 primary_model: str = "google_gemini",
                 max_context_files: int = 10):
        
        # Initialize Redis connection
        redis_client = redis.from_url(redis_url)
        
        # Initialize core components
        self.context_store = ContextStore(tenant_id, redis_client)
        self.repo_processor = RepoProcessor()
        
        # Initialize LLM clients
        self.llms = {}
        for name, cfg in model_configs.items():
            api_key = cfg.get("api_key")
            if not api_key:
                raise ValueError(f"API key for model '{name}' not found in config.")

            if name == "google_gemini":
                self.llms[name] = ChatGoogleGenerativeAI(
                    model=cfg.get("name", "gemini-1.5-flash-latest"), 
                    google_api_key=api_key
                )
            elif name == "openai":
                self.llms[name] = ChatOpenAI(
                    model=cfg.get("name", "gpt-4"), 
                    api_key=api_key
                )
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

        # Initialize enhanced context components
        self.zoekt_client = ZoektClient(zoekt_endpoint)
        self.function_analyzer = FunctionAnalyzer()
        self.zoekt_search_manager = ZoektSearchManager(self.zoekt_client, max_context_files)
        self.context_summarizer = ContextSummarizer(self.primary_llm)
        self.cache_manager = CacheManager(redis_client, tenant_id)
        
        # Initialize error context collector
        self.error_context_collector = ErrorContextCollector(
            zoekt_client=self.zoekt_client,
            function_analyzer=self.function_analyzer,
            context_summarizer=self.context_summarizer,
            cache_manager=self.cache_manager,
            zoekt_search_manager=self.zoekt_search_manager,
            max_files=max_context_files
        )

        # Define enhanced parser
        self.enhanced_parser = JsonOutputParser(pydantic_object=EnhancedCodeFix)
        
        # Create enhanced prompt template
        self.enhanced_prompt = PromptTemplate(
            template=self._create_enhanced_prompt_template(),
            input_variables=["error_input", "enhanced_context"],
            partial_variables={"format_instructions": self.enhanced_parser.get_format_instructions()}
        )

        # Enhanced chain
        self.enhanced_chain = self.enhanced_prompt | self.primary_llm | self.enhanced_parser

        # Fallback to original system
        self.parser = JsonOutputParser(pydantic_object=CodeFix)
        self.prompt = PromptTemplate(
            template=CODE_FIX_PROMPT_TEMPLATE,
            input_variables=["code"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        self.chain = self.prompt | self.primary_llm | self.parser

    def _create_enhanced_prompt_template(self) -> str:
        """Create enhanced prompt template that utilizes context information"""
        return """You are an advanced AI assistant that analyzes code errors with comprehensive context understanding.

You have been provided with an error and enhanced context information including:
- The target function containing the error
- How the function is used across the codebase
- Related dependencies and imports
- Similar functions and patterns

ERROR TO ANALYZE:
{error_input}

ENHANCED CONTEXT:
{enhanced_context}

Your task is to provide a comprehensive fix based on this rich context. Consider:

1. **Error Analysis**: What exactly is causing the error based on the context?
2. **Usage Patterns**: How is this function used elsewhere? Are there patterns that show the correct usage?
3. **Dependencies**: Are there missing imports or incorrect dependencies?
4. **Best Practices**: Based on similar functions, what's the recommended approach?
5. **Confidence**: How confident are you in the fix based on available context?

{format_instructions}

Provide a detailed analysis with specific fixes and high confidence based on the enhanced context.
"""

    async def debug_and_fix_with_context(self, error_input: str) -> Dict[str, Any]:
        """
        Enhanced debug and fix method that uses comprehensive context analysis
        
        Args:
            error_input: Error description in format like "variable_name error_type error file_path line:column"
        
        Returns:
            Enhanced fix results with context information
        """
        
        try:
            # Collect enhanced context using the error context collector
            enhanced_context = await self.error_context_collector.collect_enhanced_context(error_input)
            
            # Format context for AI consumption
            context_text = self.error_context_collector.format_context_for_ai(enhanced_context)
            
            # Use enhanced chain for analysis
            result = await self.enhanced_chain.ainvoke({
                "error_input": error_input,
                "enhanced_context": context_text
            })
            
            # Add context metadata to result
            result["context_metadata"] = {
                "processing_time_ms": enhanced_context.processing_time_ms,
                "cache_hit": enhanced_context.cache_hit,
                "function_analyzed": enhanced_context.target_function.name if enhanced_context.target_function else None,
                "usage_contexts_found": len(enhanced_context.usage_contexts),
                "context_summarized": enhanced_context.summary is not None
            }
            
            # Store results in context store
            await self.context_store.set("enhanced_debug_analysis", result)
            
            return result
            
        except Exception as e:
            print(f"Enhanced context analysis failed: {e}")
            # Fallback to original method
            return await self._fallback_debug_and_fix(error_input)

    async def _fallback_debug_and_fix(self, error_input: str) -> Dict[str, Any]:
        """Fallback to original debug method if enhanced analysis fails"""
        
        try:
            # Parse error to extract file information
            error_info = self.error_context_collector.parse_error_input(error_input)
            
            # Read the file content
            file_content = await self.error_context_collector._get_file_content(error_info.file_path)
            
            # Add line numbers for context
            numbered_content = self.repo_processor.add_line_numbers_to_content(file_content, 1)
            
            # Use original chain
            result = await self.chain.ainvoke({"code": numbered_content})
            
            # Add fallback indicator
            result["context_metadata"] = {
                "fallback_used": True,
                "error_file": error_info.file_path,
                "error_line": error_info.line_number
            }
            
            return result
            
        except Exception as e:
            return {
                "error": f"Both enhanced and fallback analysis failed: {e}",
                "line_numbers": [],
                "new_contents": [],
                "context_metadata": {"total_failure": True}
            }

    async def get_function_usage_analysis(self, function_name: str, file_path: str) -> Dict[str, Any]:
        """Get comprehensive usage analysis for a specific function"""
        
        try:
            # Analyze the function in its original file
            file_content = await self.error_context_collector._get_file_content(file_path)
            functions = await self.function_analyzer.find_all_functions(file_content, file_path)
            
            target_function = None
            for func in functions:
                if func.name == function_name:
                    target_function = func
                    break
            
            if not target_function:
                return {"error": f"Function {function_name} not found in {file_path}"}
            
            # Search for usage across codebase
            usage_contexts = await self.zoekt_search_manager.search_function_usage(
                function_name=function_name,
                original_file=file_path,
                language=target_function.language
            )
            
            # Find similar functions
            similar_functions = await self.zoekt_search_manager.search_similar_functions(
                target_function, max_results=5
            )
            
            return {
                "function": {
                    "name": target_function.name,
                    "file": target_function.file_path,
                    "language": target_function.language,
                    "signature": target_function.signature,
                    "parameters": target_function.parameters,
                    "documentation": target_function.documentation
                },
                "usage_analysis": {
                    "total_usages": len(usage_contexts),
                    "usage_by_type": self._group_usage_by_type(usage_contexts),
                    "files_using_function": list(set([u.file_path for u in usage_contexts])),
                    "top_usages": [self._format_usage_context(u) for u in usage_contexts[:5]]
                },
                "similar_functions": [
                    {
                        "file": sf.file_name,
                        "language": sf.language,
                        "score": getattr(sf, 'relevance_score', 0)
                    } for sf in similar_functions
                ]
            }
            
        except Exception as e:
            return {"error": f"Function usage analysis failed: {e}"}

    def _group_usage_by_type(self, usage_contexts: List) -> Dict[str, int]:
        """Group usage contexts by type and count them"""
        usage_types = {}
        for usage in usage_contexts:
            usage_type = usage.usage_type
            usage_types[usage_type] = usage_types.get(usage_type, 0) + 1
        return usage_types

    def _format_usage_context(self, usage_context) -> Dict[str, Any]:
        """Format usage context for API response"""
        return {
            "file": usage_context.file_path,
            "line": usage_context.line_number,
            "type": usage_context.usage_type,
            "score": usage_context.score,
            "context_preview": usage_context.context_before[-100:] + " ... " + usage_context.context_after[:100]
        }

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache and performance statistics"""
        return await self.cache_manager.get_cache_statistics()

    async def invalidate_file_cache(self, file_path: str) -> Dict[str, Any]:
        """Invalidate cache entries for a specific file (useful after file modifications)"""
        deleted_count = await self.cache_manager.invalidate_file(file_path)
        return {
            "file_path": file_path,
            "cache_entries_invalidated": deleted_count,
            "timestamp": time.time()
        }

    async def chat(self, user_message: str) -> str:
        """
        Send a user message to the primary model and return the text response.
        """
        await self.context_store.set("user_message", user_message)
        response = await self.primary_llm.ainvoke(user_message)
        return response.content

    async def analyze_codebase_patterns(self, 
                                      language: str = None, 
                                      max_files: int = 20) -> Dict[str, Any]:
        """Analyze common patterns and potential issues across the codebase"""
        
        try:
            # Search for common error patterns
            error_patterns = [
                "undefined", "null", "TypeError", "ReferenceError", 
                "SyntaxError", "ImportError", "AttributeError"
            ]
            
            pattern_results = {}
            for pattern in error_patterns:
                try:
                    results = await self.zoekt_client.search_by_text(pattern, max_docs=max_files)
                    pattern_results[pattern] = {
                        "occurrences": len(results),
                        "files": list(set([r.get("FileName", "") for r in results]))[:10]
                    }
                except:
                    pattern_results[pattern] = {"occurrences": 0, "files": []}
            
            return {
                "language_filter": language,
                "max_files_analyzed": max_files,
                "error_patterns": pattern_results,
                "analysis_timestamp": time.time(),
                "recommendations": self._generate_codebase_recommendations(pattern_results)
            }
            
        except Exception as e:
            return {"error": f"Codebase analysis failed: {e}"}

    def _generate_codebase_recommendations(self, pattern_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on pattern analysis"""
        recommendations = []
        
        for pattern, data in pattern_results.items():
            if data["occurrences"] > 5:
                recommendations.append(
                    f"High occurrence of '{pattern}' errors ({data['occurrences']} instances). "
                    f"Consider reviewing error handling in files: {', '.join(data['files'][:3])}"
                )
        
        return recommendations

    async def close(self):
        """Clean up resources"""
        try:
            await self.cache_manager.close()
            # Close other resources as needed
        except Exception as e:
            print(f"Error during cleanup: {e}")

# Compatibility function for existing usage
async def create_enhanced_ai_service(tenant_id: str, 
                                   redis_url: str, 
                                   model_configs: Dict[str, Dict[str, Any]], 
                                   **kwargs) -> EnhancedAIService:
    """Factory function to create enhanced AI service"""
    return EnhancedAIService(
        tenant_id=tenant_id,
        redis_url=redis_url,
        model_configs=model_configs,
        **kwargs
    ) 