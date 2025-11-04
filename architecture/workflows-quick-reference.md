# AI Workflows - Quick Reference Guide

## 📚 TÓM TẮT NHANH

**Module**: `ai/workflows`  
**Mục đích**: Automated error analysis workflow với LangGraph  
**Kiến trúc**: 4-node workflow với AI-powered analysis

---

## 📁 CẤU TRÚC FILE

```
ai/workflows/
├── __init__.py                    # Package exports
├── error_analysis_graph.py        # ⭐ Main workflow engine (LangGraph)
├── config.py                      # ⚙️  Configuration system
├── state.py                       # 📊 State management (TypedDict)
├── enhanced_parsers.py            # 🔧 Multi-language code parsers
├── enhanced_zoekt_manager.py      # 🔍 Search & dependency analysis
├── few_shot_examples.py           # 📚 Few-shot learning examples
└── example_usage.py               # 📖 Usage examples
```

---

## 🔄 4-NODE WORKFLOW

```
[Error Input] 
    ↓
[Node 1: Parse Error] → Extract error info
    ↓
[Node 2: Parse File] → Find function context
    ↓
[Node 3: Find Dependencies] → Analyze imports & usages
    ↓
[Node 4: Analyze Impact] → LLM analysis + fix suggestions
    ↓
[JSON Output]
```

---

## 🎯 CÁC FILE CHÍNH

### 1️⃣ **error_analysis_graph.py** (661 dòng)
```python
# Main workflow orchestrator
class ErrorAnalysisWorkflow:
    async def run_analysis(error_text: str) -> Dict:
        # 4 nodes: parse_error → parse_file → find_dependencies → analyze_impact
        # Returns: Complete analysis with fix suggestions
```

**Features**:
- ✅ LangGraph workflow với 4 nodes
- ✅ Redis caching mỗi node
- ✅ Retry logic với exponential backoff
- ✅ Security: memory limits, timeouts, sanitization
- ✅ Metrics collection per node

### 2️⃣ **config.py** (188 dòng)
```python
# Configuration management
@dataclass
class WorkflowConfig:
    security: SecurityConfig        # Memory, timeout, sanitization
    performance: PerformanceConfig  # Cache, concurrency, limits
    language: LanguageConfig        # Supported languages, parsers
    metrics: MetricsConfig          # Monitoring, Prometheus
    
    # LLM settings
    primary_model: str = "google_gemini"
    model_temperature: float = 0.1
    max_tokens: int = 2048
```

**Cách dùng**:
```python
# From file
config = WorkflowConfig.from_file("configs/production.yaml")

# From environment
config = WorkflowConfig.from_env()

# Programmatic
config = WorkflowConfig()
config.security.max_memory_mb = 1024
```

### 3️⃣ **state.py** (248 dòng)
```python
# Workflow state schema
class AnalysisState(TypedDict):
    # Input
    raw_error: str
    workflow_id: str
    
    # Node outputs
    parsed_error: ErrorInfo
    target_function: FunctionContext
    dependent_files: List[str]
    usage_contexts: List[UsageContext]
    impact_analysis: ImpactAnalysis
    
    # Metrics
    metrics: WorkflowMetrics
    cache_hits: int
    cache_misses: int
```

**Key Types**:
- `ErrorInfo`: Parsed error (type, file, line, column)
- `FunctionContext`: Function where error occurs
- `UsageContext`: How function is used in codebase
- `ImpactAnalysis`: LLM-generated analysis

### 4️⃣ **enhanced_parsers.py** (496 dòng)
```python
# Multi-language code parsing
class MultiLanguageFunctionAnalyzer:
    def analyze_function_at_line(content, path, line) -> FunctionContext:
        # Try parsers in order:
        # 1. AST (Python)
        # 2. Tree-sitter (Java, JS, TS, Rust)
        # 3. Regex (fallback)
```

**Parsers**:
- `PythonASTParser`: AST-based (ast module)
- `TreeSitterParser`: For Java, JS, TS, Rust
- `RegexParser`: Fallback cho tất cả languages

**Security**:
- Memory limits (resource.setrlimit)
- Execution timeouts (signal.alarm)
- Sandboxed execution

### 5️⃣ **enhanced_zoekt_manager.py** (464 dòng)
```python
# Search & dependency analysis
class EnhancedZoektSearchManager:
    async def find_file_imports(target_file) -> List[DependencyInfo]:
        # Find all files importing target_file
        
    async def find_function_usages(function_name) -> List[UsageContext]:
        # Search codebase for function calls
```

**Import Detection**:
- Python: `import`, `from...import`
- Java: `import`, `import static`
- JavaScript: `import`, `require()`, dynamic `import()`
- TypeScript: `import`, `import type`
- Rust: `use`, `extern crate`

### 6️⃣ **few_shot_examples.py** (526 dòng)
```python
# Few-shot learning system
class FewShotExampleManager:
    def select_relevant_examples(error, language) -> List[ErrorExample]:
        # Smart example selection based on:
        # 1. Error type match
        # 2. Language match
        # 3. Pattern match (regex)
        # 4. Confidence score
```

