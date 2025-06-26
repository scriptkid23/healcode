"""
Line-specific file editing strategy using in_place library with fileinput fallback
"""

import time
import fileinput
from pathlib import Path
from typing import Optional

try:
    import in_place
    HAS_IN_PLACE = True
except ImportError:
    HAS_IN_PLACE = False

from ..interfaces import (
    EditRequest, EditResult, EditOperationType, EditorInterface,
    FileNotFoundException, ValidationException, OperationMetadata
)


class LineEditor(EditorInterface):
    """Editor for line-specific modifications"""
    
    def __init__(self):
        self.supported_operations = {EditOperationType.LINE, EditOperationType.RANGE}
    
    def supports_operation(self, operation_type: EditOperationType) -> bool:
        """Check if this editor supports the given operation type"""
        return operation_type in self.supported_operations
    
    async def validate_request(self, request: EditRequest) -> bool:
        """Validate if the request can be processed"""
        if not self.supports_operation(request.operation_type):
            raise ValidationException(f"LineEditor does not support {request.operation_type}")
        
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundException(f"File not found: {request.file_path}")
        
        if not file_path.is_file():
            raise ValidationException(f"Path is not a file: {request.file_path}")
        
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
            
            if request.operation_type == EditOperationType.LINE:
                result = await self._edit_line(request, operation_id)
            elif request.operation_type == EditOperationType.RANGE:
                result = await self._edit_range(request, operation_id)
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
    
    async def _edit_line(self, request: EditRequest, operation_id: str) -> EditResult:
        """Edit a specific line"""
        target_line = request.target
        if not isinstance(target_line, int):
            raise ValidationException("Line target must be an integer")
        
        lines_changed = 0
        original_content = None
        
        # Read original content for diff
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            original_content = f.read()
        
        # Use in_place if available, otherwise fallback to fileinput
        if HAS_IN_PLACE:
            lines_changed = await self._edit_line_inplace(request, target_line)
        else:
            lines_changed = await self._edit_line_fileinput(request, target_line)
        
        # Read modified content for diff
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            modified_content = f.read()
        
        # Generate diff
        diff = self._generate_diff(original_content, modified_content)
        
        return EditResult.success_result(
            operation_id=operation_id,
            file_path=request.file_path,
            operation_type=request.operation_type,
            diff=diff,
            lines_changed=lines_changed,
            bytes_changed=len(modified_content.encode()) - len(original_content.encode())
        )
    
    async def _edit_line_inplace(self, request: EditRequest, target_line: int) -> int:
        """Edit line using in_place library"""
        lines_changed = 0
        
        with in_place.InPlace(
            request.file_path, 
            encoding=request.options.encoding
        ) as file:
            for line_num, line in enumerate(file, start=1):
                if line_num == target_line:
                    file.write(request.content + '\n')
                    lines_changed = 1
                else:
                    file.write(line)
        
        return lines_changed
    
    async def _edit_line_fileinput(self, request: EditRequest, target_line: int) -> int:
        """Edit line using fileinput as fallback"""
        lines_changed = 0
        
        # Create backup if requested
        if request.options.create_backup:
            import shutil
            backup_path = f"{request.file_path}.bak"
            shutil.copy2(request.file_path, backup_path)
        
        for line in fileinput.input(
            request.file_path, 
            inplace=True, 
            encoding=request.options.encoding
        ):
            if fileinput.lineno() == target_line:
                print(request.content)
                lines_changed = 1
            else:
                print(line, end='')
        
        return lines_changed
    
    async def _edit_range(self, request: EditRequest, operation_id: str) -> EditResult:
        """Edit a range of lines"""
        target_range = request.target
        if not isinstance(target_range, range):
            raise ValidationException("Range target must be a range object")
        
        lines_changed = 0
        original_content = None
        
        # Read original content
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            original_content = f.read()
        
        # Use in_place if available
        if HAS_IN_PLACE:
            lines_changed = await self._edit_range_inplace(request, target_range)
        else:
            lines_changed = await self._edit_range_fileinput(request, target_range)
        
        # Read modified content for diff
        with open(request.file_path, 'r', encoding=request.options.encoding) as f:
            modified_content = f.read()
        
        # Generate diff
        diff = self._generate_diff(original_content, modified_content)
        
        return EditResult.success_result(
            operation_id=operation_id,
            file_path=request.file_path,
            operation_type=request.operation_type,
            diff=diff,
            lines_changed=lines_changed,
            bytes_changed=len(modified_content.encode()) - len(original_content.encode())
        )
    
    async def _edit_range_inplace(self, request: EditRequest, target_range: range) -> int:
        """Edit range using in_place library"""
        lines_changed = 0
        content_lines = request.content.split('\n') if request.content else []
        
        with in_place.InPlace(
            request.file_path,
            encoding=request.options.encoding
        ) as file:
            for line_num, line in enumerate(file, start=1):
                if line_num in target_range:
                    # Replace with new content
                    if lines_changed < len(content_lines):
                        file.write(content_lines[lines_changed] + '\n')
                    lines_changed += 1
                else:
                    file.write(line)
        
        return lines_changed
    
    async def _edit_range_fileinput(self, request: EditRequest, target_range: range) -> int:
        """Edit range using fileinput as fallback"""
        lines_changed = 0
        content_lines = request.content.split('\n') if request.content else []
        
        # Create backup if requested
        if request.options.create_backup:
            import shutil
            backup_path = f"{request.file_path}.bak"
            shutil.copy2(request.file_path, backup_path)
        
        for line in fileinput.input(
            request.file_path,
            inplace=True,
            encoding=request.options.encoding
        ):
            if fileinput.lineno() in target_range:
                if lines_changed < len(content_lines):
                    print(content_lines[lines_changed])
                lines_changed += 1
            else:
                print(line, end='')
        
        return lines_changed
    
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