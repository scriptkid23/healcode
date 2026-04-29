import asyncio
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Default URL config, similar to BACKEND_URL in TS
BASE_URL = os.getenv("GIT_PLUGIN_URL", "http://0.0.0.0:8000")  # Replace with your actual service URL

# API structure definitions
apis = {
    "gitplugin": {
        "credentials": {
            "list": {
                "method": "GET",
                "endpoint": "/credentials"
            },
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
                "params": ["workspace_path"] # Send via query parameters
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
                "params": ["workspace_path"] # Send via query parameters
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

async def base_api(
    api_config,
    body=None,
    params=None,
    path_params=None,
    retries: int = 2,
    retry_delay: float = 1.0,
    timeout: float = 30.0,
):
    """
    api_config: API object from the apis map (example: apis["gitplugin"]["git"]["pull"])
    body: Payload sent in request body (for POST/PUT)
    params: Data sent as URL query strings
    path_params: Placeholder replacements in endpoint path (example: {name})
    """
    method = api_config["method"]
    endpoint = api_config["endpoint"]
    
    # 1. Resolve path parameters (example: /credentials/{name})
    if path_params:
        endpoint = endpoint.format(**path_params)
    
    url = f"{BASE_URL}{endpoint}" # Replace with your actual service URL

    for attempt in range(retries + 1):
        try:
            # 2. Call API using the configured method (thread offload for async routes)
            response = await asyncio.to_thread(
                requests.request,
                method=method,
                url=url,
                json=body,   # Automatically sends JSON when body is not None
                params=params,
                timeout=timeout,
            )

            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(str(payload.get("error")))
            return payload

        except requests.RequestException as e:
            status_code = None
            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
            retriable = (
                isinstance(e, (requests.Timeout, requests.ConnectionError))
                or (status_code is not None and status_code >= 500)
            )
            if retriable and attempt < retries:
                await asyncio.sleep(retry_delay * (2 ** attempt))
                continue
            print(f"API Error: {e}")
            raise
        except Exception as e:
            print(f"API Error: {e}")
            raise
