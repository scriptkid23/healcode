import asyncio
from ai import AIService
from indexer.zoekt_client import ZoektClient
import os

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


    # --- New flow: dùng Zoekt để tìm main.js và hỏi AI về lỗi ---
    zoekt = ZoektClient()
    main_js_results = await zoekt.search_by_filename("main.js")
    if main_js_results:
        main_js_code = main_js_results[0]["Content"]
        print("\nNội dung main.js (từ Zoekt):\n", main_js_code)
        ai_prompt = f"Đọc nội dung file main.js sau. File này có lỗi ở dòng nào? Cách sửa ra sao?\n{main_js_code}"
        raw_response = await ai_service.chat(ai_prompt)
        answer = ai_service.decode_gemini_response(raw_response)
        print("\nAI trả lời về lỗi và cách sửa:", answer)
    else:
        print("Không tìm thấy file main.js trong codebase qua Zoekt.")

if __name__ == "__main__":
    asyncio.run(main()) 