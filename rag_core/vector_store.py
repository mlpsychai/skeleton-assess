"""
Vector store wrapper for ChromaDB with sentence-transformers embeddings
"""

import os
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

from .config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CHROMA_DIR,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_TOP_K,
    DEVICE,
)


class VectorStore:
    """Wrapper around ChromaDB with sentence-transformers embeddings"""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        persist_directory: str = DEFAULT_CHROMA_DIR,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model

        # Initialize embedding model (CPU-only for GTX 1080 compatibility)
        self.embedding_model = SentenceTransformer(embedding_model, device=DEVICE)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Add documents to the vector store

        Args:
            documents: List of dicts with 'content' and 'metadata' keys

        Returns:
            Number of documents added
        """
        if not documents:
            return 0

        # Extract content and metadata
        texts = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        # Generate embeddings
        embeddings = self._embed(texts)

        # Generate IDs
        ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(documents))]

        # Add to ChromaDB
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )

        return len(documents)

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store

        Args:
            query_text: Query string
            top_k: Number of results to return
            filter_dict: Optional metadata filter

        Returns:
            List of results with content, metadata, and distance
        """
        # Generate query embedding
        query_embedding = self._embed([query_text])[0]

        # Convert any $regex filters to $in (ChromaDB doesn't support $regex)
        if filter_dict:
            filter_dict = self._convert_regex_filters(filter_dict)

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=filter_dict,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted_results = []
        for i in range(len(results["documents"][0])):
            result = {
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            formatted_results.append(result)

        return formatted_results

    def count(self) -> int:
        """Get total number of documents in the collection"""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all documents from the collection"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def list_sources(self) -> List[str]:
        """List all unique source files in the collection"""
        # Get all documents
        all_docs = self.collection.get(include=["metadatas"])

        # Extract unique sources
        sources = set()
        for metadata in all_docs["metadatas"]:
            if "source" in metadata:
                sources.add(metadata["source"])

        return sorted(list(sources))

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        count = self.count()
        sources = self.list_sources()

        return {
            "total_chunks": count,
            "unique_sources": len(sources),
            "sources": sources,
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model_name,
        }

    def _convert_regex_filters(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert $regex filters to $in by matching against known sources.
        ChromaDB doesn't support $regex, so we find matching sources first
        and use $in with the matched list.
        """
        import re
        converted = {}
        for key, value in filter_dict.items():
            if isinstance(value, dict) and "$regex" in value:
                pattern = value["$regex"]
                # Get all known sources and find matches
                sources = self.list_sources()
                matching = [s for s in sources if re.search(pattern, s, re.IGNORECASE)]
                if matching:
                    converted[key] = {"$in": matching}
                else:
                    # No matches — keep filter but use $eq with pattern to return empty
                    converted[key] = {"$eq": pattern}
            else:
                converted[key] = value
        return converted

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts"""
        embeddings = self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings
