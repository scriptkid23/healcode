import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .error_context_collector import EnhancedContext, FunctionContext, UsageContext, ErrorInfo


@dataclass
class SummaryChunk:
    """A chunk of content with its summary"""
    original_content: str
    summary: str
    relevance_score: float
    chunk_type: str  # 'function', 'usage', 'dependency'

class ContextSummarizer:
    """Intelligent context summarization using LLM"""
    
    def __init__(self, llm_client, max_chunk_size: int = 2000):
        self.llm_client = llm_client
        self.max_chunk_size = max_chunk_size
        
    async def summarize_context(self, 
                              enhanced_context: EnhancedContext, 
                              original_error_query: str) -> str:
        """Summarize enhanced context focusing on error-relevant information"""
        
        # Create chunks from different context sources
        chunks = await self._create_context_chunks(enhanced_context, original_error_query)
        
        # Summarize each chunk with error-focused prompts
        summary_chunks = []
        for chunk in chunks:
            summary = await self._summarize_chunk(chunk, enhanced_context.original_error)
            if summary:
                summary_chunks.append(SummaryChunk(
                    original_content=chunk['content'],
                    summary=summary,
                    relevance_score=chunk['relevance_score'],
                    chunk_type=chunk['type']
                ))
        
        # Combine summaries into final context
        final_summary = await self._combine_summaries(summary_chunks, enhanced_context.original_error)
        
        return final_summary
    
    async def _create_context_chunks(self, 
                                   enhanced_context: EnhancedContext, 
                                   original_error_query: str) -> List[Dict[str, Any]]:
        """Break down enhanced context into manageable chunks"""
        chunks = []
        
        # 1. Target function chunk (highest priority)
        if enhanced_context.target_function:
            func = enhanced_context.target_function
            chunk_content = f"""# Target Function: {func.name}
File: {func.file_path}
Lines: {func.start_line}-{func.end_line}
Language: {func.language}

## Function Signature
{func.signature}

## Implementation
{func.implementation}

## Documentation
{func.documentation or 'No documentation available'}

## Parameters
{', '.join(func.parameters or [])}
"""
            chunks.append({
                'content': chunk_content,
                'type': 'function',
                'relevance_score': 100.0,  # Highest priority
                'metadata': {'function_name': func.name, 'file_path': func.file_path}
            })
        
        # 2. Usage context chunks (grouped by file)
        usage_by_file = self._group_usages_by_file(enhanced_context.usage_contexts)
        
        for file_path, usages in usage_by_file.items():
            # Sort usages by score and take top ones
            sorted_usages = sorted(usages, key=lambda x: x.score, reverse=True)[:3]
            
            chunk_content = f"""# Usage in {file_path}

"""
            for usage in sorted_usages:
                chunk_content += f"""## Line {usage.line_number} - {usage.usage_type}

### Context Before
{usage.context_before}

### Context After  
{usage.context_after}

Score: {usage.score:.2f}

---
"""
            
            # Calculate relevance score based on usage scores and types
            avg_score = sum(u.score for u in sorted_usages) / len(sorted_usages)
            high_value_types = ['call', 'import', 'export', 'definition']
            type_bonus = sum(10 for u in sorted_usages if u.usage_type in high_value_types)
            relevance_score = avg_score + type_bonus
            
            chunks.append({
                'content': chunk_content,
                'type': 'usage',
                'relevance_score': relevance_score,
                'metadata': {'file_path': file_path, 'usage_count': len(sorted_usages)}
            })
        
        # 3. Dependency chunk (if significant)
        if enhanced_context.dependency_info and enhanced_context.dependency_info.get('imports'):
            imports = enhanced_context.dependency_info['imports']
            if len(imports) > 0:
                chunk_content = f"""# Dependencies and Imports

## Imports
{chr(10).join(imports)}

## Exports
{chr(10).join(enhanced_context.dependency_info.get('exports', []))}

## Dependencies
{chr(10).join(enhanced_context.dependency_info.get('dependencies', []))}
"""
                chunks.append({
                    'content': chunk_content,
                    'type': 'dependency',
                    'relevance_score': 30.0,  # Lower priority
                    'metadata': {'import_count': len(imports)}
                })
        
        # Sort chunks by relevance score
        chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return chunks
    
    def _group_usages_by_file(self, usage_contexts: List[UsageContext]) -> Dict[str, List[UsageContext]]:
        """Group usage contexts by file path"""
        grouped = {}
        for usage in usage_contexts:
            if usage.file_path not in grouped:
                grouped[usage.file_path] = []
            grouped[usage.file_path].append(usage)
        return grouped
    
    async def _summarize_chunk(self, chunk: Dict[str, Any], error_info: ErrorInfo) -> Optional[str]:
        """Summarize a single chunk focusing on error relevance"""
        
        # Create error-focused summarization prompt
        prompt = self._create_summarization_prompt(chunk, error_info)
        
        try:
            # Call LLM for summarization
            response = await self.llm_client.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"Summarization failed for {chunk['type']} chunk: {e}")
            return None
    
    def _create_summarization_prompt(self, chunk: Dict[str, Any], error_info: ErrorInfo) -> str:
        """Create error-focused summarization prompt"""
        
        chunk_type = chunk['type']
        content = chunk['content']
        
        base_context = f"""You are analyzing code to help fix this error:
- Error Type: {error_info.error_type}
- Variable/Symbol: {error_info.variable_or_symbol}
- File: {error_info.file_path}
- Line: {error_info.line_number}

"""
        
        if chunk_type == 'function':
            prompt = base_context + f"""
Summarize the following function implementation, focusing on:
1. What the function does and its purpose
2. How it relates to the error (especially the variable '{error_info.variable_or_symbol}')
3. Function parameters and their usage
4. Any potential issues or error-prone areas
5. Key implementation details that might cause or fix the error

Keep the summary concise but include ALL information relevant to understanding and fixing the error.

Function to analyze:
{content}

Summary:"""

        elif chunk_type == 'usage':
            prompt = base_context + f"""
Summarize how the function is used in other files, focusing on:
1. Different usage patterns and contexts
2. How the variable '{error_info.variable_or_symbol}' is handled in each usage
3. Common patterns that might reveal the correct usage
4. Any usage that might show how to fix the error
5. Differences in how the function is called or used

Keep the summary concise but include patterns that could help fix the error.

Usage examples to analyze:
{content}

Summary:"""

        elif chunk_type == 'dependency':
            prompt = base_context + f"""
Summarize the dependencies and imports, focusing on:
1. Where the variable '{error_info.variable_or_symbol}' might be defined
2. Missing imports that could cause the error
3. External dependencies that provide the missing functionality
4. Import/export patterns relevant to the error

Keep the summary focused on import-related causes of the error.

Dependencies to analyze:
{content}

Summary:"""
        
        else:
            prompt = base_context + f"""
Summarize this code context focusing on information relevant to fixing the error:

{content}

Summary:"""
        
        return prompt
    
    async def _combine_summaries(self, 
                                summary_chunks: List[SummaryChunk], 
                                error_info: ErrorInfo) -> str:
        """Combine individual summaries into a comprehensive context summary"""
        
        if not summary_chunks:
            return "No context available for summarization."
        
        # Sort by relevance score
        summary_chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Create comprehensive summary prompt
        summaries_text = ""
        for i, chunk in enumerate(summary_chunks, 1):
            summaries_text += f"""
## {chunk.chunk_type.title()} Context (Relevance: {chunk.relevance_score:.1f})
{chunk.summary}

"""
        
        final_prompt = f"""You are helping to fix this code error:
- Error: {error_info.error_type}
- Variable: {error_info.variable_or_symbol}
- Location: {error_info.file_path}:{error_info.line_number}

Based on the following context summaries, create a comprehensive analysis that:
1. Explains what likely caused the error
2. Provides the most relevant context for fixing it
3. Highlights key patterns and usage examples
4. Suggests the most likely solution approach

Context summaries:
{summaries_text}

Provide a comprehensive context analysis that will help an AI model accurately fix this error:"""
        
        try:
            response = await self.llm_client.ainvoke(final_prompt)
            return response.content.strip()
        except Exception as e:
            print(f"Final summarization failed: {e}")
            # Fallback: concatenate summaries
            return self._fallback_summary(summary_chunks, error_info)
    
    def _fallback_summary(self, summary_chunks: List[SummaryChunk], error_info: ErrorInfo) -> str:
        """Fallback summary when LLM summarization fails"""
        result = f"""# Context Analysis for Error: {error_info.error_type}

**Error Location:** {error_info.file_path}:{error_info.line_number}
**Variable/Symbol:** {error_info.variable_or_symbol}

"""
        
        for chunk in summary_chunks:
            result += f"""
## {chunk.chunk_type.title()} Context
{chunk.summary}

"""
        
        return result
    
    async def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        # Rough estimation: 1 token ≈ 4 characters for English text
        # This can be replaced with a proper tokenizer if needed
        return len(text) // 4
    
    async def should_summarize(self, enhanced_context: EnhancedContext, max_tokens: int = 8000) -> bool:
        """Determine if context needs summarization based on size"""
        total_size = 0
        
        if enhanced_context.target_function:
            total_size += len(enhanced_context.target_function.implementation)
            if enhanced_context.target_function.documentation:
                total_size += len(enhanced_context.target_function.documentation)
        
        for usage in enhanced_context.usage_contexts:
            total_size += len(usage.context_before) + len(usage.context_after)
        
        if enhanced_context.dependency_info:
            for key, value in enhanced_context.dependency_info.items():
                if isinstance(value, list):
                    total_size += sum(len(str(item)) for item in value)
                elif isinstance(value, str):
                    total_size += len(value)
        
        estimated_tokens = await self.estimate_token_count(str(total_size))
        return estimated_tokens > max_tokens
    
    async def adaptive_summarize(self, 
                               enhanced_context: EnhancedContext, 
                               target_tokens: int = 6000) -> str:
        """Adaptively summarize context to fit within target token count"""
        
        current_tokens = await self.estimate_token_count(
            enhanced_context.target_function.implementation if enhanced_context.target_function else ""
        )
        
        if current_tokens <= target_tokens:
            # No summarization needed
            return self._format_full_context(enhanced_context)
        
        # Progressive summarization
        if current_tokens <= target_tokens * 1.5:
            # Light summarization - keep function full, summarize usage
            return await self._light_summarization(enhanced_context)
        else:
            # Full summarization
            return await self.summarize_context(enhanced_context, "")
    
    def _format_full_context(self, enhanced_context: EnhancedContext) -> str:
        """Format context without summarization"""
        formatted = f"""# Error Context Analysis

## Original Error
- Type: {enhanced_context.original_error.error_type}
- Variable: {enhanced_context.original_error.variable_or_symbol}
- Location: {enhanced_context.original_error.file_path}:{enhanced_context.original_error.line_number}

"""
        if enhanced_context.target_function:
            func = enhanced_context.target_function
            formatted += f"""## Target Function: {func.name}
```{func.language}
{func.implementation}
```

"""
        
        if enhanced_context.usage_contexts:
            formatted += "## Function Usage Examples\n"
            for usage in enhanced_context.usage_contexts[:3]:
                formatted += f"""### {usage.file_path}:{usage.line_number} ({usage.usage_type})
```
{usage.context_before}
{usage.context_after}
```

"""
        
        return formatted
    
    async def _light_summarization(self, enhanced_context: EnhancedContext) -> str:
        """Light summarization - keep function full, summarize usage"""
        result = self._format_full_context(enhanced_context)
        
        if len(enhanced_context.usage_contexts) > 3:
            # Summarize additional usage contexts
            additional_usages = enhanced_context.usage_contexts[3:]
            usage_summary = await self._summarize_usage_list(additional_usages, enhanced_context.original_error)
            result += f"\n## Additional Usage Patterns\n{usage_summary}\n"
        
        return result
    
    async def _summarize_usage_list(self, usages: List[UsageContext], error_info: ErrorInfo) -> str:
        """Summarize a list of usage contexts"""
        usage_by_type = {}
        for usage in usages:
            if usage.usage_type not in usage_by_type:
                usage_by_type[usage.usage_type] = []
            usage_by_type[usage.usage_type].append(usage)
        
        summary = ""
        for usage_type, usage_list in usage_by_type.items():
            files = [u.file_path for u in usage_list]
            summary += f"- **{usage_type}**: Found in {len(files)} files: {', '.join(files[:3])}"
            if len(files) > 3:
                summary += f" and {len(files) - 3} others"
            summary += "\n"
        
        return summary 