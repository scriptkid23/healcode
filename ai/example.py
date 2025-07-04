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
        primary_model="google_gemini"
    )
    repo_processor = RepoProcessor()
    zoekt = ZoektClient()

    demo_file = "codebase/controls/control-1/main.js"
    main_js_results = await zoekt.search_by_filename("main.js")
    
    if main_js_results:
        main_js_code = main_js_results[0]["Content"]
        print("\nOriginal main.js content (from Zoekt):\n", main_js_code)

        # Create documents with line number metadata
        repo_content = f"## File: {demo_file}\n{main_js_code}"
        documents = repo_processor.create_documents_from_repo_content(repo_content)

        # Call the new debug_and_fix method with documents
        print("\nSending request to AI for analysis...")
        ai_result = await ai_service.debug_and_fix(documents=documents)
        
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
    else:
        print("Could not find main.js in the codebase via Zoekt.")

if __name__ == "__main__":
    asyncio.run(main()) 