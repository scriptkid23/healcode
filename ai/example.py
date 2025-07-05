import asyncio
import sys
import os
sys.path.append(os.getcwd())

from ai.services.ai_service import AIService
from ai.core.repo_processor import RepoProcessor
from indexer.zoekt_client import ZoektClient
import os
from editor.service import EditorService, EditorConfig
from editor.interfaces import EditOptions
import json
import logging

# Configure logging to see the context file loading information
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    # Model configurations (ensure API keys are set as environment variables or directly)
    model_configs = {
        "google_gemini": {
            "name": "gemini-1.5-flash-latest",
            "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            "api_key": os.environ.get("GOOGLE_API_KEY", "AIzaSyBKPHuJidiLJhTRaAFNuuJInHXiwJy7hwk")
        }
        # Add more models here if needed, e.g., OpenAI
        # "openai": {
        #     "name": "gpt-4",
        #     "api_key": os.environ.get("OPENAI_API_KEY", "your-openai-api-key")
        # }
    }

    # Initialize services
    ai_service = AIService(
        tenant_id="tenant1",
        redis_url="redis://localhost:6380",
        model_configs=model_configs,
        zoekt_endpoint="http://127.0.0.1:6070/api/search",
        primary_model="google_gemini",
        max_context_files=10
    )
    repo_processor = RepoProcessor()
    zoekt = ZoektClient()

    demo_file = "codebase/controls/control-1/main.js"
    main_js_results = await zoekt.search_by_filename("main.js")
    
    if main_js_results:
        main_js_code = main_js_results[0]["Content"]
        print("\nOriginal main.js content (from Zoekt):\n", main_js_code)

        # Create error input for enhanced context analysis
        # Format: "variable_name error_type error file_path line:column"
        error_input = f"code_analysis general_analysis error {demo_file} 1:1"
        
        # Call the enhanced debug_and_fix_with_context method
        print("\nSending request to Enhanced AI for analysis...")
        ai_result = await ai_service.debug_and_fix_with_context(error_input)
        
        print("\nAI response:", json.dumps(ai_result, indent=2))

        # Check if there are fixes to apply
        if "line_numbers" in ai_result and ai_result["line_numbers"]:
            line_numbers = ai_result["line_numbers"]
            new_contents = ai_result["new_contents"]
            
            config = EditorConfig()
            editor = EditorService(config)
            
            result_batch = await editor.edit_lines(
                file_path=demo_file,
                line_numbers=line_numbers,
                new_contents=new_contents,
                options=EditOptions(create_backup=True)
            )
            print("\nBatch edit result:", result_batch)
        else:
            print("\nNo issues found by AI.")
            
        # Demo enhanced features
        print("\n" + "="*50)
        print("ENHANCED AI SERVICE DEMO FEATURES")
        print("="*50)
        
        # 1. Chat demo
        print("\n1. Chat Demo:")
        chat_response = await ai_service.chat("What are the common JavaScript patterns in this codebase?")
        print(f"Chat response: {chat_response[:200]}...")
        
        # 2. Function analysis demo (if we find functions in the code)
        print("\n2. Function Analysis Demo:")
        if "function" in main_js_code.lower():
            # Try to analyze a function (example with common function name)
            function_analysis = await ai_service.get_function_usage_analysis("main", demo_file)
            print(f"Function analysis: {json.dumps(function_analysis, indent=2)}")
        else:
            print("No functions found for analysis demo")
        
        # 3. Codebase patterns analysis
        print("\n3. Codebase Patterns Analysis:")
        patterns_analysis = await ai_service.analyze_codebase_patterns(language="javascript", max_files=5)
        print(f"Patterns analysis: {json.dumps(patterns_analysis, indent=2)}")
        
        # 4. Cache statistics
        print("\n4. Cache Statistics:")
        cache_stats = await ai_service.get_cache_statistics()
        print(f"Cache statistics: {json.dumps(cache_stats, indent=2)}")
        
        # Close the service
        await ai_service.close()
        
    else:
        print("Could not find main.js in the codebase via Zoekt.")

if __name__ == "__main__":
    asyncio.run(main()) 