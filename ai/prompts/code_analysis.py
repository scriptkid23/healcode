from typing import List
from pydantic import BaseModel, Field

class CodeFixMetadata(BaseModel):
    total_lines_analyzed: int = Field(description="The total number of lines in the merged document that were analyzed.")
    processing_time_ms: int = Field(description="The time in milliseconds it took the model to process the request.")
    model_used: str = Field(description="The name of the language model that was used to generate the suggestions.")

class CodeFix(BaseModel):
    line_numbers: List[int] = Field(description="A list of absolute line numbers that need to be fixed (use the line numbers shown in the content).")
    new_contents: List[str] = Field(description="A list of corrected code lines corresponding to the line_numbers.")
    metadata: CodeFixMetadata = Field(description="Metadata about the code analysis process.")

class NoIssuesFound(BaseModel):
    message: str = Field(default="No issues found.", description="A message indicating that no issues were found in the code.")

CODE_FIX_PROMPT_TEMPLATE = """You are an AI assistant that analyzes code chunks for bugs, undefined names, or logic errors. The code chunk provided below has line numbers added to help you identify issues accurately.

Your goal is to automate code-review and bug-fix suggestions by returning a strictly formatted JSON object.
{format_instructions}

Task:
1. Analyze the provided code chunk with line numbers, keeping track of file paths via the `## File: path/to/file` markers (these headers are NOT numbered).
2. Identify any lines within this chunk that contain bugs, undefined names, or logic errors.
3. For each line that needs fixing, include:
   • "line_numbers": the exact line numbers shown in the content (these are absolute line numbers from the original file).
   • "new_contents": the corrected code line WITHOUT the line number prefix.
4. Do not include lines that are already correct.
5. If no issues are found, return:
   {{ "message": "No issues found." }}
6. Use the exact line numbers shown in the content - do not calculate or convert them.
7. Only report numbered lines (file headers like "## File:" are not numbered and should be ignored).
8. If the model's output is not valid JSON, automatically retry up to 10 times; on final failure return:
   {{ "error": "Failed to parse JSON after 10 attempts." }}

Important: 
- Use the line numbers exactly as shown in the numbered content (e.g., if you see "33: some code", report line number 33)
- File headers like "## File: path/to/file" are NOT numbered - ignore these lines for numbering purposes
- For new_contents, provide only the corrected code without the line number prefix
- The line numbers correspond to the actual line positions in the original source files

Model configuration:
- Temperature: 0 (deterministic)
- Streaming: enabled
- Supports multiple providers (OpenAI, Anthropic, Google Gemini, etc.)

Here is the numbered code chunk to analyze:
{code}
""" 