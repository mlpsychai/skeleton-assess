"""
Configuration settings for RAG Core library
"""

import os

# Force CPU-only processing (GTX 1080 incompatible with current PyTorch CUDA)
os.environ["CUDA_VISIBLE_DEVICES"] = ""
DEVICE = "cpu"

# Default chunk size in tokens (approximate)
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

# Embedding model
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF Document",
    ".docx": "Word Document",
    ".epub": "EPUB Book",
    ".txt": "Text File",
}

# Query settings
DEFAULT_TOP_K = 10
DEFAULT_TEMPERATURE = 0.7

# Claude model
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"

# Document types
DOCUMENT_TYPES = {
    "syllabus": "Course Syllabus",
    "article": "Academic Article",
    "chapter": "Book Chapter",
    "rubric": "Assignment Rubric",
    "sample": "Sample Work",
    "lecture": "Lecture Notes",
    "general": "General Document",
}

# Output formatting settings
DEFAULT_OUTPUT_FORMAT = "docx"  # Options: "docx", "txt"
INCLUDE_AI_SCORE = True  # Include AI detection score in outputs
OUTPUT_DIRECTORY = "output"  # Default output directory name
