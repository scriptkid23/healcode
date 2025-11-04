"""
Enhanced Multi-Language Function Parsers

Provides AST-based parsing for Python and tree-sitter parsing for other languages
with fallback to regex-based parsing.
"""

import ast
import re
import subprocess
import tempfile
import os
from typing import Optional, Dict, List, Any, Protocol, Union
from pathlib import Path
from dataclasses import dataclass
import resource
import signal
import time
import psutil

from ai.core.error_context_collector import FunctionContext
from ai.workflows.config import SecurityConfig, LanguageConfig

class ParseResult(Protocol):
    """Protocol for parse results"""
    def get_function_at_line(self, line_number: int) -> Optional[FunctionContext]:
        ...

@dataclass
class SecurityContext:
    """Security context for parsing operations"""
    max_memory_mb: int
    max_execution_time_seconds: int
    enable_sandboxing: bool
    
    def __post_init__(self):
        """Set resource limits"""
        if self.enable_sandboxing:
            # Set memory limit
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory_mb * 1024 * 1024, -1))
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.max_execution_time_seconds, -1))

class TimeoutError(Exception):
    """Raised when parsing operation times out"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Parsing operation timed out")

class SandboxedParser:
    """Base class for sandboxed parsing operations"""
    
    def __init__(self, security_config: SecurityConfig):
        self.security_config = security_config
        self.process = None
        
    def _setup_sandbox(self):
        """Setup sandboxing environment"""
        if self.security_config.enable_sandboxing:
            # Set up signal handler for timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.security_config.max_execution_time_seconds)
            
            # Monitor memory usage
            self._initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
    
    def _cleanup_sandbox(self):
        """Clean up sandboxing environment"""
        if self.security_config.enable_sandboxing:
            signal.alarm(0)  # Cancel timeout
            
            # Check final memory usage
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_used = final_memory - self._initial_memory
            
            if memory_used > self.security_config.max_memory_mb:
                raise MemoryError(f"Memory usage exceeded limit: {memory_used}MB > {self.security_config.max_memory_mb}MB")

class PythonASTParser(SandboxedParser):
    """AST-based parser for Python code"""
    
    def __init__(self, security_config: SecurityConfig):
        super().__init__(security_config)
        
    def parse(self, file_content: str, file_path: str) -> 'PythonParseResult':
        """Parse Python code using AST"""
        try:
            self._setup_sandbox()
            
            # Check file size
            file_size_mb = len(file_content.encode('utf-8')) / 1024 / 1024
            if file_size_mb > self.security_config.max_memory_mb / 4:  # Use 1/4 of memory limit
                raise ValueError(f"File too large for AST parsing: {file_size_mb}MB")
            
            tree = ast.parse(file_content)
            return PythonParseResult(tree, file_content, file_path)
            
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse Python code: {e}")
        except TimeoutError:
            raise TimeoutError("Python AST parsing timed out")
        finally:
            self._cleanup_sandbox()

class PythonParseResult:
    """Result of Python AST parsing"""
    
    def __init__(self, tree: ast.AST, content: str, file_path: str):
        self.tree = tree
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')
        
    def get_function_at_line(self, line_number: int) -> Optional[FunctionContext]:
        """Find function containing the specified line"""
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.lineno <= line_number <= getattr(node, 'end_lineno', node.lineno):
                    return self._extract_function_context(node)
        return None
    
    def _extract_function_context(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> FunctionContext:
        """Extract function context from AST node"""
        # Get function signature
        signature = self.lines[node.lineno - 1].strip()
        
        # Get function implementation
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', len(self.lines))
        implementation = '\n'.join(self.lines[start_line - 1:end_line])
        
        # Get function parameters
        parameters = [arg.arg for arg in node.args.args]
        
        # Get docstring if available
        documentation = None
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            documentation = node.body[0].value.value
        
        return FunctionContext(
            name=node.name,
            signature=signature,
            implementation=implementation,
            start_line=start_line,
            end_line=end_line,
            file_path=self.file_path,
            language='python',
            documentation=documentation,
            parameters=parameters
        )

class TreeSitterParser(SandboxedParser):
    """Tree-sitter based parser for multiple languages"""
    
    def __init__(self, language: str, security_config: SecurityConfig):
        super().__init__(security_config)
        self.language = language
        self._parser = None
        
    def _get_parser(self):
        """Get or create tree-sitter parser for the language"""
        if self._parser is None:
            try:
                import tree_sitter
                from tree_sitter import Language, Parser
                
                # Language-specific parser setup
                if self.language == 'java':
                    self._parser = self._create_java_parser()
                elif self.language == 'javascript':
                    self._parser = self._create_javascript_parser()
                elif self.language == 'typescript':
                    self._parser = self._create_typescript_parser()
                elif self.language == 'rust':
                    self._parser = self._create_rust_parser()
                else:
                    raise ValueError(f"Unsupported language: {self.language}")
                    
            except ImportError:
                raise ImportError("tree-sitter not installed. Install with: pip install tree-sitter")
                
        return self._parser
    
    def _create_java_parser(self):
        """Create Java tree-sitter parser"""
        # This would be implemented with actual tree-sitter Java grammar
        # For now, we'll use a placeholder
        raise NotImplementedError("Java tree-sitter parser not yet implemented")
    
    def _create_javascript_parser(self):
        """Create JavaScript tree-sitter parser"""
        # This would be implemented with actual tree-sitter JavaScript grammar
        raise NotImplementedError("JavaScript tree-sitter parser not yet implemented")
    
    def _create_typescript_parser(self):
        """Create TypeScript tree-sitter parser"""
        # This would be implemented with actual tree-sitter TypeScript grammar
        raise NotImplementedError("TypeScript tree-sitter parser not yet implemented")
    
    def _create_rust_parser(self):
        """Create Rust tree-sitter parser"""
        # This would be implemented with actual tree-sitter Rust grammar
        raise NotImplementedError("Rust tree-sitter parser not yet implemented")
    
    def parse(self, file_content: str, file_path: str) -> 'TreeSitterParseResult':
        """Parse code using tree-sitter"""
        try:
            self._setup_sandbox()
            
            parser = self._get_parser()
            tree = parser.parse(bytes(file_content, 'utf-8'))
            
            return TreeSitterParseResult(tree, file_content, file_path, self.language)
            
        except Exception as e:
            raise ValueError(f"Failed to parse {self.language} code: {e}")
        finally:
            self._cleanup_sandbox()

class TreeSitterParseResult:
    """Result of tree-sitter parsing"""
    
    def __init__(self, tree, content: str, file_path: str, language: str):
        self.tree = tree
        self.content = content
        self.file_path = file_path
        self.language = language
        self.lines = content.split('\n')
        
    def get_function_at_line(self, line_number: int) -> Optional[FunctionContext]:
        """Find function containing the specified line (placeholder implementation)"""
        # This would use tree-sitter query to find function nodes
        # For now, we'll return None to trigger fallback
        return None

class RegexParser(SandboxedParser):
    """Regex-based fallback parser"""
    
    # Language-specific function patterns
    FUNCTION_PATTERNS = {
        'python': [
            r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\):',
        ],
        'java': [
            r'(?:public|private|protected)?\s*(?:static)?\s*(?:async)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*{',
        ],
        'javascript': [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*{',
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{',
            r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*{',
        ],
        'typescript': [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\):\s*[^{]*{',
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\):\s*[^=]*=>\s*{',
        ],
        'rust': [
            r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*{',
        ]
    }
    
    def __init__(self, language: str, security_config: SecurityConfig):
        super().__init__(security_config)
        self.language = language
        
    def parse(self, file_content: str, file_path: str) -> 'RegexParseResult':
        """Parse code using regex patterns"""
        try:
            self._setup_sandbox()
            
            return RegexParseResult(file_content, file_path, self.language)
            
        except Exception as e:
            raise ValueError(f"Failed to parse {self.language} code with regex: {e}")
        finally:
            self._cleanup_sandbox()

class RegexParseResult:
    """Result of regex-based parsing"""
    
    def __init__(self, content: str, file_path: str, language: str):
        self.content = content
        self.file_path = file_path
        self.language = language
        self.lines = content.split('\n')
        
    def get_function_at_line(self, line_number: int) -> Optional[FunctionContext]:
        """Find function containing the specified line using regex"""
        patterns = RegexParser.FUNCTION_PATTERNS.get(self.language, [])
        
        # Find all functions in the file
        functions = []
        for i, line in enumerate(self.lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    function_name = match.group(1)
                    start_line = i
                    end_line = self._find_function_end(start_line - 1)
                    
                    functions.append({
                        'name': function_name,
                        'start_line': start_line,
                        'end_line': end_line,
                        'signature': line.strip()
                    })
        
        # Find function containing target line
        for func in functions:
            if func['start_line'] <= line_number <= func['end_line']:
                return self._create_function_context(func)
        
        return None
    
    def _find_function_end(self, start_index: int) -> int:
        """Find the end line of a function based on brace/indentation matching"""
        if self.language == 'python':
            return self._find_python_function_end(start_index)
        else:
            return self._find_brace_function_end(start_index)
    
    def _find_python_function_end(self, start_index: int) -> int:
        """Find end of Python function based on indentation"""
        if start_index >= len(self.lines):
            return len(self.lines)
        
        func_line = self.lines[start_index]
        func_indent = len(func_line) - len(func_line.lstrip())
        
        for i in range(start_index + 1, len(self.lines)):
            line = self.lines[i]
            if line.strip():  # Skip empty lines
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= func_indent:
                    return i
        
        return len(self.lines)
    
    def _find_brace_function_end(self, start_index: int) -> int:
        """Find end of function based on brace matching"""
        brace_count = 0
        in_function = False
        
        for i in range(start_index, len(self.lines)):
            line = self.lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_function = True
                elif char == '}':
                    brace_count -= 1
                    if in_function and brace_count == 0:
                        return i + 1
        
        return len(self.lines)
    
    def _create_function_context(self, func_info: Dict[str, Any]) -> FunctionContext:
        """Create FunctionContext from function info"""
        implementation_lines = self.lines[func_info['start_line'] - 1:func_info['end_line']]
        implementation = '\n'.join(implementation_lines)
        
        # Extract parameters (basic)
        parameters = self._extract_parameters(func_info['signature'])
        
        # Look for documentation
        documentation = self._extract_documentation(func_info['start_line'] - 1)
        
        return FunctionContext(
            name=func_info['name'],
            signature=func_info['signature'],
            implementation=implementation,
            start_line=func_info['start_line'],
            end_line=func_info['end_line'],
            file_path=self.file_path,
            language=self.language,
            documentation=documentation,
            parameters=parameters
        )
    
    def _extract_parameters(self, signature: str) -> List[str]:
        """Extract function parameters from signature"""
        match = re.search(r'\(([^)]*)\)', signature)
        if not match:
            return []
        
        params_str = match.group(1).strip()
        if not params_str:
            return []
        
        # Basic parameter extraction
        params = []
        for param in params_str.split(','):
            param = param.strip()
            # Remove type annotations and default values
            param = re.sub(r':\s*[^=]+', '', param)  # Remove type hints
            param = re.sub(r'=.*$', '', param)      # Remove default values
            if param and param not in ['self', 'cls']:
                params.append(param.strip())
        
        return params
    
    def _extract_documentation(self, func_start_index: int) -> Optional[str]:
        """Extract function documentation"""
        docs = []
        
        # Look for comments above function
        for i in range(func_start_index - 1, max(-1, func_start_index - 5), -1):
            if i < 0 or i >= len(self.lines):
                continue
                
            line = self.lines[i].strip()
            if not line:
                continue
            
            if line.startswith(('///', '/**', '/*', '//', '#')):
                docs.insert(0, line)
            else:
                break
        
        return '\n'.join(docs) if docs else None

class MultiLanguageFunctionAnalyzer:
    """Main analyzer that coordinates different parsers"""
    
    def __init__(self, security_config: SecurityConfig, language_config: LanguageConfig):
        self.security_config = security_config
        self.language_config = language_config
        
    def analyze_function_at_line(self, 
                               file_content: str, 
                               file_path: str, 
                               target_line: int) -> Optional[FunctionContext]:
        """Analyze function at specific line with multi-parser strategy"""
        
        language = self._get_language_from_path(file_path)
        
        if language not in self.language_config.supported_languages:
            raise ValueError(f"Unsupported language: {language}")
        
        # Try parsers in order of preference
        parsers = self._get_parsers_for_language(language)
        
        for parser_type, parser in parsers:
            try:
                result = parser.parse(file_content, file_path)
                function_context = result.get_function_at_line(target_line)
                
                if function_context:
                    return function_context
                    
            except Exception as e:
                print(f"Parser {parser_type} failed for {language}: {e}")
                continue
        
        return None
    
    def _get_language_from_path(self, file_path: str) -> str:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.java': 'java',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.rs': 'rust'
        }
        
        return language_map.get(ext, 'unknown')
    
    def _get_parsers_for_language(self, language: str) -> List[tuple]:
        """Get ordered list of parsers to try for a language"""
        parsers = []
        
        # AST parser for Python
        if language in self.language_config.ast_languages:
            parsers.append(('ast', PythonASTParser(self.security_config)))
        
        # Tree-sitter parser for supported languages
        if language in self.language_config.tree_sitter_parsers:
            try:
                parsers.append(('tree_sitter', TreeSitterParser(language, self.security_config)))
            except (ImportError, NotImplementedError):
                pass  # Fall back to regex
        
        # Regex parser as fallback
        if self.language_config.fallback_to_regex:
            parsers.append(('regex', RegexParser(language, self.security_config)))
        
        return parsers 