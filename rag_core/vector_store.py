"""
Vector store using Neon Postgres with pgvector for semantic search.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np

# Add project root to path for db import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.connection import get_connection

from .config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_TOP_K,
    DEVICE,
)


class VectorStore:
    """Semantic search against Neon Postgres pgvector embeddings."""

    def __init__(self, schema: str = "mmpi3", embedding_model: str = DEFAULT_EMBEDDING_MODEL):
        self.schema = schema
        self.embedding_model_name = embedding_model
        self.embedding_model = SentenceTransformer(embedding_model, device=DEVICE)

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for similar chunks.

        Args:
            query_text: Query string
            top_k: Number of results to return
            filter_dict: Optional metadata filter (supports 'source_type' key)

        Returns:
            List of results with content, metadata, and distance
        """
        embedding = self._embed([query_text])[0]
        embedding_str = "[" + ",".join(str(float(x)) for x in embedding) + "]"

        with get_connection(schema=self.schema) as conn:
            with conn.cursor() as cur:
                if filter_dict and "source_type" in filter_dict:
                    sql = """
                        SELECT content, chunk_index, source_type,
                               embedding <=> %s::vector AS distance
                        FROM chunks
                        WHERE source_type = %s
                        ORDER BY distance
                        LIMIT %s
                    """
                    cur.execute(sql, (embedding_str, filter_dict["source_type"], top_k))
                else:
                    sql = """
                        SELECT content, chunk_index, source_type,
                               embedding <=> %s::vector AS distance
                        FROM chunks
                        ORDER BY distance
                        LIMIT %s
                    """
                    cur.execute(sql, (embedding_str, top_k))

                rows = cur.fetchall()

        return [
            {
                "content": row[0],
                "metadata": {
                    "chunk_index": row[1],
                    "source_type": row[2],
                },
                "distance": row[3],
            }
            for row in rows
        ]

    def count(self) -> int:
        """Get total number of chunks in the store."""
        with get_connection(schema=self.schema) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chunks;")
                return cur.fetchone()[0]

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        return self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
