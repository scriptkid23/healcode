"""
Pattern-based file editing strategy using regex with in_place library
"""

import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Pattern

try:
    import in_place
    HAS_IN_PLACE = True
except ImportError:
    HAS_IN_PLACE = False

from ..interfaces import (
    EditRequest, EditResult, EditOperationType, EditorInterface,
    FileNotFoundException, ValidationException, OperationMetadata
)


class PatternEditor(EditorInterface):
    """Editor for regex pattern-based modifications"""
    
    def __init__(self):
        self.supported_operations = {EditOperationType.PATTERN}
        self._compiled_patterns: Dict[str, Pattern] = {}
    
    def supports_operation(self, operation_type: EditOperationType) -> bool:
        """Check if this editor supports the given operation type"""
        return operation_type in self.supported_operations
    
    async def validate_request(self, request: EditRequest) -> bool:
        """Validate if the request can be processed"""
        if not self.supports_operation(request.operation_type):
            raise ValidationException(f"PatternEditor does not support {request.operation_type}")
        
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundException(f"File not found: {request.file_path}")
        
        if not file_path.is_file():
            raise ValidationException(f"Path is not a file: {request.file_path}")
        
        # Validate regex pattern
        try:
            pattern = request.target
            if not isinstance(pattern, str):
                raise ValidationException("Pattern target must be a string")
            
            # Try to compile the regex
            re.compile(pattern)
        except re.error as e:
            raise ValidationException(f"Invalid regex pattern: {e}")
        
        # Check if we can read the file
        try:
            with open(file_path, 'r', encoding=request.options.encoding) as f:
                f.readline()
        except UnicodeDecodeError:
            raise ValidationException(f"Cannot decode file with encoding {request.options.encoding}")
        except PermissionError:
            raise ValidationException(f"No read permission for file: {request.file_path}")
        
        return True
    
    async def edit(self, request: EditRequest) -> EditResult:
        """Edit a file according to the request"""
        start_time = time.time()
        operation_id = OperationMetadata.generate_operation_id()
        
        try:
            await self.validate_request(request)
            
            if request.operation_type == EditOperationType.PATTERN:
                result = await self._edit_pattern(request, operation_id)
            else:
                return EditResult.error_result(
                    operation_id, request.file_path, request.operation_type,
                    f"Unsupported operation: {request.operation_type}"
                )
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            return EditResult.error_result(
                operation_id, request.file_path, request.operation_type, str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def _edit_pattern(self, request: EditRequest, operation_id: str) -> EditResult:
        """Edit using regex pattern replacement"""
        pattern = request.target
        replacement = request.content
        
        # Read original content
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            original_content = f.read()
        
        # Get or compile pattern
        compiled_pattern = self._get_compiled_pattern(pattern)
        
        # Count matches before replacement
        matches = list(compiled_pattern.finditer(original_content))
        match_count = len(matches)
        
        if match_count == 0:
            return EditResult.success_result(
                operation_id=operation_id,
                file_path=request.file_path,
                operation_type=request.operation_type,
                diff="",
                lines_changed=0,
                bytes_changed=0,
                metadata={"matches_found": 0, "pattern": pattern}
            )
        
        # Perform replacement
        if HAS_IN_PLACE:
            modified_content = await self._edit_pattern_inplace(request, compiled_pattern)
        else:
            modified_content = await self._edit_pattern_standard(request, compiled_pattern)
        
        # Generate diff
        diff = self._generate_diff(original_content, modified_content)
        
        # Count lines changed (approximate by counting lines in diff)
        lines_changed = self._count_changed_lines(diff)
        
        return EditResult.success_result(
            operation_id=operation_id,
            file_path=request.file_path,
            operation_type=request.operation_type,
            diff=diff,
            lines_changed=lines_changed,
            bytes_changed=len(modified_content.encode()) - len(original_content.encode()),
            metadata={
                "matches_found": match_count,
                "pattern": pattern,
                "replacement": replacement
            }
        )
    
    async def _edit_pattern_inplace(self, request: EditRequest, compiled_pattern: Pattern) -> str:
        """Edit using in_place library"""
        modified_content = ""
        
        with in_place.InPlace(
            request.file_path,
            encoding=request.options.encoding
        ) as file:
            for line in file:
                modified_line = compiled_pattern.sub(request.content, line)
                file.write(modified_line)
                modified_content += modified_line
        
        return modified_content
    
    async def _edit_pattern_standard(self, request: EditRequest, compiled_pattern: Pattern) -> str:
        """Edit using standard file operations"""
        # Create backup if requested
        if request.options.create_backup:
            import shutil
            backup_path = f"{request.file_path}.bak"
            shutil.copy2(request.file_path, backup_path)
        
        # Read, modify, and write back
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            content = f.read()
        
        modified_content = compiled_pattern.sub(request.content, content)
        
        with open(request.file_path, 'w', encoding=request.options.encoding) as f:
            f.write(modified_content)
        
        return modified_content
    
    def _get_compiled_pattern(self, pattern: str) -> Pattern:
        """Get or compile regex pattern with caching"""
        if pattern not in self._compiled_patterns:
            self._compiled_patterns[pattern] = re.compile(pattern, re.MULTILINE)
        return self._compiled_patterns[pattern]
    
    def _generate_diff(self, original: str, modified: str) -> str:
        """Generate unified diff between original and modified content"""
        import difflib
        
        return '\n'.join(difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile='original',
            tofile='modified',
            lineterm=''
        ))
    
    def _count_changed_lines(self, diff: str) -> int:
        """Count the number of changed lines from diff output"""
        if not diff:
            return 0
        
        changed_lines = 0
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                changed_lines += 1
            elif line.startswith('-') and not line.startswith('---'):
                changed_lines += 1
        
        return changed_lines // 2  # Each change has both + and - lines
    
    async def search_pattern(self, file_path: str, pattern: str, encoding: str = 'utf-8') -> List[Dict]:
        """Search for pattern matches without editing (utility method)"""
        try:
            compiled_pattern = self._get_compiled_pattern(pattern)
            
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            matches = []
            for match in compiled_pattern.finditer(content):
                # Calculate line number
                line_num = content[:match.start()].count('\n') + 1
                
                matches.append({
                    'match': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'line_number': line_num,
                    'groups': match.groups() if match.groups() else [],
                    'groupdict': match.groupdict() if match.groupdict() else {}
                })
            
            return matches
            
        except Exception as e:
            raise ValidationException(f"Error searching pattern: {e}")
    
    def clear_pattern_cache(self):
        """Clear compiled pattern cache"""
        self._compiled_patterns.clear()
    
    async def validate_pattern(self, pattern: str) -> Dict[str, any]:
        """Validate and analyze a regex pattern"""
        try:
            compiled = re.compile(pattern, re.MULTILINE)
            
            # Basic pattern analysis
            analysis = {
                'valid': True,
                'pattern': pattern,
                'groups': compiled.groups,
                'groupindex': compiled.groupindex,
                'flags': compiled.flags,
                'error': None
            }
            
            # Check for common issues
            warnings = []
            
            # Check for potentially inefficient patterns
            if '.*' in pattern or '.+' in pattern:
                warnings.append("Pattern contains .* or .+ which may be inefficient")
            
            # Check for unescaped special characters
            special_chars = ['.', '^', '$', '*', '+', '?', '{', '}', '[', ']', '\\', '|', '(', ')']
            unescaped = []
            for i, char in enumerate(pattern):
                if char in special_chars and (i == 0 or pattern[i-1] != '\\'):
                    if char not in ['^', '$'] or (char == '^' and i != 0) or (char == '$' and i != len(pattern)-1):
                        unescaped.append(char)
            
            if unescaped:
                warnings.append(f"Potentially unescaped special characters: {', '.join(set(unescaped))}")
            
            analysis['warnings'] = warnings
            return analysis
            
        except re.error as e:
            return {
                'valid': False,
                'pattern': pattern,
                'error': str(e),
                'warnings': []
            } 