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
            "create": {
                "method": "POST",
                "endpoint": "/credentials",
                "body": ["name", "type", "token", "username", "password"]
            },
            "delete": {
                "method": "DELETE",
                "endpoint": "/credentials/{name}"
            }
        },
        "git": {
            "setup": {
                "method": "POST",
                "endpoint": "/git/setup",
                "body": ["repo_url", "credential_name", "workspace_path"]
            },
            "pull": {
                "method": "POST",
                "endpoint": "/git/pull",
                "params": ["workspace_path"] # Truyền qua Query Parameter
            },
            "commit": {
                "method": "POST",
                "endpoint": "/git/commit",
                "body": ["workspace_path", "message", "files"]
            },
            "push": {
                "method": "POST",
                "endpoint": "/git/push",
                "body": ["workspace_path", "branch"]
            },
            "pull_request": {
                "method": "POST",
                "endpoint": "/git/pull-request",
                "body": ["repo_url", "credential_name", "source_branch", "target_branch", "title", "description"]
            },
            "status": {
                "method": "GET",
                "endpoint": "/git/status",
                "params": ["workspace_path"] # Truyền qua Query Parameter
            },
            "branch_create": {
                "method": "POST",
                "endpoint": "/git/branch/create",
                "body": ["workspace_path", "branch_name", "checkout"]
            },
            "branch_switch": {
                "method": "POST",
                "endpoint": "/git/branch/switch",
                "body": ["workspace_path", "branch_name"]
            },
            "workflow_complete": {
                "method": "POST",
                "endpoint": "/git/workflow/complete",
                "params": ["repo_url", "credential_name", "workspace_path", "commit_message", "branch_name", "target_branch", "pr_title", "pr_description"]
            }
        }
    }
}

def base_api(api_config, body=None, params=None, path_params=None):
    """
    api_config: Object từ biến apis (ví dụ: apis["gitplugin"]["git"]["pull"])
    body: Dữ liệu gửi trong body (cho POST/PUT)
    params: Dữ liệu gửi qua URL (Query strings)
    path_params: Dữ liệu thay thế trong URL (ví dụ: {name})
    """
    method = api_config["method"]
    endpoint = api_config["endpoint"]
    
    # 1. Xử lý Path Parameters (ví dụ: /credentials/{name})
    if path_params:
        endpoint = endpoint.format(**path_params)
    
    url = f"http://localhost:8000{endpoint}" # Thay bằng URL thực tế của bạn

    try:
        # 2. Thực hiện gọi API tùy theo method
        response = requests.request(
            method=method,
            url=url,
            json=body,   # Tự động gửi JSON nếu body không None
            params=params
        )
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"API Error: {e}")
        raise e