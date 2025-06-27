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


   

    # --- New flow: Zoekt + AI xuất tham số batch edit và sửa file main.js ---
    demo_file = "codebase/controls/control-1/main.js"
    zoekt = ZoektClient()
    main_js_results = await zoekt.search_by_filename("main.js")
    if main_js_results:
        main_js_code = main_js_results[0]["Content"]
        # Đánh số dòng trước khi hỏi AI
        main_js_code_numbered = add_line_numbers_to_code(main_js_code)
        print("\nNội dung main.js (từ Zoekt, đã đánh số dòng):\n", main_js_code_numbered)
        ai_prompt = (
            "Đọc nội dung file main.js sau (có đánh số dòng). Nếu có lỗi, hãy chỉ ra các dòng cần sửa (bắt đầu từ 1) "
            "và nội dung mới cho từng dòng để sửa lỗi. "
            "Trả về kết quả ở dạng JSON với 2 trường: line_numbers (danh sách số dòng), "
            "new_contents (danh sách nội dung mới cho từng dòng, cùng thứ tự). "
            "Chỉ trả về JSON, không giải thích gì thêm.\n"
            f"{main_js_code_numbered}"
        )
        raw_response = await ai_service.chat(ai_prompt)
        json_str = ai_service.decode_gemini_response(raw_response)
        print("\nAI trả về JSON:", json_str)
        # Loại bỏ markdown nếu có
        json_str_clean = re.sub(r"^```json|```$", "", json_str.strip(), flags=re.MULTILINE).strip()
        params = json.loads(json_str_clean)
        line_numbers = params["line_numbers"]
        new_contents = params["new_contents"]
        # Khởi tạo editor
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