**Built-in Examples**:
- Python: NameError, AttributeError, TypeError
- JavaScript: ReferenceError, TypeError
- Java: NullPointerException, IndexOutOfBounds
- TypeScript: Type errors

---

## 🚀 CÁCH SỬ DỤNG

### Basic Usage
```python
from ai.workflows import ErrorAnalysisWorkflow, WorkflowConfig
from indexer.zoekt_client import ZoektClient

# 1. Create config
config = WorkflowConfig()

# 2. Initialize workflow
workflow = ErrorAnalysisWorkflow(config)

# 3. Setup Zoekt
zoekt = ZoektClient("http://localhost:6070")
workflow.setup(zoekt)

# 4. Run analysis
result = await workflow.run_analysis(
    "NameError: name 'user_id' is not defined at auth.py:42"
)

# 5. Use result
print(result["impact_analysis"]["fix_suggestions"])
print(result["impact_analysis"]["risk_level"])  # high/medium/low
print(result["dependencies"]["dependent_files"])
```

### Advanced Configuration
```python
config = WorkflowConfig()

# Security
config.security.enable_sandboxing = True
config.security.max_memory_mb = 1024
config.security.max_execution_time_seconds = 300

# Performance
config.performance.max_concurrent_nodes = 5
config.performance.cache_ttl_seconds = 3600
config.performance.desired_cache_hit_rate = 0.9

# Language support
config.language.supported_languages = ['python', 'java', 'javascript']
config.language.fallback_to_regex = True

# LLM
config.primary_model = "google_gemini"
config.model_temperature = 0.05

# Metrics
config.metrics.enable_metrics = True
config.metrics.export_to_prometheus = True
```

### Integration với Editor
```python
from ai.workflows import ErrorAnalysisWorkflow
from editor.service import EditorService

# 1. Analyze error
workflow = ErrorAnalysisWorkflow(config)
result = await workflow.run_analysis(error_text)

# 2. Get fix suggestions
fixes = result["impact_analysis"]["fix_suggestions"]

# 3. Apply fixes (nếu có line numbers)
if result["function_context"]:
    editor = EditorService()
    await editor.edit_line(
        file_path=result["function_context"]["file"],
        line_number=result["error_info"]["parsed_error"]["line"],
        new_content=fixes[0]  # Apply first suggestion
    )
```

---

## ⚙️ CONFIGURATION OPTIONS

### SecurityConfig
```python
enable_sandboxing: bool = True              # Enable resource limits
max_memory_mb: int = 512                    # Max memory per request
max_execution_time_seconds: int = 300       # Max workflow time
sensitive_patterns: List[str]               # Patterns to redact
```

### PerformanceConfig
```python
max_ast_file_size_mb: int = 10             # Skip large files
max_concurrent_nodes: int = 3               # Parallel execution
cache_ttl_seconds: int = 3600               # Cache expiration
desired_cache_hit_rate: float = 0.8         # Target cache hit rate
max_dependency_depth: int = 3               # Limit dependency tree
max_files_per_search: int = 50              # Limit search results
```

### LanguageConfig
```python
supported_languages: List[str]              # Enabled languages
tree_sitter_parsers: Dict[str, str]        # Parser mappings
ast_languages: List[str] = ['python']      # Languages with AST
fallback_to_regex: bool = True              # Enable fallback
```

### MetricsConfig
```python
enable_metrics: bool = True                 # Enable tracking
track_node_performance: bool = True         # Per-node metrics
track_cache_performance: bool = True        # Cache stats
track_memory_usage: bool = True             # Memory tracking
export_to_prometheus: bool = False          # Prometheus export
```

---

## 📊 OUTPUT SCHEMA

```json
{
  "workflow_id": "abc-123",
  "timestamp": 1234567890,
  
  "error_info": {
    "raw_error": "NameError: name 'user_id' is not defined",
    "parsed_error": {
      "type": "NameError",
      "file": "auth.py",
      "line": 42,
      "column": 15,
      "variable": "user_id"
    }
  },
  
  "function_context": {
    "name": "authenticate_user",
    "file": "auth.py",
    "language": "python",
    "signature": "def authenticate_user(username, password):",
    "parameters": ["username", "password"],
    "documentation": "Authenticate user with credentials"
  },
  
  "dependencies": {
    "dependent_files": ["api.py", "views.py", "tests.py"],
    "import_dependencies": [
      {
        "file": "api.py",
        "type": "import",
        "line": 5,
        "statement": "from auth import authenticate_user"
      }
    ],
    "usage_contexts": 15,
    "usage_summary": [...]
  },
  
  "impact_analysis": {
    "risk_level": "high",
    "affected_files": ["api.py", "views.py"],
    "fix_suggestions": [
      "Define user_id before using it",
      "Pass user_id as function parameter",
      "Get user_id from session or context"
    ],
    "breaking_changes": [
      "Function signature may need to change"
    ],
    "test_recommendations": [
      "Add unit test for missing user_id",
      "Test authentication flow end-to-end"
    ],
    "confidence_score": 0.92
  },
  
  "metrics": {
    "total_execution_time_ms": 3420,
    "total_memory_usage_mb": 145.2,
    "cache_hit_rate": 0.75,
    "cache_hits": 3,
    "cache_misses": 1,
    "node_performance": [
      {
        "node": "parse_error",
        "execution_time_ms": 120,
        "memory_usage_mb": 5.2,
        "cache_hit": false,
        "retry_count": 0,
        "error_count": 0
      },
      {
        "node": "parse_file",
        "execution_time_ms": 450,
        "memory_usage_mb": 25.5,
        "cache_hit": true,
        "retry_count": 0,
        "error_count": 0
      },
      ...
    ]
  },
  
  "security": {
    "sensitive_data_detected": false,
    "sanitized_fields": 0
  },
  
  "status": {
    "success": true,
    "error": null,
    "warnings": []
  }
}
```

