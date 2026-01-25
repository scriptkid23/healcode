import os
import requests
from typing import Any, Dict, Optional, Union
from dotenv import load_dotenv

load_dotenv()

# Cấu hình URL mặc định giống như BACKEND_URL trong TS
BASE_URL = os.getenv("BASE_URL") or "https://khoai-axiom-backend.vercel.app"

# Cấu trúc APIs bạn đã định nghĩa
apis = {
    "gitplugin": {
        "credentials": {
            "method": "POST",
            "endpoint": "/credentials"
        }
    }
}

def base_api(api_config: Dict[str, str], body: Optional[Dict[str, Any]] = None) -> Any:
    """
    Hàm gọi API chung, tương tự apiBase trong TypeScript.
    :param api_config: Dict chứa 'method' và 'endpoint' lấy từ object 'apis'
    :param body: Dữ liệu gửi đi (JSON body)
    """
    url = f"{BASE_URL}{api_config['endpoint']}"
    method = api_config['method'].upper()
    
    headers = {
        "Content-Type": "application/json",
    }

    try:
        # requests.request cho phép truyền method linh hoạt (GET, POST, PUT,...)
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body if method != "GET" else None,
            params=body if method == "GET" else None, # Nếu là GET thì gửi qua query params
            timeout=10 # Nên có timeout để tránh treo app
        )

        # Kiểm tra nếu status code >= 400 thì nhảy vào except
        response.raise_for_status()
        
        return response.json()

    except requests.exceptions.RequestException as e:
        # Xử lý lỗi tương tự logic của bạn trong TS
        error_obj = {
            "status": 500,
            "message": str(e)
        }

        if e.response is not None:
            error_obj["status"] = e.response.status_code
            try:
                # Cố gắng lấy message từ server trả về nếu có
                server_message = e.response.json().get("message")
                if server_message:
                    error_obj["message"] = server_message
            except:
                pass
        
        # In ra lỗi hoặc raise exception tùy nhu cầu của bạn
        print(f"❌ API Error: {error_obj}")
        raise Exception(error_obj)

# --- CÁCH SỬ DỤNG ---
if __name__ == "__main__":
    # Ví dụ gọi API tạo credentials
    try:
        config = apis["gitplugin"]["credentials"]
        data = {"username": "duongess", "token": "123456"}
        
        result = base_api(config, body=data)
        print("✅ Thành công:", result)
    except Exception as e:
        print("🔥 Thất bại:", e)