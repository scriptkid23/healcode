import aiohttp
import json
from typing import List, Dict, Any
from pathlib import Path

class AISuggestionService:
    """
    AI Service to process error messages, search for relevant files, load context, and suggest edits.
    """
    def __init__(self, search_api_url: str = 'http://127.0.0.1:6070/api/search'):
        self.search_api_url = search_api_url

    async def search_files(self, query: str, max_docs: int = 5) -> List[Dict[str, Any]]:
        """
        Call the search API to find relevant files.
        """
        payload = {
            "Q": query,
            "Opts": {
                "Whole": True,
                "MaxDocDisplayCount": max_docs
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.search_api_url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Search API error: {resp.status}")
                data = await resp.json()
                return data.get('Files', [])

    async def load_file_context(self, file_path: str, lines: List[int], context_window: int = 5) -> str:
        """
        Load context lines from a file around the specified lines.
        """
        path = Path(file_path)
        if not path.exists():
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        context = []
        for line_num in lines:
            start = max(0, line_num - context_window - 1)
            end = min(len(all_lines), line_num + context_window)
            context.extend(all_lines[start:end])
        return ''.join(context)

    async def process_error_message(self, error_message: str) -> Dict[str, Any]:
        """
        Main entry: parse error message, search files, load context, and suggest edits.
        Returns a dict with file, line_numbers, and suggested new_contents.
        """
        # 1. Parse error message (placeholder: extract file and line if present)
        import re
        match = re.search(r"([\w./\\-]+):(\d+)", error_message)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))
            query = f"{Path(file_path).stem} f:{Path(file_path).name}"
        else:
            # Fallback: use error message as query
            file_path = None
            line_number = None
            query = error_message

        # 2. Search for relevant files
        files = await self.search_files(query)
        if not files:
            return {"error": "No relevant files found"}

        # 3. For each file, load context (for now, just the first file)
        target_file = files[0].get('FileName') if isinstance(files[0], dict) else files[0]
        if not target_file:
            return {"error": "No file name in search result"}
        # For demo, suggest editing line 2-4
        line_numbers = [2, 3, 4]
        context = await self.load_file_context(target_file, line_numbers)

        # 4. AI logic placeholder: suggest new contents (could call LLM here)
        new_contents = [
            '# AI suggestion: fix line 2',
            '# AI suggestion: fix line 3',
            '# AI suggestion: fix line 4'
        ]
        return {
            "file_path": target_file,
            "line_numbers": line_numbers,
            "new_contents": new_contents,
            "context": context
        } 