---

## 🔍 SUPPORTED ERROR FORMATS

### Python
```
NameError: name 'variable' is not defined
AttributeError: 'NoneType' object has no attribute 'get'
TypeError: unsupported operand type(s) for +: 'int' and 'str'
IndentationError: unexpected indent
```

### JavaScript
```
ReferenceError: variable is not defined
TypeError: Cannot read property 'x' of undefined
SyntaxError: Unexpected token '{'
```

### Java
```
NullPointerException at Example.java:42
ArrayIndexOutOfBoundsException: Index 5 out of bounds
ClassCastException: cannot cast X to Y
```

### TypeScript
```
TS2304: Cannot find name 'variable'
TS2339: Property 'x' does not exist on type 'Y'
```

---

## 🎯 KEY FEATURES

✅ **Multi-Language**: Python, Java, JavaScript, TypeScript, Rust  
✅ **Context-Aware**: Analyzes dependencies, imports, usage patterns  
✅ **AI-Powered**: LLM-based analysis với few-shot learning  
✅ **Production-Ready**: Security, caching, metrics, monitoring  
✅ **Extensible**: Dễ dàng thêm languages, parsers, nodes mới  
✅ **Fault-Tolerant**: Retry logic, fallback strategies  

---

## 📈 PERFORMANCE TARGETS

| Metric | Development | Production |
|--------|-------------|------------|
| Execution Time | < 5s | < 3s |
| Cache Hit Rate | > 70% | > 80% |
| Memory Usage | < 256MB | < 512MB |
| Success Rate | > 90% | > 95% |

---

## 🔗 INTEGRATION POINTS

### 1. AI Service (ai/services/ai_service.py)
```python
# Workflows được integrate vào AIService
class AIService:
    async def debug_and_fix_with_context(error_input: str):
        # Uses ErrorAnalysisWorkflow internally
        enhanced_context = await self.error_context_collector.collect_enhanced_context(error_input)
        result = await self.enhanced_chain.ainvoke(...)
        return result
```

### 2. Editor Service (editor/service.py)
```python
# Apply fixes từ workflow analysis
editor = EditorService()
await editor.edit_lines(
    file_path=file,
    line_numbers=result["line_numbers"],
    new_contents=result["new_contents"]
)
```

### 3. Git Plugin (gitplugin/)
```python
# Tạo PR với fixes
git_engine = GitOperationsEngine()
await git_engine.commit_changes(workspace, "AI: Fix error")
await git_engine.create_pull_request(...)
```

### 4. Queue Service (serve/app.py)
```python
# Background processing
@app.post("/api/fix/{repo}")
async def submit_fix_request(repo, request):
    # Submit to queue
    # Worker runs workflow
    # Apply fixes automatically
```

---

## 🐛 TROUBLESHOOTING

### Slow Execution
```bash
# Check cache hit rate
metrics.cache_hit_rate  # Should be > 0.7

# Reduce scope
config.performance.max_dependency_depth = 2
config.performance.max_files_per_search = 30
```

### Memory Errors
```bash
# Increase memory limit
config.security.max_memory_mb = 1024

# Reduce file size limit
config.performance.max_ast_file_size_mb = 5
```

### LLM Failures
```bash
# Enable fallback
config.enable_llm_fallback = True
config.enable_simple_fallback = True

# Reduce context size
# Or use faster model
config.primary_model = "google_gemini"  # Faster than GPT-4
```

---

## 📚 NEXT STEPS

1. 📖 Read full documentation: `architecture/workflows-architecture.md`
2. 🎨 View system diagram: `architecture/workflows-system-diagram.mermaid`
3. 🧪 Run examples: `python ai/workflows/example_usage.py`
4. ⚙️  Configure: Edit `ai/configs/development.yaml`
5. 🚀 Integrate: Use in your AI service or API

---

## 💡 TIPS

- 🔥 **Always validate config**: `config.validate()` before using
- 💾 **Monitor cache hit rate**: Aim for > 80% in production
- 🔒 **Enable sandboxing**: Trong production environment
- 📊 **Track metrics**: Enable Prometheus export cho monitoring
- 🧪 **Test with examples**: Use `example_usage.py` để hiểu workflow
- 🔧 **Start simple**: Use default config, optimize sau based on metrics

