from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field

class CodeFixMetadata(BaseModel):
    total_lines_analyzed: int = Field(description="The total number of lines in the merged document that were analyzed.")
    processing_time_ms: int = Field(description="The time in milliseconds it took the model to process the request.")
    model_used: str = Field(description="The name of the language model that was used to generate the suggestions.")

class CodeFix(BaseModel):
    line_numbers: List[int] = Field(description="A list of absolute line numbers within the merged document that need to be fixed.")
    new_contents: List[str] = Field(description="A list of corrected code lines corresponding to the line_numbers.")
    metadata: CodeFixMetadata = Field(description="Metadata about the code analysis process.")

class NoIssuesFound(BaseModel):
    message: str = Field(default="No issues found.", description="A message indicating that no issues were found in the code.")

CODE_FIX_PROMPT_TEMPLATE = """You are an AI assistant that understands the full codebase of a Python project. The repository contents (all files concatenated with file-path headers) are provided below.

Your goal is to automate code-review and bug-fix suggestions by returning a strictly formatted JSON object.
{format_instructions}

Task:
1. Parse the merged repository content, keeping track of file paths via the `## File: path/to/file` markers.
2. Identify any lines across any file that contain bugs, undefined names, or logic errors.
3. For each line that needs fixing, include:
   • "line_numbers": the absolute line numbers within the merged document.
   • "new_contents": the corrected code line.
4. Do not include lines that are already correct.
5. If no issues are found, return:
   {{ "message": "No issues found." }}
6. Validate that each reported line number maps to a valid file and line within that file.
7. If the model's output is not valid JSON, automatically retry up to 10 times; on final failure return:
   {{ "error": "Failed to parse JSON after 10 attempts." }}

Model configuration:
- Temperature: 0 (deterministic)
- Streaming: enabled
- Supports multiple providers (OpenAI, Anthropic, Google Gemini, etc.)

Here is the merged repository content:
{code}
""" 