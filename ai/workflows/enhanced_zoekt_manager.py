"""
Enhanced Zoekt Search Manager for LangGraph Workflow

Extends the existing ZoektSearchManager with import detection, dependency analysis,
and multi-language support for the error analysis workflow.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import time

from indexer.zoekt_client import ZoektClient
from ai.core.error_context_collector import UsageContext, FunctionContext, ErrorInfo
from ai.core.zoekt_search_manager import ZoektSearchManager
from ai.workflows.state import DependencyInfo
from ai.workflows.config import PerformanceConfig, SecurityConfig

class EnhancedZoektSearchManager(ZoektSearchManager):
    """
    Enhanced Zoekt client with import detection and comprehensive dependency analysis
    
    Extends the base ZoektSearchManager with:
    - File import detection across multiple languages
    - Dependency depth analysis
    - Security-aware search patterns
    - Performance optimizations
    """
    
    def __init__(self, 
                 zoekt_client: ZoektClient, 
                 performance_config: PerformanceConfig,
                 security_config: SecurityConfig):
        super().__init__(zoekt_client, performance_config.max_files_per_search)
        self.performance_config = performance_config
        self.security_config = security_config
        
        # Language-specific import patterns
        self.import_patterns = {
            'python': [
                r'import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)',
                r'from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import',
                r'from\s+\.([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
            ],
            'java': [
                r'import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*);',
                r'import\s+static\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*);',
            ],
            'javascript': [
                r'import\s+.*\s+from\s+[\'"]([^\'\"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)',
                r'import\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)',
            ],
            'typescript': [
                r'import\s+.*\s+from\s+[\'"]([^\'\"]+)[\'"]',
                r'import\s+type\s+.*\s+from\s+[\'"]([^\'\"]+)[\'"]',
                r'import\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)',
            ],
            'rust': [
                r'use\s+([a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)*)',
                r'extern\s+crate\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            ]
        }
    
    async def find_file_imports(self, target_file: str, language: Optional[str] = None) -> List[DependencyInfo]:
        """
        Find all files that import the target file
        
        Args:
            target_file: Path to the file to find imports for
            language: Optional language hint for better pattern matching
            
        Returns:
            List of DependencyInfo objects describing import relationships
        """
        if not language:
            language = self._detect_language_from_path(target_file)
        
        # Get the module/file name for searching
        module_name = self._extract_module_name(target_file, language)
        
        # Build search queries for this language
        search_queries = self._build_import_search_queries(module_name, language)
        
        all_dependencies = []
        
        for query in search_queries[:self.performance_config.max_concurrent_nodes]:
            try:
                results = await self.zoekt_client.search_by_text(
                    query, 
                    max_docs=self.performance_config.max_files_per_search
                )
                
                dependencies = await self._extract_import_dependencies(
                    results, target_file, language
                )
                all_dependencies.extend(dependencies)
                
            except Exception as e:
                print(f"Import search failed for query '{query}': {e}")
                continue
        
        # Remove duplicates and filter by relevance
        return self._deduplicate_dependencies(all_dependencies)
    
    async def analyze_dependency_chain(self, 
                                     target_file: str, 
                                     max_depth: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze the full dependency chain for a file
        
        Args:
            target_file: File to analyze dependencies for
            max_depth: Maximum depth to traverse (default from config)
            
        Returns:
            Dictionary containing dependency tree and analysis
        """
        max_depth = max_depth or self.performance_config.max_dependency_depth
        
        dependency_tree = {}
        visited_files = set()
        
        async def traverse_dependencies(file_path: str, current_depth: int):
            if current_depth >= max_depth or file_path in visited_files:
                return
            
            visited_files.add(file_path)
            language = self._detect_language_from_path(file_path)
            
            # Find files that import this file
            importers = await self.find_file_imports(file_path, language)
            
            # Find files that this file imports
            imported_files = await self._find_files_imported_by(file_path, language)
            
            dependency_tree[file_path] = {
                'depth': current_depth,
                'language': language,
                'importers': [dep.file_path for dep in importers],
                'imports': imported_files,
                'import_details': importers
            }
            
            # Recursively analyze importers
            for importer in importers:
                if importer.file_path not in visited_files:
                    await traverse_dependencies(importer.file_path, current_depth + 1)
        
        await traverse_dependencies(target_file, 0)
        
        return {
            'target_file': target_file,
            'dependency_tree': dependency_tree,
            'total_files_analyzed': len(visited_files),
            'max_depth_reached': max(
                info['depth'] for info in dependency_tree.values()
            ) if dependency_tree else 0,
            'languages_involved': list(set(
                info['language'] for info in dependency_tree.values()
            ))
        }
    
    async def find_cross_language_dependencies(self, target_file: str) -> List[DependencyInfo]:
        """
        Find dependencies that cross language boundaries
        
        This is useful for polyglot codebases where files in different languages
        might depend on each other through APIs, shared libraries, etc.
        """
        target_language = self._detect_language_from_path(target_file)
        all_dependencies = []
        
        # Search for the target file in different language contexts
        for language in ['python', 'java', 'javascript', 'typescript', 'rust']:
            if language != target_language:
                try:
                    deps = await self.find_file_imports(target_file, language)
                    cross_language_deps = [
                        dep for dep in deps 
                        if self._detect_language_from_path(dep.file_path) != target_language
                    ]
                    all_dependencies.extend(cross_language_deps)
                except Exception as e:
                    print(f"Cross-language dependency search failed for {language}: {e}")
        
        return all_dependencies
    
    def _build_import_search_queries(self, module_name: str, language: str) -> List[str]:
        """Build search queries to find imports of a module"""
        queries = []
        patterns = self.import_patterns.get(language, [])
        
        for pattern in patterns:
            # Replace the capture group with the actual module name
            query = pattern.replace('([a-zA-Z_][a-zA-Z0-9_]*(?:\\.[a-zA-Z_][a-zA-Z0-9_]*)*)', module_name)
            query = query.replace('([^\'\"]+)', module_name)
            query = query.replace('([a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)*)', module_name)
            queries.append(query)
        
        # Add generic searches
        queries.extend([
            f'import.*{module_name}',
            f'require.*{module_name}',
            f'use.*{module_name}',
            module_name  # Simple name search
        ])
        
        return queries
    
    def _extract_module_name(self, file_path: str, language: str) -> str:
        """Extract the module name from a file path based on language conventions"""
        path = Path(file_path)
        
        if language == 'python':
            # For Python, use the file name without extension
            return path.stem
        elif language == 'java':
            # For Java, might need to consider package structure
            return path.stem
        elif language in ['javascript', 'typescript']:
            # For JS/TS, could be relative path or npm package
            return str(path.with_suffix(''))
        elif language == 'rust':
            # For Rust, use crate name or module path
            return path.stem
        else:
            return path.stem
    
    async def _extract_import_dependencies(self, 
                                         search_results: List[Dict[str, Any]], 
                                         target_file: str, 
                                         language: str) -> List[DependencyInfo]:
        """Extract dependency information from search results"""
        dependencies = []
        patterns = self.import_patterns.get(language, [])
        
        for result in search_results:
            file_path = result.get("FileName", "")
            
            # Skip the target file itself
            if file_path == target_file:
                continue
            
            line_matches = result.get("LineMatches", [])
            
            for line_match in line_matches:
                line_number = line_match.get("LineNumber", 0)
                line_content = self._get_line_content_from_match(line_match, result)
                
                # Check if this line contains an import of our target
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match and self._is_import_match(match.group(1), target_file, language):
                        import_type = self._determine_import_type(line_content, language)
                        
                        dependency = DependencyInfo(
                            file_path=file_path,
                            import_type=import_type,
                            line_number=line_number,
                            import_statement=line_content.strip()
                        )
                        dependencies.append(dependency)
                        break
        
        return dependencies
    
    def _is_import_match(self, imported_name: str, target_file: str, language: str) -> bool:
        """Check if the imported name matches our target file"""
        target_module = self._extract_module_name(target_file, language)
        
        # Direct match
        if imported_name == target_module:
            return True
        
        # Check for partial matches (e.g., relative imports)
        if target_module in imported_name or imported_name in target_module:
            return True
        
        # Check for path-based matches
        if language in ['javascript', 'typescript']:
            # Handle relative imports like './module' or '../module'
            normalized_import = imported_name.replace('./', '').replace('../', '')
            if normalized_import == target_module:
                return True
        
        return False
    
    def _determine_import_type(self, line_content: str, language: str) -> str:
        """Determine the type of import statement"""
        line = line_content.lower().strip()
        
        if language == 'python':
            if line.startswith('from'):
                return 'from_import'
            elif line.startswith('import'):
                return 'import'
        elif language == 'java':
            if 'static' in line:
                return 'static_import'
            else:
                return 'import'
        elif language in ['javascript', 'typescript']:
            if 'require(' in line:
                return 'require'
            elif 'import(' in line:
                return 'dynamic_import'
            elif 'import' in line and 'from' in line:
                return 'es6_import'
        elif language == 'rust':
            if 'extern crate' in line:
                return 'extern_crate'
            elif 'use' in line:
                return 'use'
        
        return 'unknown'
    
    async def _find_files_imported_by(self, file_path: str, language: str) -> List[str]:
        """Find files that are imported by the given file"""
        try:
            # Read the file content to analyze its imports
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            imported_files = []
            patterns = self.import_patterns.get(language, [])
            
            for line in content.split('\n'):
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        imported_name = match.group(1)
                        # Convert import name to potential file path
                        potential_file = self._resolve_import_to_file(imported_name, file_path, language)
                        if potential_file:
                            imported_files.append(potential_file)
            
            return imported_files
            
        except Exception as e:
            print(f"Failed to analyze imports in {file_path}: {e}")
            return []
    
    def _resolve_import_to_file(self, import_name: str, current_file: str, language: str) -> Optional[str]:
        """Resolve an import statement to an actual file path"""
        current_dir = Path(current_file).parent
        
        if language == 'python':
            # Handle relative imports
            if import_name.startswith('.'):
                relative_path = import_name.replace('.', '/') + '.py'
                return str(current_dir / relative_path)
            else:
                # Absolute import - would need more sophisticated resolution
                return import_name.replace('.', '/') + '.py'
        
        elif language in ['javascript', 'typescript']:
            if import_name.startswith('./') or import_name.startswith('../'):
                # Relative import
                return str(current_dir / import_name)
            else:
                # Could be npm package or absolute path
                return import_name
        
        elif language == 'java':
            # Java package to file path conversion
            return import_name.replace('.', '/') + '.java'
        
        elif language == 'rust':
            # Rust module resolution is complex, simplified here
            return import_name.replace('::', '/') + '.rs'
        
        return None
    
    def _deduplicate_dependencies(self, dependencies: List[DependencyInfo]) -> List[DependencyInfo]:
        """Remove duplicate dependencies and sort by relevance"""
        seen = set()
        unique_deps = []
        
        for dep in dependencies:
            key = (dep.file_path, dep.line_number, dep.import_statement)
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)
        
        # Sort by file path for consistent ordering
        unique_deps.sort(key=lambda x: x.file_path)
        return unique_deps
    
    def _detect_language_from_path(self, file_path: str) -> str:
        """Detect programming language from file path"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.java': 'java',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.rs': 'rust',
            '.go': 'go',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp'
        }
        
        return language_map.get(ext, 'unknown')
    
    async def get_dependency_metrics(self, target_file: str) -> Dict[str, Any]:
        """Get comprehensive metrics about file dependencies"""
        start_time = time.time()
        
        # Analyze dependencies
        dependency_analysis = await self.analyze_dependency_chain(target_file)
        
        # Find cross-language dependencies
        cross_lang_deps = await self.find_cross_language_dependencies(target_file)
        
        # Calculate metrics
        dependency_tree = dependency_analysis['dependency_tree']
        
        total_importers = sum(
            len(info['importers']) for info in dependency_tree.values()
        )
        
        total_imports = sum(
            len(info['imports']) for info in dependency_tree.values()
        )
        
        return {
            'target_file': target_file,
            'analysis_time_ms': int((time.time() - start_time) * 1000),
            'total_files_in_chain': len(dependency_tree),
            'total_importers': total_importers,
            'total_imports': total_imports,
            'max_depth': dependency_analysis['max_depth_reached'],
            'languages_involved': dependency_analysis['languages_involved'],
            'cross_language_dependencies': len(cross_lang_deps),
            'dependency_density': total_importers / max(len(dependency_tree), 1),
            'complexity_score': self._calculate_complexity_score(dependency_tree)
        }
    
    def _calculate_complexity_score(self, dependency_tree: Dict[str, Any]) -> float:
        """Calculate a complexity score for the dependency tree"""
        if not dependency_tree:
            return 0.0
        
        # Factors that increase complexity:
        # - Number of files
        # - Depth of dependencies
        # - Cross-language dependencies
        # - Circular dependencies (if detected)
        
        file_count = len(dependency_tree)
        max_depth = max(info['depth'] for info in dependency_tree.values())
        language_count = len(set(info['language'] for info in dependency_tree.values()))
        
        # Simple complexity formula (can be refined)
        complexity = (file_count * 0.3) + (max_depth * 0.4) + (language_count * 0.3)
        
        return min(complexity, 10.0)  # Cap at 10.0 