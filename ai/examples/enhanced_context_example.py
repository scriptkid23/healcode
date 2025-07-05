"""
Example demonstrating the Context-Enhanced Code Analysis system

This example shows how to use the enhanced AI service to analyze code errors
with comprehensive context including function usage, dependencies, and similar patterns.
"""

import asyncio
import os
from ai.services.ai_service import AIService

async def main():
    """Demonstrate the enhanced context analysis system"""
    
    # Configuration
    tenant_id = "demo_tenant"
    redis_url = "redis://localhost:6379"
    zoekt_endpoint = "http://127.0.0.1:6070/api/search"
    
    # Model configuration (you need to provide your API keys)
    model_configs = {
        "google_gemini": {
            "name": "gemini-1.5-flash-latest",
            "api_key": os.getenv("GOOGLE_API_KEY", "your-google-api-key-here")
        },
        "openai": {
            "name": "gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")
        }
    }
    
    # Initialize enhanced AI service
    print("🚀 Initializing Enhanced AI Service...")
    enhanced_service = AIService(
        tenant_id=tenant_id,
        redis_url=redis_url,
        model_configs=model_configs,
        zoekt_endpoint=zoekt_endpoint,
        primary_model="google_gemini",
        max_context_files=10
    )
    
    # Example 1: Analyze error with enhanced context
    print("\n📋 Example 1: Enhanced Error Analysis")
    print("=" * 50)
    
    # Simulate the error from the user's example
    error_input = "input undefined error controls/control-1/main.js 32:12"
    
    print(f"Analyzing error: {error_input}")
    
    try:
        result = await enhanced_service.debug_and_fix_with_context(error_input)
        
        print("\n✅ Analysis Results:")
        print(f"📊 Confidence Score: {result.get('confidence_score', 'N/A')}")
        print(f"🔧 Lines to fix: {result.get('line_numbers', [])}")
        print(f"📝 Explanation: {result.get('explanation', 'No explanation provided')}")
        
        context_meta = result.get('context_metadata', {})
        print(f"\n🔍 Context Analysis:")
        print(f"  - Processing time: {context_meta.get('processing_time_ms', 0)}ms")
        print(f"  - Cache hit: {context_meta.get('cache_hit', False)}")
        print(f"  - Function analyzed: {context_meta.get('function_analyzed', 'None')}")
        print(f"  - Usage contexts found: {context_meta.get('usage_contexts_found', 0)}")
        print(f"  - Context summarized: {context_meta.get('context_summarized', False)}")
        
        if result.get('new_contents'):
            print(f"\n💡 Suggested fixes:")
            for i, fix in enumerate(result['new_contents'], 1):
                print(f"  {i}. {fix}")
                
    except Exception as e:
        print(f"❌ Error analysis failed: {e}")
    
    # Example 2: Function usage analysis
    print("\n📋 Example 2: Function Usage Analysis")
    print("=" * 50)
    
    function_name = "handleChange"  # From the main.js example
    file_path = "controls/control-1/main.js"
    
    print(f"Analyzing function usage: {function_name} in {file_path}")
    
    try:
        usage_result = await enhanced_service.get_function_usage_analysis(function_name, file_path)
        
        if "error" not in usage_result:
            func_info = usage_result['function']
            usage_info = usage_result['usage_analysis']
            
            print(f"\n✅ Function Analysis:")
            print(f"  - Name: {func_info['name']}")
            print(f"  - Language: {func_info['language']}")
            print(f"  - Parameters: {func_info.get('parameters', [])}")
            
            print(f"\n📈 Usage Statistics:")
            print(f"  - Total usages: {usage_info['total_usages']}")
            print(f"  - Files using function: {len(usage_info['files_using_function'])}")
            
            print(f"  - Usage by type:")
            for usage_type, count in usage_info['usage_by_type'].items():
                print(f"    • {usage_type}: {count}")
            
            if usage_result.get('similar_functions'):
                print(f"\n🔍 Similar Functions:")
                for sim_func in usage_result['similar_functions'][:3]:
                    print(f"  - {sim_func['file']} (score: {sim_func['score']:.2f})")
        else:
            print(f"❌ Function analysis failed: {usage_result['error']}")
            
    except Exception as e:
        print(f"❌ Function usage analysis failed: {e}")
    
    # Example 3: Codebase pattern analysis
    print("\n📋 Example 3: Codebase Pattern Analysis")
    print("=" * 50)
    
    try:
        pattern_result = await enhanced_service.analyze_codebase_patterns(
            language="JavaScript", 
            max_files=15
        )
        
        if "error" not in pattern_result:
            print(f"✅ Pattern Analysis Results:")
            print(f"  - Language filter: {pattern_result['language_filter']}")
            print(f"  - Files analyzed: {pattern_result['max_files_analyzed']}")
            
            print(f"\n🐛 Error Patterns Found:")
            for pattern, data in pattern_result['error_patterns'].items():
                if data['occurrences'] > 0:
                    print(f"  - {pattern}: {data['occurrences']} occurrences")
                    if data['files']:
                        print(f"    Files: {', '.join(data['files'][:3])}")
            
            if pattern_result.get('recommendations'):
                print(f"\n💡 Recommendations:")
                for i, rec in enumerate(pattern_result['recommendations'], 1):
                    print(f"  {i}. {rec}")
        else:
            print(f"❌ Pattern analysis failed: {pattern_result['error']}")
            
    except Exception as e:
        print(f"❌ Pattern analysis failed: {e}")
    
    # Example 4: Cache statistics
    print("\n📋 Example 4: Cache Performance")
    print("=" * 50)
    
    try:
        cache_stats = await enhanced_service.get_cache_statistics()
        
        if "error" not in cache_stats:
            stats = cache_stats.get('detailed_stats', {})
            print(f"✅ Cache Statistics:")
            print(f"  - Hit rate: {stats.get('hit_rate', 0):.2%}")
            print(f"  - Total requests: {stats.get('total_requests', 0)}")
            print(f"  - Cache entries: {cache_stats.get('context_entries', 0)}")
            print(f"  - Average response time: {stats.get('avg_response_time_ms', 0):.2f}ms")
            print(f"  - Total cached size: {stats.get('total_size_cached_bytes', 0)} bytes")
        else:
            print(f"❌ Cache statistics failed: {cache_stats['error']}")
            
    except Exception as e:
        print(f"❌ Cache statistics failed: {e}")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    await enhanced_service.close()
    print("✅ Done!")

def demo_error_formats():
    """Demonstrate different error input formats supported"""
    
    print("\n📋 Supported Error Input Formats:")
    print("=" * 50)
    
    examples = [
        "input undefined error main.js 33:12",
        "TypeError: Cannot read property 'value' of null at main.js:33:12", 
        "main.js:33:12 - error TS2304: Cannot find name 'input'",
        "ReferenceError: input is not defined at controls/control-1/main.js:32:12"
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example}")
    
    print("\nAll these formats will be automatically parsed and analyzed!")

if __name__ == "__main__":
    print("🔧 Context-Enhanced Code Analysis Demo")
    print("=" * 60)
    
    # Show supported error formats first
    demo_error_formats()
    
    # Run the main demo
    asyncio.run(main()) 