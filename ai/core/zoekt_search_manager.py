import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time

from indexer.zoekt_client import ZoektClient
from .error_context_collector import UsageContext, FunctionContext, ErrorInfo

class ZoektSearchManager:
    """Enhanced Zoekt client with smart search and ranking for function usage analysis"""
    
    def __init__(self, zoekt_client: ZoektClient, max_files: int = 10):
        self.zoekt_client = zoekt_client
        self.max_files = max_files
        self.file_modification_cache = {}
        
    async def search_function_usage(self, 
                                  function_name: str, 
                                  original_file: str,
                                  language: Optional[str] = None) -> List[UsageContext]:
        """Search for function usage across repository with intelligent ranking"""
        
        # Build search queries for different usage patterns
        search_queries = self._build_function_search_queries(function_name, language)
        
        all_results = []
        for query in search_queries:
            try:
                # ZoektClient already returns parsed results
                results = await self.zoekt_client.search_by_text(query, max_docs=self.max_files)
                all_results.extend(results)
            except Exception as e:
                print(f"Search failed for query '{query}': {e}")
                continue
        
        # Remove duplicates and filter results
        unique_results = self._deduplicate_results(all_results)
        filtered_results = self._filter_relevant_results(unique_results, original_file, function_name)
        
        # Convert to UsageContext with ranking
        usage_contexts = []
        for result in filtered_results[:self.max_files]:
            contexts = await self._extract_usage_contexts(result, function_name, original_file)
            usage_contexts.extend(contexts)
        
        # Sort by relevance score
        usage_contexts.sort(key=lambda x: x.score, reverse=True)
        return usage_contexts[:self.max_files]
    
    def _build_function_search_queries(self, function_name: str, language: Optional[str] = None) -> List[str]:
        """Build intelligent search queries for different function usage patterns"""
        queries = []
        
        # Basic function name search
        queries.append(function_name)
        
        if language == 'javascript':
            # JavaScript/TypeScript patterns
            queries.extend([
                f"{function_name}(",           # Function call
                f"const {function_name}",      # Assignment
                f"let {function_name}",        # Assignment
                f"import {function_name}",     # Import
                f"export {function_name}",     # Export
                f".{function_name}(",          # Method call
                f"{function_name}:",           # Object property
                f"= {function_name}",          # Assignment
            ])
            
        elif language == 'python':
            # Python patterns
            queries.extend([
                f"def {function_name}",        # Function definition
                f"{function_name}(",           # Function call
                f"import {function_name}",     # Import
                f"from .* import.*{function_name}",  # From import
                f"self.{function_name}(",      # Method call
                f"= {function_name}",          # Assignment
            ])
            
        elif language in ['java', 'c', 'cpp']:
            # Java/C/C++ patterns
            queries.extend([
                f"{function_name}(",           # Function call
                f"public.*{function_name}",    # Public method
                f"private.*{function_name}",   # Private method
                f"static.*{function_name}",    # Static method
            ])
        
        else:
            # Generic patterns for other languages
            queries.extend([
                f"{function_name}(",           # Function call
                f"= {function_name}",          # Assignment
                f"import {function_name}",     # Import (if supported)
            ])
        
        return queries
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on file path and checksum"""
        seen = set()
        unique_results = []
        
        for result in results:
            file_name = result.get("FileName", "")
            checksum = result.get("Checksum", "")
            key = (file_name, checksum)
            
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        return unique_results
    
    def _filter_relevant_results(self, 
                                results: List[Dict[str, Any]], 
                                original_file: str, 
                                function_name: str) -> List[Dict[str, Any]]:
        """Filter and rank results by relevance"""
        filtered = []
        
        for result in results:
            file_name = result.get("FileName", "")
            
            # Skip the original file (we already have its context)
            if file_name == original_file:
                continue
            
            # Check if result actually contains meaningful usage
            if self._has_meaningful_usage(result, function_name):
                # Calculate relevance score
                score = self._calculate_relevance_score(result, original_file, function_name)
                result["relevance_score"] = score
                filtered.append(result)
        
        # Sort by relevance score
        filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return filtered
    
    def _has_meaningful_usage(self, result: Dict[str, Any], function_name: str) -> bool:
        """Check if the search result contains meaningful function usage"""
        line_matches = result.get("LineMatches", [])
        
        for line_match in line_matches:
            # ZoektClient already decodes the line content in LineMatches
            # We can get the actual line content from the Content field or reconstruct it
            line_content = self._get_line_content_from_match(line_match, result)
            
            # Skip comments and strings (basic check)
            if (line_content.strip().startswith('//') or 
                line_content.strip().startswith('#') or
                line_content.strip().startswith('/*')):
                continue
            
            # Check for actual function usage patterns
            usage_patterns = [
                rf'\b{function_name}\s*\(',           # Function call
                rf'=\s*{function_name}\b',            # Assignment
                rf'import.*{function_name}\b',        # Import
                rf'export.*{function_name}\b',        # Export
                rf'\.{function_name}\s*\(',           # Method call
                rf'{function_name}\s*:',              # Object property
            ]
            
            for pattern in usage_patterns:
                if re.search(pattern, line_content):
                    return True
        
        return False
    
    def _get_line_content_from_match(self, line_match: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Extract line content from line match or file content"""
        # If ZoektClient already decoded line content, use it
        # Otherwise extract from file content using line number
        content = result.get("Content", "")
        if content:
            lines = content.split('\n')
            line_number = line_match.get("LineNumber", 1)
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1]
        
        # Fallback: try to decode Line field if available
        import base64
        line_b64 = line_match.get("Line", "")
        if line_b64:
            try:
                return base64.b64decode(line_b64).decode("utf-8")
            except Exception:
                return ""
        
        return ""
    
    def _calculate_relevance_score(self, 
                                  result: Dict[str, Any], 
                                  original_file: str, 
                                  function_name: str) -> float:
        """Calculate relevance score for ranking results"""
        score = 0.0
        
        # Base score from Zoekt
        file_score = result.get("Score", 0)
        score += file_score / 1000000  # Normalize Zoekt score
        
        # Language match bonus
        original_ext = Path(original_file).suffix.lower()
        result_file = result.get("FileName", "")
        result_ext = Path(result_file).suffix.lower()
        if original_ext == result_ext:
            score += 20.0  # Same language bonus
        
        # Recent modification bonus (if we have file timestamps)
        recency_score = self._get_file_recency_score(result_file)
        score += recency_score
        
        # Directory proximity bonus
        proximity_score = self._get_directory_proximity_score(original_file, result_file)
        score += proximity_score
        
        # Usage type scoring
        line_matches = result.get("LineMatches", [])
        for line_match in line_matches:
            line_content = self._get_line_content_from_match(line_match, result)
            usage_type_score = self._get_usage_type_score(line_content, function_name)
            score += usage_type_score
        
        # Match count bonus
        score += len(line_matches) * 2.0
        
        return score
    
    def _get_file_recency_score(self, file_path: str) -> float:
        """Get score based on file modification recency (mock implementation)"""
        # In real implementation, you would check file modification times
        # For now, prioritize files in common directories
        common_dirs = ['src', 'lib', 'components', 'utils', 'services']
        for dir_name in common_dirs:
            if dir_name in file_path:
                return 10.0
        return 0.0
    
    def _get_directory_proximity_score(self, original_file: str, result_file: str) -> float:
        """Get score based on directory proximity"""
        original_parts = Path(original_file).parts
        result_parts = Path(result_file).parts
        
        # Same directory bonus
        if len(original_parts) > 1 and len(result_parts) > 1:
            if original_parts[:-1] == result_parts[:-1]:  # Same directory
                return 15.0
            
            # Parent directory bonus
            common_depth = 0
            for i in range(min(len(original_parts), len(result_parts)) - 1):
                if original_parts[i] == result_parts[i]:
                    common_depth += 1
                else:
                    break
            
            if common_depth > 0:
                return 5.0 * common_depth
        
        return 0.0
    
    def _get_usage_type_score(self, line_content: str, function_name: str) -> float:
        """Get score based on type of function usage"""
        line = line_content.lower()
        func_name = function_name.lower()
        
        # Import/export statements (high value)
        if re.search(rf'import.*{func_name}|export.*{func_name}', line):
            return 10.0
        
        # Function calls (high value)
        if re.search(rf'{func_name}\s*\(', line):
            return 8.0
        
        # Method calls (medium value)
        if re.search(rf'\.{func_name}\s*\(', line):
            return 6.0
        
        # Assignment (medium value)
        if re.search(rf'=\s*{func_name}\b', line):
            return 5.0
        
        # Type/interface usage (lower value)
        if re.search(rf':\s*{func_name}\b|<{func_name}>', line):
            return 3.0
        
        # Comment/documentation (lowest value)
        if line.strip().startswith(('/', '#', '*')):
            return 1.0
        
        return 2.0  # Default for any other usage
    
    def _get_context_around_line(self, result: Dict[str, Any], target_line: int, context_lines: int = 3) -> Tuple[str, str]:
        """Get context before and after a specific line"""
        content = result.get("Content", "")
        if not content:
            return "", ""
        
        lines = content.split('\n')
        start_idx = max(0, target_line - context_lines - 1)
        end_idx = min(len(lines), target_line + context_lines)
        
        before_lines = lines[start_idx:target_line - 1]
        after_lines = lines[target_line:end_idx]
        
        return '\n'.join(before_lines), '\n'.join(after_lines)
    
    async def _extract_usage_contexts(self, 
                                    result: Dict[str, Any], 
                                    function_name: str,
                                    original_file: str) -> List[UsageContext]:
        """Extract usage contexts from search result"""
        contexts = []
        line_matches = result.get("LineMatches", [])
        file_name = result.get("FileName", "")
        
        for line_match in line_matches:
            line_number = line_match.get("LineNumber", 0)
            line_content = self._get_line_content_from_match(line_match, result)
            
            # Determine usage type
            usage_type = self._determine_usage_type(line_content, function_name)
            
            # Get context around the line
            context_before, context_after = self._get_context_around_line(result, line_number, 3)
            
            # Calculate individual usage score
            usage_score = (
                self._get_usage_type_score(line_content, function_name) +
                line_match.get("Score", 0) / 1000 +  # Normalize Zoekt line score
                result.get("relevance_score", 0) / 10  # Factor in file relevance
            )
            
            context = UsageContext(
                file_path=file_name,
                line_number=line_number,
                context_before=context_before,
                context_after=context_after,
                usage_type=usage_type,
                score=usage_score
            )
            
            contexts.append(context)
        
        return contexts
    
    def _determine_usage_type(self, line_content: str, function_name: str) -> str:
        """Determine the type of function usage"""
        line = line_content.strip().lower()
        func_name = function_name.lower()
        
        if re.search(rf'import.*{func_name}', line):
            return 'import'
        elif re.search(rf'export.*{func_name}', line):
            return 'export'
        elif re.search(rf'def\s+{func_name}|function\s+{func_name}', line):
            return 'definition'
        elif re.search(rf'{func_name}\s*\(', line):
            return 'call'
        elif re.search(rf'\.{func_name}\s*\(', line):
            return 'method_call'
        elif re.search(rf'=\s*{func_name}\b', line):
            return 'assignment'
        elif re.search(rf'{func_name}\s*:', line):
            return 'property'
        elif re.search(rf':\s*{func_name}\b|<{func_name}>', line):
            return 'type_annotation'
        else:
            return 'reference'
    
    async def search_similar_functions(self, 
                                     function_context: FunctionContext, 
                                     max_results: int = 5) -> List[Dict[str, Any]]:
        """Search for similar functions in the codebase"""
        queries = []
        
        # Search by function signature patterns
        if function_context.parameters:
            param_types = self._extract_parameter_types(function_context.signature)
            if param_types:
                queries.append(" ".join(param_types))
        
        # Search by function name patterns
        name_patterns = self._generate_name_patterns(function_context.name)
        queries.extend(name_patterns)
        
        # Search by implementation keywords
        impl_keywords = self._extract_implementation_keywords(function_context.implementation)
        if impl_keywords:
            queries.append(" ".join(impl_keywords[:3]))  # Top 3 keywords
        
        all_results = []
        for query in queries[:3]:  # Limit to top 3 queries
            try:
                results = await self.zoekt_client.search_by_text(query, max_docs=max_results)
                all_results.extend(results)
            except Exception as e:
                print(f"Similar function search failed for query '{query}': {e}")
                continue
        
        # Filter and deduplicate
        unique_results = self._deduplicate_results(all_results)
        return unique_results[:max_results]
    
    def _extract_parameter_types(self, signature: str) -> List[str]:
        """Extract parameter types from function signature"""
        # Basic implementation - can be enhanced for specific languages
        type_keywords = re.findall(r'\b(string|number|boolean|int|float|list|dict|array|object)\b', 
                                  signature.lower())
        return list(set(type_keywords))
    
    def _generate_name_patterns(self, function_name: str) -> List[str]:
        """Generate search patterns based on function name"""
        patterns = []
        
        # Split camelCase and snake_case
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|[0-9]+', function_name)
        words = [w.lower() for w in words if len(w) > 2]  # Filter short words
        
        if len(words) > 1:
            patterns.append(" ".join(words))
            patterns.extend(words[:2])  # Individual words
        
        return patterns
    
    def _extract_implementation_keywords(self, implementation: str) -> List[str]:
        """Extract important keywords from function implementation"""
        # Remove common code constructs and focus on domain-specific terms
        code_keywords = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', implementation)
        
        # Filter out common programming keywords
        common_keywords = {
            'function', 'return', 'const', 'let', 'var', 'if', 'else', 'for', 'while',
            'def', 'class', 'import', 'export', 'from', 'try', 'catch', 'finally',
            'async', 'await', 'then', 'catch', 'true', 'false', 'null', 'undefined'
        }
        
        filtered_keywords = [kw for kw in code_keywords 
                           if kw.lower() not in common_keywords and len(kw) > 3]
        
        # Return most frequent keywords
        from collections import Counter
        keyword_counts = Counter(filtered_keywords)
        return [kw for kw, count in keyword_counts.most_common(10)] 