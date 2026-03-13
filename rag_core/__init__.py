"""
RAG Core - Shared library for course document querying

A unified RAG (Retrieval-Augmented Generation) library for processing
and querying course materials using ChromaDB and Anthropic Claude.
"""

from .document_loader import DocumentLoader
from .vector_store import VectorStore
from .query_engine import QueryEngine
from .output_formatter import OutputFormatter
from .output_utils import save_rag_output, analyze_text_for_ai, get_ai_score_only
from .config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_TOP_K,
    DEFAULT_TEMPERATURE,
    DEFAULT_CLAUDE_MODEL,
    SUPPORTED_EXTENSIONS,
    DOCUMENT_TYPES,
    DEVICE,
    DEFAULT_OUTPUT_FORMAT,
    INCLUDE_AI_SCORE,
    OUTPUT_DIRECTORY,
)

__version__ = "0.1.0"
__all__ = [
    "DocumentLoader",
    "VectorStore",
    "QueryEngine",
    "OutputFormatter",
    "save_rag_output",
    "analyze_text_for_ai",
    "get_ai_score_only",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_TOP_K",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_CLAUDE_MODEL",
    "SUPPORTED_EXTENSIONS",
    "DOCUMENT_TYPES",
    "DEVICE",
    "DEFAULT_OUTPUT_FORMAT",
    "INCLUDE_AI_SCORE",
    "OUTPUT_DIRECTORY",
]
