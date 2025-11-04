# 📖 AI Workflows - Hướng Dẫn Sử Dụng Chi Tiết

Tài liệu này hướng dẫn cách sử dụng AI Workflows module với các ví dụ thực tế.

---

## 🚀 VÍ DỤ 1: SỬ DỤNG CƠ BẢN NHẤT

### Đây là cách đơn giản nhất để bắt đầu:

```python
import asyncio
from ai.workflows import ErrorAnalysisWorkflow, WorkflowConfig
from indexer.zoekt_client import ZoektClient

async def simple_example():
    """Ví dụ đơn giản nhất - chỉ cần 3 bước"""
    
    # Bước 1: Tạo config (dùng mặc định)
    config = WorkflowConfig()
    
    # Bước 2: Khởi tạo workflow
    workflow = ErrorAnalysisWorkflow(config)
    
    # Bước 3: Setup Zoekt (search engine)
    zoekt = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt)
    
    # Bước 4: Phân tích lỗi
    error_text = "NameError: name 'user_id' is not defined at auth.py:42"
    result = await workflow.run_analysis(error_text)
    
    # Bước 5: In kết quả
    print("✅ Phân tích thành công!")
    print(f"File lỗi: {result['error_info']['parsed_error']['file']}")
    print(f"Function: {result['function_context']['name']}")
    print(f"Risk level: {result['impact_analysis']['risk_level']}")
    print(f"\n💡 Fix suggestions:")
    for i, fix in enumerate(result['impact_analysis']['fix_suggestions'], 1):
        print(f"  {i}. {fix}")

# Chạy
asyncio.run(simple_example())
```

**Output mẫu:**
```
✅ Phân tích thành công!
File lỗi: auth.py
Function: authenticate_user
Risk level: high

💡 Fix suggestions:
  1. Define user_id before using it
  2. Pass user_id as function parameter
  3. Get user_id from session or context
```

---

## 📝 VÍ DỤ 2: XỬ LÝ KẾT QUẢ CHI TIẾT

### Cách truy cập và sử dụng các phần của kết quả:

```python
async def detailed_result_example():
    """Ví dụ xử lý kết quả chi tiết"""
    
    config = WorkflowConfig()
    workflow = ErrorAnalysisWorkflow(config)
    zoekt = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt)
    
    error_text = "AttributeError: 'NoneType' object has no attribute 'get' at user_service.py:45"
    result = await workflow.run_analysis(error_text)
    
    # 1. THÔNG TIN LỖI
    print("=" * 60)
    print("📋 THÔNG TIN LỖI")
    print("=" * 60)
    
    error_info = result['error_info']
    print(f"Lỗi gốc: {error_info['raw_error']}")
    
    parsed = error_info['parsed_error']
    if parsed:
        print(f"Loại lỗi: {parsed['type']}")
        print(f"File: {parsed['file']}")
        print(f"Dòng: {parsed['line']}")
        print(f"Cột: {parsed.get('column', 'N/A')}")
    
    # 2. THÔNG TIN FUNCTION
    print("\n" + "=" * 60)
    print("🔍 FUNCTION CHỨA LỖI")
    print("=" * 60)
    
    func_ctx = result['function_context']
    if func_ctx:
        print(f"Tên function: {func_ctx['name']}")
        print(f"File: {func_ctx['file']}")
        print(f"Ngôn ngữ: {func_ctx['language']}")
        print(f"Signature: {func_ctx['signature']}")
        print(f"Parameters: {', '.join(func_ctx.get('parameters', []))}")
        if func_ctx.get('documentation'):
            print(f"Documentation: {func_ctx['documentation'][:100]}...")
    
    # 3. DEPENDENCIES
    print("\n" + "=" * 60)
    print("🔗 DEPENDENCIES")
    print("=" * 60)
    
    deps = result['dependencies']
    print(f"Files import target file: {len(deps['dependent_files'])}")
    for file in deps['dependent_files'][:5]:  # Top 5
        print(f"  - {file}")
    
    print(f"\nUsage contexts: {deps['usage_contexts']} usages found")
    
    # 4. IMPACT ANALYSIS (Phần quan trọng nhất!)
    print("\n" + "=" * 60)
    print("💡 PHÂN TÍCH TÁC ĐỘNG & ĐỀ XUẤT FIX")
    print("=" * 60)
    
    impact = result['impact_analysis']
    print(f"Risk level: {impact['risk_level'].upper()}")  # HIGH/MEDIUM/LOW
    print(f"Confidence score: {impact['confidence_score']:.1%}")
    
    print(f"\n📁 Files bị ảnh hưởng ({len(impact['affected_files'])}):")
    for file in impact['affected_files'][:5]:
        print(f"  - {file}")
    
    print(f"\n🔧 Fix suggestions ({len(impact['fix_suggestions'])}):")
    for i, fix in enumerate(impact['fix_suggestions'], 1):
        print(f"  {i}. {fix}")
    
    if impact.get('breaking_changes'):
        print(f"\n⚠️ Breaking changes:")
        for change in impact['breaking_changes']:
            print(f"  - {change}")
    
    if impact.get('test_recommendations'):
        print(f"\n🧪 Test recommendations:")
        for test in impact['test_recommendations']:
            print(f"  - {test}")
    
    # 5. METRICS (Performance)
    print("\n" + "=" * 60)
    print("📊 METRICS")
    print("=" * 60)
    
    metrics = result['metrics']
    print(f"Thời gian thực thi: {metrics['total_execution_time_ms']}ms")
    print(f"Memory sử dụng: {metrics['total_memory_usage_mb']:.2f}MB")
    print(f"Cache hit rate: {metrics['cache_hit_rate']:.1%}")
    print(f"Cache hits: {metrics['cache_hits']}")
    print(f"Cache misses: {metrics['cache_misses']}")
    
    # 6. STATUS
    print("\n" + "=" * 60)
    print("✅ STATUS")
    print("=" * 60)
    
    status = result['status']
    if status['success']:
        print("✅ Phân tích thành công!")
    else:
        print(f"❌ Lỗi: {status['error']}")
    
    if status.get('warnings'):
        print("⚠️ Warnings:")
        for warning in status['warnings']:
            print(f"  - {warning}")

asyncio.run(detailed_result_example())
```

