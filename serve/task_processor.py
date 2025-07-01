"""
Task processor for handling code fix requests
"""

import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .models import TaskInfo

logger = logging.getLogger(__name__)


class TaskProcessor:
    """Processes code fix tasks by coordinating AI and editor services"""
    
    def __init__(self):
        # Services will be initialized when needed to avoid import issues
        self.ai_service = None
        self.git_ops = None
    
    def process_fix_request(self, task: TaskInfo) -> Dict[str, Any]:
        """
        Process a code fix request
        
        Args:
            task: Task information containing repo_name and trace_error
            
        Returns:
            Dictionary with fix results
        """
        logger.info(f"Processing fix request for repo: {task.repo_name}")
        
        try:
            # Step 1: Analyze the error trace
            analysis_result = self._analyze_error_trace(task.trace_error)
            
            # Step 2: Get repository context (if available)
            repo_context = self._get_repo_context(task.repo_name)
            
            # Step 3: Generate fix suggestions using AI
            fix_suggestions = self._generate_fix_suggestions(
                task.trace_error, 
                analysis_result, 
                repo_context
            )
            
            # Step 4: Apply fixes (simulation for now)
            applied_fixes = self._apply_fixes(
                task.repo_name,
                fix_suggestions,
                repo_context
            )
            
            # Step 5: Compile results
            result = {
                'repo_name': task.repo_name,
                'analysis': analysis_result,
                'fix_suggestions': fix_suggestions,
                'applied_fixes': applied_fixes,
                'files_modified': len(applied_fixes.get('modified_files', [])),
                'success': True,
                'message': 'Code fix completed successfully'
            }
            
            logger.info(f"Fix request completed for repo: {task.repo_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing fix request for {task.repo_name}: {e}")
            return {
                'repo_name': task.repo_name,
                'success': False,
                'error': str(e),
                'message': 'Fix request failed'
            }
    
    def _analyze_error_trace(self, trace_error: str) -> Dict[str, Any]:
        """
        Analyze error trace to extract meaningful information
        
        Args:
            trace_error: The error trace string
            
        Returns:
            Analysis results
        """
        logger.debug("Analyzing error trace...")
        
        # Basic error analysis (can be enhanced with AI)
        analysis = {
            'error_type': self._extract_error_type(trace_error),
            'file_locations': self._extract_file_locations(trace_error),
            'error_patterns': self._identify_error_patterns(trace_error),
            'severity': self._assess_error_severity(trace_error),
            'suggested_approach': []
        }
        
        # Determine suggested fix approach based on error type
        if 'ImportError' in trace_error or 'ModuleNotFoundError' in trace_error:
            analysis['suggested_approach'].append('missing_import')
        if 'SyntaxError' in trace_error:
            analysis['suggested_approach'].append('syntax_fix')
        if 'NameError' in trace_error:
            analysis['suggested_approach'].append('undefined_variable')
        if 'AttributeError' in trace_error:
            analysis['suggested_approach'].append('missing_attribute')
        if 'TypeError' in trace_error:
            analysis['suggested_approach'].append('type_mismatch')
        
        return analysis
    
    def _extract_error_type(self, trace_error: str) -> str:
        """Extract the main error type from trace"""
        lines = trace_error.split('\n')
        for line in reversed(lines):
            if ':' in line and any(error_type in line for error_type in 
                                 ['Error', 'Exception', 'Warning']):
                return line.split(':')[0].strip()
        return 'UnknownError'
    
    def _extract_file_locations(self, trace_error: str) -> list:
        """Extract file paths and line numbers from trace"""
        locations = []
        lines = trace_error.split('\n')
        
        for line in lines:
            if 'File "' in line and 'line ' in line:
                try:
                    # Extract file path
                    start = line.find('File "') + 6
                    end = line.find('"', start)
                    file_path = line[start:end]
                    
                    # Extract line number
                    line_start = line.find('line ') + 5
                    line_end = line.find(',', line_start)
                    if line_end == -1:
                        line_end = line.find(' ', line_start)
                    line_number = int(line[line_start:line_end]) if line_end > line_start else None
                    
                    locations.append({
                        'file': file_path,
                        'line': line_number
                    })
                except (ValueError, IndexError):
                    continue
        
        return locations
    
    def _identify_error_patterns(self, trace_error: str) -> list:
        """Identify common error patterns"""
        patterns = []
        
        if 'cannot import name' in trace_error.lower():
            patterns.append('import_name_error')
        if 'no module named' in trace_error.lower():
            patterns.append('missing_module')
        if 'unexpected token' in trace_error.lower():
            patterns.append('syntax_error')
        if 'undefined variable' in trace_error.lower():
            patterns.append('undefined_variable')
        if 'object has no attribute' in trace_error.lower():
            patterns.append('missing_attribute')
        
        return patterns
    
    def _assess_error_severity(self, trace_error: str) -> str:
        """Assess the severity of the error"""
        if 'SyntaxError' in trace_error:
            return 'high'
        elif 'ImportError' in trace_error or 'ModuleNotFoundError' in trace_error:
            return 'medium'
        elif 'Warning' in trace_error:
            return 'low'
        else:
            return 'medium'
    
    def _get_repo_context(self, repo_name: str) -> Dict[str, Any]:
        """
        Get repository context (structure, dependencies, etc.)
        
        Args:
            repo_name: Repository name
            
        Returns:
            Repository context information
        """
        logger.debug(f"Getting context for repo: {repo_name}")
        
        # Simulated repo context (in real implementation, would scan actual repo)
        context = {
            'repo_name': repo_name,
            'language': 'python',  # Could be detected from file extensions
            'framework': None,      # Could be detected from requirements/package.json
            'dependencies': [],     # Would be extracted from requirements.txt, etc.
            'file_structure': [],   # Would scan directory structure
            'common_patterns': []   # Code patterns found in the repo
        }
        
        # Simulate some realistic context
        if 'flask' in repo_name.lower():
            context['framework'] = 'flask'
            context['dependencies'] = ['flask', 'werkzeug', 'jinja2']
        elif 'django' in repo_name.lower():
            context['framework'] = 'django'
            context['dependencies'] = ['django', 'pillow', 'psycopg2']
        elif 'fastapi' in repo_name.lower():
            context['framework'] = 'fastapi'
            context['dependencies'] = ['fastapi', 'uvicorn', 'pydantic']
        
        return context
    
    def _generate_fix_suggestions(self, trace_error: str, analysis: Dict[str, Any], 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate fix suggestions using AI service
        
        Args:
            trace_error: Original error trace
            analysis: Error analysis results
            context: Repository context
            
        Returns:
            Fix suggestions
        """
        logger.debug("Generating fix suggestions...")
        
        # Prepare prompt for AI service
        prompt = self._build_fix_prompt(trace_error, analysis, context)
        
        try:
            # Use AI service to generate suggestions (mock for now)
            ai_response = {
                'suggestions': [
                    {
                        'type': 'code_change',
                        'file': analysis['file_locations'][0]['file'] if analysis['file_locations'] else 'unknown.py',
                        'line': analysis['file_locations'][0]['line'] if analysis['file_locations'] else 1,
                        'original_code': '# Original problematic code',
                        'fixed_code': '# Fixed code',
                        'explanation': 'Fixed the issue by correcting the syntax/import/logic',
                        'confidence': 0.85
                    }
                ],
                'explanation': 'AI-generated explanation of the fix',
                'alternative_approaches': []
            }
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating AI fix suggestions: {e}")
            return {
                'suggestions': [],
                'explanation': f'Failed to generate AI suggestions: {e}',
                'alternative_approaches': []
            }
    
    def _build_fix_prompt(self, trace_error: str, analysis: Dict[str, Any], 
                         context: Dict[str, Any]) -> str:
        """Build prompt for AI service"""
        prompt = f"""
Please analyze this error and suggest fixes:

Error Trace:
{trace_error}

Error Analysis:
- Type: {analysis['error_type']}
- Severity: {analysis['severity']}
- Patterns: {', '.join(analysis['error_patterns'])}

Repository Context:
- Language: {context['language']}
- Framework: {context.get('framework', 'None')}
- Dependencies: {', '.join(context['dependencies'])}

Please provide specific code fixes with explanations.
"""
        return prompt
    
    def _apply_fixes(self, repo_name: str, fix_suggestions: Dict[str, Any], 
                    context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply the suggested fixes to the repository
        
        Args:
            repo_name: Repository name
            fix_suggestions: AI-generated fix suggestions
            context: Repository context
            
        Returns:
            Results of applied fixes
        """
        logger.debug(f"Applying fixes to repo: {repo_name}")
        
        applied_fixes = {
            'modified_files': [],
            'created_files': [],
            'deleted_files': [],
            'git_changes': [],
            'success_count': 0,
            'failure_count': 0,
            'details': []
        }
        
        try:
            for suggestion in fix_suggestions.get('suggestions', []):
                if suggestion['type'] == 'code_change':
                    result = self._apply_code_change(repo_name, suggestion)
                    applied_fixes['details'].append(result)
                    
                    if result['success']:
                        applied_fixes['success_count'] += 1
                        if result['file'] not in applied_fixes['modified_files']:
                            applied_fixes['modified_files'].append(result['file'])
                    else:
                        applied_fixes['failure_count'] += 1
            
            # Simulate git operations (in real implementation, would use GitOperations)
            if applied_fixes['modified_files']:
                applied_fixes['git_changes'] = [
                    f"Modified {len(applied_fixes['modified_files'])} files",
                    "Created commit with fixes",
                    "Ready for review"
                ]
            
            return applied_fixes
            
        except Exception as e:
            logger.error(f"Error applying fixes: {e}")
            applied_fixes['error'] = str(e)
            return applied_fixes
    
    def _apply_code_change(self, repo_name: str, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a single code change suggestion
        
        Args:
            repo_name: Repository name
            suggestion: Single fix suggestion
            
        Returns:
            Result of applying the change
        """
        file_path = suggestion.get('file', 'unknown.py')
        
        try:
            # In real implementation, would:
            # 1. Read the actual file
            # 2. Apply the suggested change
            # 3. Use appropriate editor strategy
            # 4. Validate the change
            # 5. Save the file
            
            # For now, simulate the process
            time.sleep(0.1)  # Simulate processing time
            
            return {
                'success': True,
                'file': file_path,
                'line': suggestion.get('line', 1),
                'change_type': suggestion.get('type', 'code_change'),
                'message': f"Successfully applied fix to {file_path}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'file': file_path,
                'error': str(e),
                'message': f"Failed to apply fix to {file_path}"
            } 