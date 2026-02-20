"""
Document loader for various file formats
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
from docx import Document
import tiktoken

from .config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    SUPPORTED_EXTENSIONS,
)


class DocumentLoader:
    """Loads and chunks documents from various file formats"""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def load_directory(self, directory: str) -> List[Dict[str, Any]]:
        """Load all supported documents from a directory"""
        documents = []
        directory_path = Path(directory)

        if not directory_path.exists():
            raise ValueError(f"Directory not found: {directory}")

        for file_path in directory_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    docs = self.load_file(str(file_path))
                    documents.extend(docs)
                except Exception as e:
                    print(f"Warning: Failed to load {file_path}: {e}")

        return documents

    def load_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load a single file and return chunked documents"""
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise ValueError(f"File not found: {file_path}")

        extension = file_path_obj.suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")

        # Extract text based on file type
        if extension == ".txt":
            text = self._load_txt(file_path)
        elif extension == ".pdf":
            text = self._load_pdf(file_path)
        elif extension == ".docx":
            text = self._load_docx(file_path)
        elif extension == ".epub":
            text = self._load_epub(file_path)
        else:
            raise ValueError(f"Unsupported extension: {extension}")

        # Generate metadata
        metadata = self._generate_metadata(file_path)

        # Chunk the text
        chunks = self._chunk_text(text)

        # Create document dicts
        documents = []
        for i, chunk in enumerate(chunks):
            doc = {
                "content": chunk,
                "metadata": {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            }
            documents.append(doc)

        return documents

    def _load_txt(self, file_path: str) -> str:
        """Load text file, parsing OCR tool output format"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        content_lines = []
        current_page = None

        for line in lines:
            # Skip metadata lines (starting with #)
            if line.strip().startswith('#'):
                continue

            # Parse page separators
            if line.strip().startswith('--- Page'):
                match = re.match(r'--- Page (\d+) ---', line.strip())
                if match:
                    current_page = int(match.group(1))
                continue

            # Add content line
            content_lines.append(line)

        return ''.join(content_lines)

    def _load_pdf(self, file_path: str) -> str:
        """Load PDF file"""
        try:
            reader = PdfReader(file_path)
            text = []
            for page in reader.pages:
                text.append(page.extract_text())
            return '\n\n'.join(text)
        except Exception as e:
            raise ValueError(f"Failed to read PDF: {e}")

    def _load_docx(self, file_path: str) -> str:
        """Load DOCX file"""
        try:
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)
            return '\n\n'.join(text)
        except Exception as e:
            raise ValueError(f"Failed to read DOCX: {e}")

    def _load_epub(self, file_path: str) -> str:
        """Load EPUB file (basic implementation)"""
        # For now, return a simple message
        # A full implementation would use ebooklib or similar
        raise NotImplementedError("EPUB support not yet implemented")

    def _generate_metadata(self, file_path: str) -> Dict[str, Any]:
        """Generate metadata for a document"""
        file_path_obj = Path(file_path)
        filename = file_path_obj.name

        metadata = {
            "source": str(file_path_obj),
            "filename": filename,
            "file_type": file_path_obj.suffix.lower(),
        }

        # Auto-detect syllabus files
        if "syllabus" in filename.lower():
            metadata["document_type"] = "syllabus"
        else:
            metadata["document_type"] = "general"

        return metadata

    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into smaller pieces based on token count"""
        # Tokenize the entire text
        tokens = self.encoding.encode(text)

        chunks = []
        start = 0

        while start < len(tokens):
            # Get chunk tokens
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Clean up the chunk
            chunk_text = chunk_text.strip()

            if chunk_text:
                chunks.append(chunk_text)

            # Move start position with overlap
            start = end - self.chunk_overlap

        return chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