---

## ⚙️ VÍ DỤ 3: CUSTOM CONFIGURATION

### Tùy chỉnh config cho production hoặc development:

```python
async def custom_config_example():
    """Ví dụ với custom configuration"""
    
    # Tạo config và tùy chỉnh
    config = WorkflowConfig()
    
    # 🔒 SECURITY SETTINGS
    config.security.enable_sandboxing = True      # Bật sandboxing
    config.security.max_memory_mb = 1024          # Tăng memory limit
    config.security.max_execution_time_seconds = 300  # 5 phút timeout
    
    # ⚡ PERFORMANCE SETTINGS
    config.performance.max_concurrent_nodes = 5   # Chạy song song nhiều hơn
    config.performance.cache_ttl_seconds = 7200   # Cache 2 giờ
    config.performance.desired_cache_hit_rate = 0.9  # Target 90% cache hit
    config.performance.max_dependency_depth = 5   # Phân tích sâu hơn
    config.performance.max_files_per_search = 100 # Tìm nhiều file hơn
    
    # 🌐 LANGUAGE SUPPORT
    config.language.supported_languages = [
        'python', 'java', 'javascript', 
        'typescript', 'rust'
    ]
    config.language.fallback_to_regex = True  # Fallback nếu parser fail
    
    # 🧠 LLM SETTINGS
    config.primary_model = "google_gemini"  # Hoặc "openai", "anthropic"
    config.model_temperature = 0.05         # Thấp hơn = consistent hơn
    config.max_tokens = 4096                # Response dài hơn
    config.max_retries_per_node = 3         # Retry 3 lần nếu fail
    config.enable_llm_fallback = True       # Fallback nếu LLM fail
    
    # 📊 METRICS SETTINGS
    config.metrics.enable_metrics = True
    config.metrics.track_node_performance = True
    config.metrics.track_cache_performance = True
    config.metrics.track_memory_usage = True
    config.metrics.export_to_prometheus = True  # Export để monitoring
    
    # Validate config trước khi dùng
    issues = config.validate()
    if issues:
        print("⚠️ Config có vấn đề:")
        for issue in issues:
            print(f"  - {issue}")
        return
    
    # Khởi tạo workflow với config tùy chỉnh
    workflow = ErrorAnalysisWorkflow(config)
    zoekt = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt)
    
    # Phân tích với config đã tùy chỉnh
    error_text = "TypeError: unsupported operand type(s) for +: 'int' and 'str' at calculator.py:23"
    result = await workflow.run_analysis(error_text)
    
    print("✅ Phân tích với custom config thành công!")
    return result

asyncio.run(custom_config_example())
```

---

## 📦 VÍ DỤ 4: BATCH PROCESSING (Xử lý nhiều lỗi cùng lúc)

### Phân tích nhiều lỗi cùng một lúc:

```python
async def batch_processing_example():
    """Ví dụ xử lý nhiều lỗi cùng lúc"""
    
    config = WorkflowConfig()
    config.performance.max_concurrent_nodes = 5  # Tăng concurrency
    
    workflow = ErrorAnalysisWorkflow(config)
    zoekt = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt)
    
    # Danh sách lỗi cần phân tích
    errors = [
        "NameError: name 'user_id' is not defined at auth.py:42",
        "AttributeError: 'NoneType' object has no attribute 'get' at service.py:15",
        "TypeError: unsupported operand type(s) for +: 'int' and 'str' at calc.py:23",
        "KeyError: 'email' at user_manager.py:67",
        "IndexError: list index out of range at processor.py:89"
    ]
    
    print(f"📦 Đang phân tích {len(errors)} lỗi...")
    
    # Tạo tasks để chạy song song
    tasks = []
    for i, error_text in enumerate(errors):
        print(f"  [{i+1}/{len(errors)}] {error_text[:50]}...")
        tasks.append(workflow.run_analysis(error_text))
    
    # Chạy tất cả cùng lúc
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Xử lý kết quả
    successful = 0
    failed = 0
    total_time = 0
    high_risk_count = 0
    
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ BATCH PROCESSING")
    print("=" * 60)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"\n❌ Error {i+1} failed: {result}")
            failed += 1
            continue
        
        successful += 1
        total_time += result['metrics']['total_execution_time_ms']
        
        if result['impact_analysis']['risk_level'] == 'high':
            high_risk_count += 1
        
        print(f"\n✅ Error {i+1}:")
        print(f"   File: {result['error_info']['parsed_error']['file']}")
        print(f"   Risk: {result['impact_analysis']['risk_level']}")
        print(f"   Time: {result['metrics']['total_execution_time_ms']}ms")
        print(f"   Fixes: {len(result['impact_analysis']['fix_suggestions'])} suggestions")
    
    print("\n" + "=" * 60)
    print(f"📈 Summary:")
    print(f"   Total: {len(errors)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   High risk: {high_risk_count}")
    print(f"   Avg time: {total_time / successful if successful else 0:.0f}ms")
    print("=" * 60)
    
    return results

asyncio.run(batch_processing_example())
```

