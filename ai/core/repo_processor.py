from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List

class RepoProcessor:
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 0):
        # We will manage chunking manually to preserve line numbers accurately.
        # The text_splitter is not used in the new implementation.
        self.chunk_size = chunk_size

    def create_documents_from_repo_content(self, repo_content: str) -> List[Document]:
        """
        Splits the concatenated repository content into Documents, each with metadata
        about its starting line number, ensuring accuracy.
        """
        lines = repo_content.splitlines(keepends=True)
        
        docs = []
        current_chunk = ""
        start_line = 1
        
        for i, line in enumerate(lines):
            # The line number in a typical editor is 1-based
            current_line_number = i + 1

            if len(current_chunk) + len(line) > self.chunk_size:
                # Finalize the current chunk and start a new one
                if current_chunk:
                    docs.append(Document(
                        page_content=current_chunk,
                        metadata={"start_line": start_line}
                    ))
                
                # Start the new chunk
                current_chunk = line
                start_line = current_line_number
            else:
                current_chunk += line

        # Add the last remaining chunk
        if current_chunk:
            docs.append(Document(
                page_content=current_chunk,
                metadata={"start_line": start_line}
            ))
            
        return docs

    def convert_relative_to_absolute_line(self, doc: Document, relative_line: int) -> int:
        """
        Converts a line number relative to a document chunk to an absolute line
        number in the original file.
        
        Args:
            doc: Document chunk with start_line metadata
            relative_line: 1-based line number relative to the chunk (1 = first line of chunk)
        
        Returns:
            1-based absolute line number in the original repository
            
        Example:
            If chunk starts at line 10 and relative_line is 1, returns 10
            If chunk starts at line 10 and relative_line is 2, returns 11
        """
        start_line = doc.metadata.get("start_line", 1)
        return start_line + relative_line - 1

    def add_line_numbers_to_content(self, content: str, start_line: int = 1) -> str:
        """
        Add line numbers to content to help AI accurately identify lines.
        Handles file headers (## File: path) by not numbering them.
        
        Args:
            content: The content to add line numbers to
            start_line: The starting line number (1-based)
            
        Returns:
            Content with line numbers added
        """
        lines = content.splitlines()
        numbered_lines = []
        
        current_line_num = start_line
        
        for line in lines:
            # Skip numbering for file headers
            if line.strip().startswith("## File:"):
                numbered_lines.append(line)  # Keep header as-is
            else:
                numbered_lines.append(f"{current_line_num:3d}: {line}")
                current_line_num += 1
        
        return '\n'.join(numbered_lines) 