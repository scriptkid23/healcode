import os
import re
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import hashlib
import time

from indexer.zoekt_client import ZoektClient

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
class DependencyInfo:
    """
    Docstring for DependencyInfo
    
    :var formats: Description
    """
    import_name: str
    resolved_path: str
    line_number: int

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
class Dependent:
    """
    Docstring for Dependent
    
    :var formats: Description
    """
    file_path: str
    dependent_files: List[str]
    import_dependencies: List[DependencyInfo]
    usage_contexts: List[UsageContext]
    @property
    def import_dependencies_count(self) -> int:
        return len(self.import_dependencies)
    
    @property
    def dependent_files_count(self) -> int:
        return len(self.dependent_files)

    @property
    def usage_contexts_count(self) -> int:
        return len(self.usage_contexts)

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


MAX_CONCURRENT_TASKS = 3
api_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
class ErrorContextCollector:
    """Main orchestrator for collecting enhanced context around code errors"""
    
    def __init__(self, 
                 zoekt_client:ZoektClient,
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

    async def parse_error_input(self, error_input: str, path_local_repo: str) -> List[ErrorInfo]:
        """
        Parse various error input formats:
        - "input undefined error main.js 33:12"
        - "TypeError: Cannot read property 'value' of null at main.js:33:12"
        - "main.js:33:12 - error TS2304: Cannot find name 'input'"
        """
        # Setup return
        error_input = error_input.replace("\n", " ")
        errors_list: List[ErrorInfo] = []

        # Pattern 1: "variable_name error_type error file_path line:column"
        # pattern1 = r"(\w+)\s+(\w+)\s+error\s+([^\s]+)\s+(\d+):(\d+)"
        # match = re.search(pattern1, error_input)
        # if match:
        #     return ErrorInfo(
        #         variable_or_symbol=match.group(1),
        #         error_type=match.group(2),
        #         file_path=match.group(3),
        #         line_number=int(match.group(4)),
        #         column_number=int(match.group(5))
        #     )
        
        # Pattern 2: "file_path:line:column - error message"
        # pattern2 = r"([^\s:]+):(\d+):(\d+)\s*-\s*.*?(\w+)"
        # match = re.search(pattern2, error_input)
        # if match:
        #     return ErrorInfo(
        #         file_path=match.group(1),
        #         line_number=int(match.group(2)),
        #         column_number=int(match.group(3)),
        #         error_type=match.group(4),
        #         variable_or_symbol=""  # Will be extracted from context
        #     )
        
        # Pattern 3: "ErrorType: message at file_path:line:column"
        # pattern3 = r"(\w+Error):\s*.*?\s+at\s+([^\s:]+):(\d+):(\d+)"
        # match = re.search(pattern3, error_input)
        # if match:
        #     return ErrorInfo(
        #         error_type=match.group(1),
        #         file_path=match.group(2),
        #         line_number=int(match.group(3)),
        #         column_number=int(match.group(4)),
        #         variable_or_symbol=""  # Will be extracted from context
        #     )
        # Pattern4: Python
        pattern4 = r'File "([^"]+)", line (\d+)[\s\S]*?(\w+Error):'
        matches = re.finditer(pattern4, error_input)
        if matches:
            for match in matches:
                file_path = "./codebase/" + await self._find_correct_file_path(path_local_repo, match.group(1))
                error = ErrorInfo(
                    file_path=file_path,
                    line_number=int(match.group(2)),
                    error_type=match.group(3),
                    variable_or_symbol="",
                    column_number=None
                )
                errors_list.append(error)

        pattern5 = r"([^:\s]+):(\d+): \w+: (.*?)\s+.*?\^"
        matches = re.finditer(pattern5, error_input)
        if matches:
            for match in matches:
                file_path = "./codebase/" + await self._find_correct_file_path(path_local_repo, match.group(1))
                error = ErrorInfo(
                    file_path=file_path, # type: ignore
                    line_number=int(match.group(2)),
                    error_type=match.group(3).strip(), # Đây là thông điệp lỗi
                    variable_or_symbol="",
                    column_number=None 
                )
                errors_list.append(error)
            return errors_list
        
        # Fallback: try to extract basic info
        file_match = re.search(r"([^\s:]+\.[a-zA-Z]+)", error_input)
        line_match = re.search(r":(\d+)", error_input)

        if file_match and line_match:
            return [ErrorInfo(
                file_path=file_match.group(1),
                line_number=int(line_match.group(1)),
                error_type="unknown",
                variable_or_symbol=""
            )]

        print(f"Unable to parse error input: {error_input}")
        raise ValueError(f"Unable to parse error input: {error_input}")

    def generate_cache_key(self, error_info: ErrorInfo, file_content_hash: str) -> str:
        """Generate cache key based on error pattern and file content"""
        key_data = f"{error_info.file_path}:{error_info.line_number}:{error_info.error_type}:{file_content_hash}"
        return hashlib.md5(key_data.encode()).hexdigest()


    async def collect_enhanced_context(self, error_input: str, workspace_path: str):
        """
        Main method to coordinate the collection of enhanced context for multiple errors.
        This method handles the error_info array by processing each entry in parallel.
        """
        start_time = time.time()
        
        try:
            # Parse error input which now returns a list of error objects
            error_list = await self.parse_error_input(error_input, workspace_path)
            
            if not error_list:
                return []

            # Create tasks for each error in the list to process them concurrently
            # We pass the original input for summarization context
            tasks = [self._process_single_error_context(info, error_input) for info in error_list]
            
            # Execute all collection tasks in parallel
            # return_exceptions=True ensures one failure doesn't crash the whole batch
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and return only successfully collected EnhancedContext objects
            valid_results = [r for r in results if not isinstance(r, Exception)]
            
            return valid_results
            
        except Exception as e:
            print(f"Failed to coordinate enhanced context collection: {e}")
            return []

    async def _process_single_error_context(self, error_info, original_input):
        """
        Internal logic to collect context for a single error object.
        Uses a semaphore to control concurrency and avoid API rate limits.
        """
        # Use semaphore to guard the processing logic
        async with api_semaphore:
            start_time = time.time()
            try:
                # Fetch file content for hash generation and analysis
                file_content = await self._get_file_content(error_info.file_path)
                file_hash = hashlib.md5(file_content.encode()).hexdigest()
                
                # Check cache to avoid redundant expensive operations
                cache_key = self.generate_cache_key(error_info, file_hash)
                cached_result = await self.cache_manager.get(cache_key)
                
                if cached_result:
                    cached_result.cache_hit = True
                    return cached_result
                
                # Apply processing timeout to prevent hanging tasks
                async with asyncio.timeout(self.max_processing_time):
                    # Phase 1: Analyze the specific target function where the error occurred
                    target_function = await self._analyze_target_function(error_info, file_content)
                    
                    # Phase 2: Execute usage search and dependency extraction in parallel
                    context_tasks = await asyncio.gather(
                        self._search_function_usage(error_info, target_function),
                        self._extract_dependency_info(error_info),
                        return_exceptions=True
                    )
                    
                    # Safely extract results or default to empty values on failure
                    usage_contexts = context_tasks[0] if not isinstance(context_tasks[0], Exception) else []
                    dependency_info = context_tasks[1] if not isinstance(context_tasks[1], Exception) else {}
                    
                    # Initialize the context object with all gathered data
                    enhanced_context = EnhancedContext(
                        original_error=error_info,
                        target_function=target_function,
                        usage_contexts=usage_contexts,
                        dependency_info=dependency_info,
                        processing_time_ms=int((time.time() - start_time) * 1000),
                        cache_hit=False
                    )
                    
                    # Phase 3: Summarize if the collected data exceeds token limits
                    if self._should_summarize_context(enhanced_context):
                        enhanced_context.summary = await self.context_summarizer.summarize_context(
                            enhanced_context, original_input
                        )
                    
                    # Store processed result in cache for 1 hour
                    await self.cache_manager.set(cache_key, enhanced_context, ttl=3600)
                    
                    return enhanced_context
                    
            except Exception as e:
                print(f"Error collecting context for {error_info.file_path}: {e}")
                raise e

    async def _find_correct_file_path(self, repo_name: str, path_error: str):
        # This is a fast, sync string operation.
        path_guess = self._normalize_path_for_zoekt(repo_name, path_error)
        
        # Try to find the file using the full guessed path.
        results = await self.zoekt_client.search_by_filename(
            filename=path_guess
        )

        if results and len(results) == 1:
            return results[0]["FileName"]

        # try a fallback search using only the bare filename.
        print(f"Could not find '{path_guess}'. Trying fallback...")
        
        fallback_name = os.path.basename(path_guess)
        
        results_fallback = await self.zoekt_client.search_by_filename(
            filename=fallback_name
        )
        if results_fallback and len(results_fallback) > 0:
            return results_fallback[0]["FileName"]
        
        # Give up, return the best guess we had
        return path_guess
    
    def _normalize_path_for_zoekt(self, repo_name: str, path_error: str) -> str:
        """
        Cleans the error path. NO I/O, NO 'await'. Just string processing.
        """
        # ... (Implementation from previous message) ...
        base_repo_name = repo_name.split('/')[-1].split('\\')[-1]
        clean_path = path_error.replace("\\", "/")
        clean_path = re.sub(r":\d+.*$", "", clean_path).strip()

        if base_repo_name in clean_path:
            repo_index = clean_path.find(base_repo_name)
            start_index = repo_index + len(base_repo_name)
            return clean_path[start_index:].lstrip("/")
        else:
            return clean_path.lstrip("./")

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
    
    def format_json_return(self):
        return f"""
STRICT OUTPUT FORMAT:
- Return only the JSON value that conforms to the schema. Do not include any additional text, explanations, or wrappers.
- The response must be a single, valid JSON object.

Here is the output schema:

{{
  "$defs": {{
    "FileFixDetail": {{
      "properties": {{
        "file_path": {{
          "description": "The relative path to the file that needs to be fixed.",
          "title": "File Path",
          "type": "string"
        }},
        "line_numbers": {{
          "description": "A list of line numbers in this file that need to be replaced.",
          "items": {{"type": "integer"}},
          "title": "Line Numbers",
          "type": "array"
        }},
        "new_contents": {{
          "description": "A corresponding list of new code lines. The line at line_numbers[i] must be replaced with new_contents[i].",
          "items": {{"type": "string"}},
          "title": "New Contents",
          "type": "array"
        }}
      }},
      "required": ["file_path", "line_numbers", "new_contents"],
      "title": "FileFixDetail",
      "type": "object"
    }},
    "CodeFixMetadata": {{
      "properties": {{
        "total_lines_analyzed": {{
          "description": "The total number of lines analyzed.",
          "title": "Total Lines Analyzed",
          "type": "integer"
        }},
        "processing_time_ms": {{
          "description": "The time in milliseconds it took the model to process the request.",
          "title": "Processing Time Ms",
          "type": "integer"
        }},
        "model_used": {{
          "description": "The name of the language model used.",
          "title": "Model Used",
          "type": "string"
        }}
      }},
      "required": ["total_lines_analyzed", "processing_time_ms", "model_used"],
      "title": "CodeFixMetadata",
      "type": "object"
    }}
  }},
  "properties": {{
    "file_fixes": {{
      "description": "A list of files to fix. Each item contains the file path and the corresponding lists of lines and new content.",
      "items": {{"$ref": "#/$defs/FileFixDetail"}},
      "title": "File Fixes",
      "type": "array"
    }},
    "explanation": {{
      "description": "A high-level, human-readable summary from the AI explaining what was wrong and how it was fixed.",
      "title": "Explanation",
      "type": "string"
    }},
    "metadata": {{
      "$ref": "#/$defs/CodeFixMetadata"
    }}
  }},
  "required": ["file_fixes", "explanation", "metadata"]
}}
"""