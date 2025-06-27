import httpx
import base64
from typing import Any, Dict, List, Optional

class ZoektClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:6070/api/search"):
        self.endpoint = endpoint

    async def search_by_filename(self, filename: str, max_docs: int = 5) -> List[Dict[str, Any]]:
        query = {
            "Q": f"f:{filename}",
            "Opts": {"Whole": True, "MaxDocDisplayCount": max_docs}
        }
        return await self._search(query)

    async def search_by_text_and_filename(self, text: str, filename: str, max_docs: int = 5) -> List[Dict[str, Any]]:
        query = {
            "Q": f"{text} f:{filename}",
            "Opts": {"Whole": True, "MaxDocDisplayCount": max_docs}
        }
        return await self._search(query)

    async def search_by_text(self, text: str, max_docs: int = 5) -> List[Dict[str, Any]]:
        query = {
            "Q": text,
            "Opts": {"Whole": True, "MaxDocDisplayCount": max_docs}
        }
        return await self._search(query)

    async def _search(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.endpoint, json=query)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data)

    def _parse_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        files = data.get("Result", {}).get("Files") or []
        results = []
        for f in files:
            file_info = {
                "FileName": f.get("FileName"),
                "Repository": f.get("Repository"),
                "Language": f.get("Language"),
            }
            # Decode the file-level Content field once
            file_content = self._safe_b64decode(f.get("Content"))
            for match in f.get("LineMatches", []):
                results.append({
                    **file_info,
                    "LineStart": match.get("LineStart"),
                    "LineEnd": match.get("LineEnd"),
                    "LineNumber": match.get("LineNumber"),
                    "Before": match.get("Before"),
                    "After": match.get("After"),
                    "FileNameMatch": match.get("FileName"),
                    "Score": match.get("Score"),
                    "Content": file_content,
                })
        return results

    def _safe_b64decode(self, s: Optional[str]) -> str:
        if not s:
            return ""
        try:
            return base64.b64decode(s).decode("utf-8")
        except Exception:
            return "<decode error>"

def add_line_numbers_to_code(code: str) -> str:
    """
    Add line numbers to each line of code, formatted as '1. code', '2. code', ...
    """
    lines = code.splitlines()
    return "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines)) 