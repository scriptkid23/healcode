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

import tree_sitter
from tree_sitter import Language, Parser

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
        self._parser = Parser()
        
    def _get_parser(self):
        """Get or create tree-sitter parser for the language"""
        if self._parser.language is None:
            try:
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
        print(12345)
        try:
            import tree_sitter_javascript as js
            parser = Parser(Language(js.language()))
            return parser
        except ImportError:
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
        """
        Return a FunctionContext for the smallest function-like node that contains
        the given 1-based line_number. If nothing is found, return None.

        Works best for JavaScript/TypeScript/JSX/TSX (and reasonable for others).
        Extracts: name, signature, implementation (full source slice), start/end lines,
        file_path, language, documentation (leading comments), and parameters (list).
        """
        if not self.tree or not self.content:
            return None
        if line_number < 1 or line_number > len(self.lines):
            return None

        # -------------------- helpers --------------------
        def _point_for_line(ln: int):
            # Tree-sitter points are 0-based; query the entire line span.
            return (ln - 1, 0), (ln - 1, 10**9)

        def _text(node) -> str:
            return self.content[node.start_byte:node.end_byte]

        def _func_node_types(lang: str):
            js_like = {
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            }
            ts_like = js_like | {"method_signature", "function_signature", "constructor"}
            java_like = {"method_declaration", "constructor_declaration", "lambda_expression"}
            rust_like = {"function_item", "closure_expression"}

            lang = (lang or "").lower()
            if lang in ("javascript", "jsx"):
                return js_like
            if lang in ("typescript", "tsx"):
                return ts_like
            if lang == "java":
                return java_like
            if lang == "rust":
                return rust_like
            return js_like | ts_like | java_like | rust_like

        def _nearest_func_ancestor(node, wanted: set):
            cur = node
            while cur is not None:
                if cur.type in wanted:
                    return cur
                cur = cur.parent
            return None

        def _child_by_field_name(node, field: str):
            try:
                return node.child_by_field_name(field)
            except Exception:
                return None

        def _first_child_of_type(node, types):
            for ch in node.children:
                if ch.type in types:
                    return ch
            return None

        def _extract_arrow_assigned_name(node):
            """
            For arrow functions, try to infer name from the left-hand side:
            - const foo = () => {}
            - obj.foo = () => {}
            - class C { method = () => {} }
            """
            p = node.parent
            hops = 4
            while p is not None and hops > 0:
                hops -= 1
                if p.type in ("variable_declarator", "lexical_declaration", "variable_declaration"):
                    ident = _first_child_of_type(p, ("identifier", "property_identifier"))
                    if ident: return _text(ident).strip()
                    if p.children:
                        left = p.children[0]
                        ident = _first_child_of_type(left, ("identifier", "property_identifier"))
                        if ident: return _text(ident).strip()
                if p.type == "assignment_expression" and p.children:
                    lhs = p.children[0]
                    ident = _first_child_of_type(lhs, ("identifier", "property_identifier"))
                    if ident: return _text(ident).strip()
                if p.type in ("method_definition", "pair", "public_field_definition"):
                    ident = _first_child_of_type(p, ("property_identifier", "identifier"))
                    if ident: return _text(ident).strip()
                p = p.parent
            return "<anonymous>"

        def _extract_name(node):
            # 1) Prefer a named field
            nf = _child_by_field_name(node, "name")
            if nf: return _text(nf).strip()
            # 2) Common identifier children
            ident = _first_child_of_type(node, ("identifier", "property_identifier"))
            if ident: return _text(ident).strip()
            # 3) Arrow function often anonymous → try LHS
            if node.type == "arrow_function":
                return _extract_arrow_assigned_name(node)
            return "<anonymous>"

        def _extract_params_list(node):
            """
            Return a list of parameter "names" (best-effort).
            For destructuring and complex patterns, we return the raw text slice.
            """
            params = _child_by_field_name(node, "parameters")
            if not params:
                return []

            # Try to pick identifiers inside parameters; if not found, fall back to raw chunks.
            result = []
            # Many grammars wrap the actual list; look for direct children that are parameters
            # and gather identifiable tokens.
            def collect_simple_idents(n):
                found = []
                stack = [n]
                while stack:
                    cur = stack.pop()
                    if cur.type in ("identifier", "shorthand_property_identifier_pattern", "property_identifier"):
                        found.append(_text(cur).strip())
                    else:
                        stack.extend(cur.children or [])
                return found

            idents = collect_simple_idents(params)
            if idents:
                # de-dup while keeping order
                seen = set()
                for s in idents:
                    if s and s not in seen:
                        seen.add(s)
                        result.append(s)
                return result

            # Fallback: split raw text between parentheses by commas (best-effort).
            raw = _text(params).strip()
            if raw.startswith("(") and raw.endswith(")"):
                raw = raw[1:-1]
            # Very naive split; fine for most everyday signatures.
            pieces = [p.strip() for p in raw.split(",")]
            return [p for p in pieces if p]

        def _extract_params_snippet(node):
            params = _child_by_field_name(node, "parameters")
            return _text(params).strip() if params else ""

        def _extract_leading_docstring(func_node):
            """
            Collect contiguous line/block comments immediately above the function.
            Stops at the first blank line or non-comment code.
            """
            start_line = func_node.start_point[0]  # 0-based
            line_idx = start_line - 1
            if line_idx < 0:
                return None

            doc_lines = []
            seen_nonempty = False

            # Walk upward until a blank line without comments or we hit file start.
            while line_idx >= 0:
                line = self.lines[line_idx]
                stripped = line.strip()

                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped.endswith("*/"):
                    doc_lines.append(line.rstrip())
                    seen_nonempty = True
                    line_idx -= 1
                    continue

                # allow pure whitespace between comment lines
                if stripped == "" and seen_nonempty:
                    doc_lines.append(line.rstrip())
                    line_idx -= 1
                    continue

                # hit non-comment code or gap above comment block
                break

            if not doc_lines:
                return None

            # Reverse to restore top→down order and clean up common JSDoc markers.
            doc_lines.reverse()
            doc = "\n".join(doc_lines)
            # Strip common JSDoc decorations
            doc = doc.replace("/**", "").replace("*/", "")
            doc = "\n".join(l.lstrip(" *") for l in doc.splitlines())
            return doc.strip() or None

        # -------------------- core logic --------------------
        start_pt, end_pt = _point_for_line(line_number)
        root = self.tree.root_node
        try:
            node = root.descendant_for_point_range(start_pt, end_pt)
        except Exception:
            end_pt = (start_pt[0], start_pt[1] + 1)
            node = root.descendant_for_point_range(start_pt, end_pt)

        if node is None:
            return None

        func_node = _nearest_func_ancestor(node, _func_node_types(self.language))
        if func_node is None:
            return None

        name = _extract_name(func_node)
        params_snip = _extract_params_snippet(func_node)
        params_list = _extract_params_list(func_node)
        doc = _extract_leading_docstring(func_node)

        impl = _text(func_node)
        start_line0, start_col = func_node.start_point
        end_line0, end_col = func_node.end_point

        signature = f"{name}{params_snip}" if params_snip else name

        # Build FunctionContext (works whether your class is a plain class or a @dataclass)
        try:
            # If FunctionContext is a dataclass or has an __init__ with these fields:
            return FunctionContext(
                name=name,
                signature=signature,
                implementation=impl,
                start_line=start_line0 + 1,  # convert to 1-based
                end_line=end_line0 + 1,
                file_path=self.file_path,
                language=self.language,
                documentation=doc,
                parameters=params_list,
            )
        except TypeError:
            # If FunctionContext has no __init__, instantiate then assign attributes.
            ctx = FunctionContext() # type: ignore
            ctx.name = name
            ctx.signature = signature
            ctx.implementation = impl
            ctx.start_line = start_line0 + 1
            ctx.end_line = end_line0 + 1
            ctx.file_path = self.file_path
            ctx.language = self.language
            ctx.documentation = doc
            ctx.parameters = params_list
            return ctx


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
        parsers:List[tuple[str, TreeSitterParser]] = self._get_parsers_for_language(language)
        
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
    
    def _get_parsers_for_language(self, language: str) -> List[tuple[str, TreeSitterParser]]:
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