import re
import ast
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from dataclasses import dataclass

from .error_context_collector import FunctionContext

class LanguagePatterns:
    """Regex patterns for detecting functions in different programming languages"""
    
    PATTERNS = {
        # JavaScript/TypeScript
        'javascript': [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*{',  # function declaration
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{',  # arrow function
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\([^)]*\)\s*{',  # function expression
            r'(\w+)\s*:\s*(?:async\s+)?function\s*\([^)]*\)\s*{',  # object method
            r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*{',  # method in class or object
        ],
        
        # Python
        'python': [
            r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\):',  # function definition
            r'(\w+)\s*=\s*lambda\s+[^:]*:',  # lambda function
        ],
        
        # Java/C#
        'java': [
            r'(?:public|private|protected)?\s*(?:static)?\s*(?:async)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*{',
        ],
        
        # C/C++
        'c': [
            r'(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*{',  # function definition
        ],
        
        # Go
        'go': [
            r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\([^)]*\)\s*(?:\([^)]*\))?\s*{',
        ],
        
        # Rust
        'rust': [
            r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*{',
        ],
        
        # PHP
        'php': [
            r'(?:public|private|protected)?\s*(?:static)?\s*function\s+(\w+)\s*\([^)]*\)\s*{',
        ],
        
        # Ruby
        'ruby': [
            r'def\s+(\w+)(?:\([^)]*\))?',
        ],
        
        # Swift
        'swift': [
            r'(?:override\s+)?(?:class\s+)?(?:static\s+)?func\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*{',
        ]
    }

    @classmethod
    def get_language_from_extension(cls, file_path: str) -> str:
        """Determine programming language from file extension"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.js': 'javascript',
            '.jsx': 'javascript', 
            '.ts': 'javascript',
            '.tsx': 'javascript',
            '.py': 'python',
            '.java': 'java',
            '.cs': 'java',  # C# uses similar patterns
            '.c': 'c',
            '.cpp': 'c',
            '.cc': 'c',
            '.cxx': 'c',
            '.h': 'c',
            '.hpp': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
        }
        
        return language_map.get(ext, 'javascript')  # Default to JavaScript

class FunctionAnalyzer:
    """Analyze functions in source code across different programming languages"""
    
    def __init__(self):
        self.patterns = LanguagePatterns()

    async def analyze_function_at_line(self, 
                                     file_content: str, 
                                     file_path: str, 
                                     target_line: int) -> Optional[FunctionContext]:
        """Find and analyze the function containing the specified line"""
        
        language = self.patterns.get_language_from_extension(file_path)
        lines = file_content.split('\n')
        
        # First, try language-specific analysis
        if language == 'python':
            return await self._analyze_python_function(file_content, file_path, target_line)
        elif language == 'javascript':
            return await self._analyze_javascript_function(file_content, file_path, target_line)
        else:
            # Fallback to generic pattern matching
            return await self._analyze_generic_function(file_content, file_path, target_line, language)

    async def _analyze_python_function(self, 
                                     file_content: str, 
                                     file_path: str, 
                                     target_line: int) -> Optional[FunctionContext]:
        """Analyze Python functions using AST parsing"""
        try:
            tree = ast.parse(file_content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if target line is within this function
                    if node.lineno <= target_line <= getattr(node, 'end_lineno', node.lineno):
                        return await self._extract_python_function_context(
                            node, file_content, file_path
                        )
                        
        except SyntaxError:
            # Fallback to regex if AST parsing fails
            pass
        
        return await self._analyze_generic_function(file_content, file_path, target_line, 'python')

    async def _extract_python_function_context(self, 
                                             node: ast.FunctionDef | ast.AsyncFunctionDef, 
                                             file_content: str, 
                                             file_path: str) -> FunctionContext:
        """Extract context information from Python AST node"""
        lines = file_content.split('\n')
        
        # Get function signature
        signature = lines[node.lineno - 1].strip()
        
        # Get function implementation
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', len(lines))
        implementation = '\n'.join(lines[start_line - 1:end_line])
        
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
            file_path=file_path,
            language='python',
            documentation=documentation,
            parameters=parameters
        )

    async def _analyze_javascript_function(self, 
                                         file_content: str, 
                                         file_path: str, 
                                         target_line: int) -> Optional[FunctionContext]:
        """Analyze JavaScript functions using pattern matching"""
        return await self._analyze_generic_function(file_content, file_path, target_line, 'javascript')

    async def _analyze_generic_function(self, 
                                      file_content: str, 
                                      file_path: str, 
                                      target_line: int, 
                                      language: str) -> Optional[FunctionContext]:
        """Generic function analysis using regex patterns"""
        lines = file_content.split('\n')
        patterns = self.patterns.PATTERNS.get(language, self.patterns.PATTERNS['javascript'])
        
        # Find all functions in the file
        functions = []
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    function_name = match.group(1)
                    start_line = i
                    end_line = self._find_function_end(lines, start_line - 1, language)
                    
                    functions.append({
                        'name': function_name,
                        'start_line': start_line,
                        'end_line': end_line,
                        'signature': line.strip()
                    })
        
        # Find function containing target line
        for func in functions:
            if func['start_line'] <= target_line <= func['end_line']:
                # Extract implementation
                implementation_lines = lines[func['start_line'] - 1:func['end_line']]
                implementation = '\n'.join(implementation_lines)
                
                # Extract parameters (basic)
                parameters = self._extract_parameters(func['signature'], language)
                
                # Look for documentation (comments above function)
                documentation = self._extract_documentation(lines, func['start_line'] - 1, language)
                
                return FunctionContext(
                    name=func['name'],
                    signature=func['signature'],
                    implementation=implementation,
                    start_line=func['start_line'],
                    end_line=func['end_line'],
                    file_path=file_path,
                    language=language,
                    documentation=documentation,
                    parameters=parameters
                )
        
        return None

    def _find_function_end(self, lines: List[str], start_index: int, language: str) -> int:
        """Find the end line of a function based on brace/indentation matching"""
        
        if language == 'python':
            return self._find_python_function_end(lines, start_index)
        else:
            return self._find_brace_function_end(lines, start_index)

    def _find_python_function_end(self, lines: List[str], start_index: int) -> int:
        """Find end of Python function based on indentation"""
        if start_index >= len(lines):
            return len(lines)
        
        # Get the indentation level of the function definition
        func_line = lines[start_index]
        func_indent = len(func_line) - len(func_line.lstrip())
        
        # Find the next line with same or lower indentation (excluding empty lines)
        for i in range(start_index + 1, len(lines)):
            line = lines[i]
            if line.strip():  # Skip empty lines
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= func_indent:
                    return i
        
        return len(lines)

    def _find_brace_function_end(self, lines: List[str], start_index: int) -> int:
        """Find end of function based on brace matching"""
        brace_count = 0
        in_function = False
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            
            # Count braces
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_function = True
                elif char == '}':
                    brace_count -= 1
                    
                    # Function ends when we close all braces
                    if in_function and brace_count == 0:
                        return i + 1
        
        return len(lines)

    def _extract_parameters(self, signature: str, language: str) -> List[str]:
        """Extract function parameters from signature"""
        # Find parameter list in parentheses
        match = re.search(r'\(([^)]*)\)', signature)
        if not match:
            return []
        
        params_str = match.group(1).strip()
        if not params_str:
            return []
        
        # Basic parameter extraction (can be enhanced)
        if language == 'python':
            # Python: handle default values, type hints
            params = []
            for param in params_str.split(','):
                param = param.strip()
                # Remove type hints and default values
                param = re.sub(r':\s*[^=]+', '', param)  # Remove type hints
                param = re.sub(r'=.*$', '', param)      # Remove default values
                if param and param != 'self':
                    params.append(param.strip())
            return params
        else:
            # JavaScript and others: basic comma-separated extraction
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            return params

    def _extract_documentation(self, lines: List[str], func_start_index: int, language: str) -> Optional[str]:
        """Extract function documentation (comments, docstrings)"""
        docs = []
        
        if language == 'python':
            # Look for docstring after function definition
            if func_start_index + 1 < len(lines):
                next_line = lines[func_start_index + 1].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    # Multi-line docstring
                    quote_type = next_line[:3]
                    if next_line.endswith(quote_type) and len(next_line) > 6:
                        # Single line docstring
                        return next_line[3:-3].strip()
                    else:
                        # Multi-line docstring
                        docs.append(next_line[3:])
                        for i in range(func_start_index + 2, len(lines)):
                            line = lines[i]
                            if quote_type in line:
                                docs.append(line[:line.index(quote_type)])
                                break
                            docs.append(line)
                        return '\n'.join(docs).strip()
        
        # Look for comments above function
        for i in range(func_start_index - 1, max(-1, func_start_index - 10), -1):
            line = lines[i].strip()
            if not line:
                continue
            
            if language == 'javascript':
                if line.startswith('//') or line.startswith('/*') or line.startswith('*'):
                    docs.insert(0, line)
                else:
                    break
            elif language in ['python']:
                if line.startswith('#'):
                    docs.insert(0, line)
                else:
                    break
            else:
                # Generic comment detection
                if line.startswith('//') or line.startswith('#') or line.startswith('/*'):
                    docs.insert(0, line)
                else:
                    break
        
        return '\n'.join(docs) if docs else None

    async def find_all_functions(self, file_content: str, file_path: str) -> List[FunctionContext]:
        """Find all functions in a file"""
        language = self.patterns.get_language_from_extension(file_path)
        functions = []
        
        if language == 'python':
            try:
                tree = ast.parse(file_content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        func_context = await self._extract_python_function_context(
                            node, file_content, file_path
                        )
                        functions.append(func_context)
                return functions
            except SyntaxError:
                pass
        
        # Fallback to regex for all languages
        lines = file_content.split('\n')
        patterns = self.patterns.PATTERNS.get(language, self.patterns.PATTERNS['javascript'])
        
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    function_name = match.group(1)
                    start_line = i
                    end_line = self._find_function_end(lines, start_line - 1, language)
                    
                    implementation_lines = lines[start_line - 1:end_line]
                    implementation = '\n'.join(implementation_lines)
                    parameters = self._extract_parameters(line, language)
                    documentation = self._extract_documentation(lines, start_line - 1, language)
                    
                    functions.append(FunctionContext(
                        name=function_name,
                        signature=line.strip(),
                        implementation=implementation,
                        start_line=start_line,
                        end_line=end_line,
                        file_path=file_path,
                        language=language,
                        documentation=documentation,
                        parameters=parameters
                    ))
        
        return functions 