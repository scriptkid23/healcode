import re
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import hashlib
import time

@dataclass
class ErrorInfo:
    """Structured error information extracted from input"""
    error_type: str
    variable_or_symbol: str
    file_path: str
    line_number: int
    column_number: Optional[int] = None
    repository: Optional[str] = None

@dataclass
class FunctionContext:
    """Context information about a function"""
    name: str
    signature: str
    implementation: str
    start_line: int
    end_line: int
    file_path: str
    language: str
    documentation: Optional[str] = None
    parameters: List[str] = None

@dataclass
class UsageContext:
    """Context about function usage in other files"""
    file_path: str
    line_number: int
    context_before: str
    context_after: str
    usage_type: str  # 'call', 'import', 'reference'
    score: float

@dataclass
class EnhancedContext:
    """Complete enhanced context for AI analysis"""
    original_error: ErrorInfo
    target_function: FunctionContext
    usage_contexts: List[UsageContext]
    dependency_info: Dict[str, Any]
    summary: Optional[str] = None
    processing_time_ms: int = 0
    cache_hit: bool = False

class ErrorContextCollector:
    """Main orchestrator for collecting enhanced context around code errors"""
    
    def __init__(self, 
                 zoekt_client,
                 function_analyzer,
                 context_summarizer,
                 cache_manager,
                 zoekt_search_manager,
                 max_files: int = 10,
                 max_processing_time: int = 600):  # 10 minutes
        self.zoekt_client = zoekt_client
        self.function_analyzer = function_analyzer
        self.context_summarizer = context_summarizer
        self.cache_manager = cache_manager
        self.zoekt_search_manager = zoekt_search_manager
        self.max_files = max_files
        self.max_processing_time = max_processing_time

    def parse_error_input(self, error_input: str) -> ErrorInfo:
        """
        Parse various error input formats:
        - "input undefined error main.js 33:12"
        - "TypeError: Cannot read property 'value' of null at main.js:33:12"
        - "main.js:33:12 - error TS2304: Cannot find name 'input'"
        """
        # Pattern 1: "variable_name error_type error file_path line:column"
        pattern1 = r"(\w+)\s+(\w+)\s+error\s+([^\s]+)\s+(\d+):(\d+)"
        match = re.search(pattern1, error_input)
        if match:
            return ErrorInfo(
                variable_or_symbol=match.group(1),
                error_type=match.group(2),
                file_path=match.group(3),
                line_number=int(match.group(4)),
                column_number=int(match.group(5))
            )
        
        # Pattern 2: "file_path:line:column - error message"
        pattern2 = r"([^\s:]+):(\d+):(\d+)\s*-\s*.*?(\w+)"
        match = re.search(pattern2, error_input)
        if match:
            return ErrorInfo(
                file_path=match.group(1),
                line_number=int(match.group(2)),
                column_number=int(match.group(3)),
                error_type=match.group(4),
                variable_or_symbol=""  # Will be extracted from context
            )
        
        # Pattern 3: "ErrorType: message at file_path:line:column"
        pattern3 = r"(\w+Error):\s*.*?\s+at\s+([^\s:]+):(\d+):(\d+)"
        match = re.search(pattern3, error_input)
        if match:
            return ErrorInfo(
                error_type=match.group(1),
                file_path=match.group(2),
                line_number=int(match.group(3)),
                column_number=int(match.group(4)),
                variable_or_symbol=""  # Will be extracted from context
            )
        
        # Fallback: try to extract basic info
        file_match = re.search(r"([^\s:]+\.[a-zA-Z]+)", error_input)
        line_match = re.search(r":(\d+)", error_input)
        
        if file_match and line_match:
            return ErrorInfo(
                file_path=file_match.group(1),
                line_number=int(line_match.group(1)),
                error_type="unknown",
                variable_or_symbol=""
            )
        
        raise ValueError(f"Unable to parse error input: {error_input}")

    def generate_cache_key(self, error_info: ErrorInfo, file_content_hash: str) -> str:
        """Generate cache key based on error pattern and file content"""
        key_data = f"{error_info.file_path}:{error_info.line_number}:{error_info.error_type}:{file_content_hash}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def collect_enhanced_context(self, error_input: str) -> EnhancedContext:
        """Main method to collect enhanced context for an error"""
        start_time = time.time()
        
        try:
            # Parse error input
            error_info = self.parse_error_input(error_input)
            
            # Check cache first
            file_content = await self._get_file_content(error_info.file_path)
            file_hash = hashlib.md5(file_content.encode()).hexdigest()
            cache_key = self.generate_cache_key(error_info, file_hash)
            
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                cached_result.cache_hit = True
                return cached_result
            
            # Create timeout context
            async with asyncio.timeout(self.max_processing_time):
                # First analyze target function, then search usage with function info
                target_function = await self._analyze_target_function(error_info, file_content)
                
                # Execute remaining tasks in parallel with function info
                context_tasks = await asyncio.gather(
                    self._search_function_usage(error_info, target_function),
                    self._extract_dependency_info(error_info),
                    return_exceptions=True
                )
                
                usage_contexts = context_tasks[0] if not isinstance(context_tasks[0], Exception) else []
                dependency_info = context_tasks[1] if not isinstance(context_tasks[1], Exception) else {}
                
                # Create enhanced context
                enhanced_context = EnhancedContext(
                    original_error=error_info,
                    target_function=target_function,
                    usage_contexts=usage_contexts,
                    dependency_info=dependency_info,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    cache_hit=False
                )
                
                # Summarize if context is too large
                if self._should_summarize_context(enhanced_context):
                    enhanced_context.summary = await self.context_summarizer.summarize_context(
                        enhanced_context, error_input
                    )
                
                # Cache the result
                await self.cache_manager.set(cache_key, enhanced_context, ttl=3600)  # 1 hour
                
                return enhanced_context
                
        except asyncio.TimeoutError:
            # Return partial context if timeout
            return EnhancedContext(
                original_error=error_info,
                target_function=None,
                usage_contexts=[],
                dependency_info={"error": "Timeout during context collection"},
                processing_time_ms=self.max_processing_time * 1000,
                cache_hit=False
            )
        except Exception as e:
            # Return error context
            return EnhancedContext(
                original_error=error_info if 'error_info' in locals() else None,
                target_function=None,
                usage_contexts=[],
                dependency_info={"error": str(e)},
                processing_time_ms=int((time.time() - start_time) * 1000),
                cache_hit=False
            )

    async def _get_file_content(self, file_path: str) -> str:
        """Get file content, handling both absolute and relative paths"""
        try:
            # Try relative to current working directory first
            path = Path(file_path)
            if not path.is_absolute():
                # Try relative to codebase directory
                codebase_path = Path("codebase") / file_path
                if codebase_path.exists():
                    path = codebase_path
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise FileNotFoundError(f"Cannot read file {file_path}: {e}")

    async def _analyze_target_function(self, error_info: ErrorInfo, file_content: str) -> Optional[FunctionContext]:
        """Analyze the function containing the error"""
        return await self.function_analyzer.analyze_function_at_line(
            file_content, error_info.file_path, error_info.line_number
        )

    async def _search_function_usage(self, error_info: ErrorInfo, target_function: Optional[FunctionContext] = None) -> List[UsageContext]:
        """Search for function usage across the repository"""
        if not target_function:
            return []
        
        # Use ZoektSearchManager to find function usage
        language = target_function.language
        usage_contexts = await self.zoekt_search_manager.search_function_usage(
            function_name=target_function.name,
            original_file=error_info.file_path,
            language=language
        )
        
        return usage_contexts

    async def _extract_dependency_info(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Extract dependency and import information"""
        # Will be implemented to analyze imports, requires, etc.
        return {"imports": [], "exports": [], "dependencies": []}

    def _should_summarize_context(self, context: EnhancedContext) -> bool:
        """Determine if context should be summarized due to size"""
        # Estimate token count (rough approximation: 1 token ≈ 4 characters)
        total_size = 0
        if context.target_function:
            total_size += len(context.target_function.implementation)
        
        for usage in context.usage_contexts:
            total_size += len(usage.context_before) + len(usage.context_after)
        
        # Summarize if estimated tokens > 8000 (to leave room for other prompt content)
        estimated_tokens = total_size // 4
        return estimated_tokens > 8000

    def format_context_for_ai(self, context: EnhancedContext) -> str:
        """Format enhanced context for AI consumption"""
        if context.summary:
            return context.summary
        
        formatted = f"""# Enhanced Context for Error Analysis

## Original Error
- Type: {context.original_error.error_type}
- Variable/Symbol: {context.original_error.variable_or_symbol}
- Location: {context.original_error.file_path}:{context.original_error.line_number}

## Target Function Context
"""
        if context.target_function:
            formatted += f"""
- Function: {context.target_function.name}
- File: {context.target_function.file_path}
- Lines: {context.target_function.start_line}-{context.target_function.end_line}
- Language: {context.target_function.language}

```{context.target_function.language}
{context.target_function.implementation}
```
"""
        
        if context.usage_contexts:
            formatted += "\n## Function Usage in Other Files\n"
            for i, usage in enumerate(context.usage_contexts[:5], 1):  # Limit to top 5
                formatted += f"""
### Usage {i}: {usage.file_path}:{usage.line_number}
```
{usage.context_before}
>>> {usage.usage_type} <<<
{usage.context_after}
```
"""
        
        if context.dependency_info.get("imports"):
            formatted += f"\n## Dependencies\n{context.dependency_info['imports']}\n"
        
        return formatted 