import asyncio
from ai import AIService
from indexer.zoekt_client import ZoektClient, add_line_numbers_to_code
import os
from editor import EditorService
from editor.service import EditorConfig
from editor.interfaces import EditOptions
import json
import re

async def main():
    # Model configurations for xai (add openai if needed)
    model_configs = {
        "xai": {
            "name": "grok-3-latest",
            "endpoint": "https://api.x.ai/v1/chat/completions",
            "api_key": "your-xai-key"
        },
        "google_gemini": {
            "name": "gemini-pro",
            "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "api_key": "AIzaSyBKPHuJidiLJhTRaAFNuuJInHXiwJy7hwk"
        }
        # Add more models here if needed
    }

    # Initialize AIService
    ai_service = AIService(
        tenant_id="tenant1",
        redis_url="redis://localhost:6380",
        model_configs=model_configs,
        primary_model="google_gemini"
    )


    demo_file = "codebase/controls/control-1/main.js"
    zoekt = ZoektClient()
    main_js_results = await zoekt.search_by_filename("main.js")
    if main_js_results:
        main_js_code = main_js_results[0]["Content"]
        main_js_code_numbered = add_line_numbers_to_code(main_js_code)
        print("\nNội dung main.js (từ Zoekt, đã đánh số dòng):\n", main_js_code_numbered)
        ai_prompt = (
            "Below is the content of main.js, with each line numbered in the format \"1. code\", \"2. code\", etc.\n\n"
            "Your task:\n"
            "- Carefully review the code and identify any lines that contain bugs, undefined variables, or logic errors.\n"
            "- For each line that needs to be fixed, provide the corrected content for that line.\n"
            "- Only include lines that actually need to be changed (do not include lines that are already correct).\n"
            "- Return your answer as a JSON object with two fields:\n"
            "  - \"line_numbers\": a list of line numbers (integers, starting from 1) that should be changed.\n"
            "  - \"new_contents\": a list of the new content for each corresponding line, in the same order.\n"
            "- Only output the JSON object, with no explanation or extra text.\n\n"
            "Here is the code:\n"
            f"{main_js_code_numbered}"
        )
        raw_response = await ai_service.chat(ai_prompt)
        json_str = ai_service.decode_gemini_response(raw_response)
        print("\nAI trả về JSON:", json_str)
        json_str_clean = re.sub(r"^```json|```$", "", json_str.strip(), flags=re.MULTILINE).strip()
        params = json.loads(json_str_clean)
        line_numbers = params["line_numbers"]
        new_contents = params["new_contents"]
        config = EditorConfig()
        editor = EditorService(config)
        result_batch = await editor.edit_lines(
            file_path=demo_file,
            line_numbers=line_numbers,
            new_contents=new_contents,
            options=EditOptions(create_backup=True)
        )
        print("\nKết quả batch edit:", result_batch)
    else:
        print("Không tìm thấy file main.js trong codebase qua Zoekt.")

if __name__ == "__main__":
    asyncio.run(main()) 