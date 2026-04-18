"""
Ingest MCMI-IV textbook content into Neon Postgres (pgvector) for RAG interpretation.

Usage:
    python ingest_mcmi4.py <text_file>

The text file should be the OCR output from the Essentials of MCMI-IV Assessment textbook.
This script:
  1. Creates the mcmi4 schema + chunks table if they don't exist
  2. Chunks the text (~500 tokens per chunk with 100-token overlap)
  3. Generates embeddings with sentence-transformers/all-MiniLM-L6-v2
  4. Inserts into mcmi4.chunks
"""

import sys
import os
import re
from pathlib import Path

# Force CPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import psycopg2
import numpy as np
from sentence_transformers import SentenceTransformer

DATABASE_URL = os.getenv("DATABASE_URL")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500  # tokens (approx)
CHUNK_OVERLAP = 100
SCHEMA = "mcmi4"


def create_schema_and_table(conn):
    """Create the mcmi4 schema and chunks table if they don't exist."""
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")
        cur.execute(f"SET search_path TO {SCHEMA}, corpus, public;")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.chunks (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                source_type TEXT DEFAULT 'fulltext',
                embedding vector(384)
            );
        """)
        # Create index for cosine similarity search
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS chunks_embedding_idx
            ON {SCHEMA}.chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 20);
        """)
    conn.commit()
    print(f"Schema '{SCHEMA}' and chunks table ready.")


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks by approximate token count.

    Uses whitespace splitting as a rough tokenizer (~1 token per word).
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = ' '.join(words[start:end])

        # Clean up the chunk
        chunk = chunk.strip()
        if len(chunk) > 50:  # Skip very short chunks
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def clean_ocr_text(text):
    """Clean common OCR artifacts from extracted text."""
    # Remove page separators
    text = re.sub(r'---\s*Page\s+\d+\s*---', '\n\n', text)
    # Collapse excessive whitespace
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Remove standalone page numbers
    text = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', text)
    return text.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_mcmi4.py <text_file>")
        sys.exit(1)

    text_file = Path(sys.argv[1])
    if not text_file.exists():
        print(f"File not found: {text_file}")
        sys.exit(1)

    if not DATABASE_URL:
        print("DATABASE_URL not set in .env")
        sys.exit(1)

    # Read text
    print(f"Reading {text_file}...")
    text = text_file.read_text(encoding='utf-8')
    text = clean_ocr_text(text)
    print(f"  Total characters: {len(text):,}")
    print(f"  Total words: {len(text.split()):,}")

    # Chunk
    chunks = chunk_text(text)
    print(f"  Generated {len(chunks)} chunks")

    # Connect to Neon
    print(f"Connecting to Neon...")
    conn = psycopg2.connect(DATABASE_URL)

    # Create schema/table
    create_schema_and_table(conn)

    # Check for existing data
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {SCHEMA}, corpus, public;")
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.chunks;")
        existing_count = cur.fetchone()[0]

    if existing_count > 0:
        print(f"  WARNING: {existing_count} existing chunks found in {SCHEMA}.chunks")
        response = input("  Clear existing data and re-ingest? (y/N): ")
        if response.lower() != 'y':
            print("  Aborted.")
            conn.close()
            sys.exit(0)
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {SCHEMA}.chunks;")
        conn.commit()
        print(f"  Cleared {existing_count} existing chunks.")

    # Generate embeddings
    print(f"Loading embedding model ({EMBEDDING_MODEL})...")
    model = SentenceTransformer(EMBEDDING_MODEL, device='cpu')

    print(f"Generating embeddings for {len(chunks)} chunks...")
    embeddings = model.encode(chunks, show_progress_bar=True, convert_to_numpy=True)

    # Insert into Neon
    print(f"Inserting into {SCHEMA}.chunks...")
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {SCHEMA}, corpus, public;")
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            embedding_str = "[" + ",".join(str(float(x)) for x in embedding) + "]"
            cur.execute(
                f"INSERT INTO {SCHEMA}.chunks (content, chunk_index, source_type, embedding) "
                f"VALUES (%s, %s, %s, %s::vector)",
                (chunk, i, 'fulltext', embedding_str)
            )
            if (i + 1) % 50 == 0:
                print(f"  Inserted {i + 1}/{len(chunks)} chunks...")

    conn.commit()
    conn.close()

    print(f"\nDone! Inserted {len(chunks)} chunks into {SCHEMA}.chunks")
    print(f"Verify with: SELECT COUNT(*) FROM {SCHEMA}.chunks;")


if __name__ == '__main__':
    main()
