from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List

class RepoProcessor:
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 100):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def create_documents_from_repo_content(self, repo_content: str) -> List[Document]:
        """
        Splits the concatenated repository content into Documents, each with metadata
        about its starting line number.
        """
        # We assume repo_content is a single string with "## File: ..." markers
        # For now, we will treat it as one large file, but this can be extended
        # to handle per-file chunking.
        
        blocks = self.splitter.split_text(repo_content)
        
        docs = []
        current_line = 1
        for block in blocks:
            docs.append(Document(
                page_content=block,
                metadata={"start_line": current_line}
            ))
            num_lines = block.count('\\n') + 1
            current_line += num_lines
            
        return docs

    def convert_relative_to_absolute_line(self, doc: Document, relative_line: int) -> int:
        """
        Converts a line number relative to a document chunk to an absolute line
        number in the original file.
        """
        return doc.metadata["start_line"] + relative_line - 1 