---

## 🔧 VÍ DỤ 5: TÍCH HỢP VỚI EDITOR SERVICE (Tự động fix)

### Tự động apply fixes sau khi phân tích:

```python
from editor.service import EditorService, EditorConfig
from editor.interfaces import EditOptions

async def auto_fix_example():
    """Ví dụ tự động fix lỗi sau khi phân tích"""
    
    # 1. Phân tích lỗi
    config = WorkflowConfig()
    workflow = ErrorAnalysisWorkflow(config)
    zoekt = ZoektClient("http://localhost:6070")
    workflow.setup(zoekt)
    
    error_text = "NameError: name 'total_amount' is not defined at calculator.py:67"
    result = await workflow.run_analysis(error_text)
    
    if not result['status']['success']:
        print(f"❌ Phân tích thất bại: {result['status']['error']}")
        return
    
    # 2. Kiểm tra confidence score
    confidence = result['impact_analysis']['confidence_score']
    if confidence < 0.7:
        print(f"⚠️ Confidence thấp ({confidence:.1%}), không tự động fix")
        print("💡 Suggestions:")
        for fix in result['impact_analysis']['fix_suggestions']:
            print(f"   - {fix}")
        return
    
    # 3. Lấy thông tin để fix
    file_path = result['error_info']['parsed_error']['file']
    line_number = result['error_info']['parsed_error']['line']
    
    # 4. Tạo Editor service
    editor_config = EditorConfig()
    editor = EditorService(editor_config)
    
    # 5. Apply fix suggestion đầu tiên (nếu có)
    fixes = result['impact_analysis']['fix_suggestions']
    if fixes:
        print(f"🔧 Đang apply fix: {fixes[0][:50]}...")
        
        # Đọc file để lấy context
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Tạo new content (giả sử fix đơn giản)
        original_line = lines[line_number - 1]
        # Logic fix ở đây (tùy vào loại lỗi)
        new_line = original_line.replace('total_amount', 'total')  # Ví dụ
        
        # Apply fix
        edit_result = await editor.edit_line(
            file_path=file_path,
            line_number=line_number,
            new_content=new_line,
            options=EditOptions(create_backup=True)
        )
        
        if edit_result['success']:
            print("✅ Fix applied successfully!")
            print(f"   Backup created: {edit_result.get('backup_path')}")
        else:
            print(f"❌ Fix failed: {edit_result.get('error')}")
    else:
        print("⚠️ Không có fix suggestion nào")

asyncio.run(auto_fix_example())
```

---

## 🎯 TÓM TẮT - CÁC BƯỚC QUAN TRỌNG

### ✅ Checklist khi sử dụng:

1. **Import các modules cần thiết**
   ```python
   from ai.workflows import ErrorAnalysisWorkflow, WorkflowConfig
   from indexer.zoekt_client import ZoektClient
   ```

2. **Tạo config** (dùng default hoặc custom)
   ```python
   config = WorkflowConfig()
   # hoặc custom
   config.security.max_memory_mb = 1024
   ```

3. **Khởi tạo workflow**
   ```python
   workflow = ErrorAnalysisWorkflow(config)
   ```

4. **Setup Zoekt client**
   ```python
   zoekt = ZoektClient("http://localhost:6070")
   workflow.setup(zoekt)
   ```

5. **Chạy phân tích**
   ```python
   result = await workflow.run_analysis(error_text)
   ```

6. **Xử lý kết quả**
   ```python
   if result['status']['success']:
       fixes = result['impact_analysis']['fix_suggestions']
       risk = result['impact_analysis']['risk_level']
       # ... xử lý tiếp
   ```

---

## 🎓 NEXT STEPS

1. ✅ **Thử các ví dụ trên** - Copy và chạy thử
2. ✅ **Đọc thêm**: [workflows-quick-reference.md](workflows-quick-reference.md)
3. ✅ **Chi tiết kỹ thuật**: [workflows-architecture.md](workflows-architecture.md)
4. ✅ **Xem code thực**: `ai/workflows/example_usage.py`

---

**Happy coding! 🚀**
