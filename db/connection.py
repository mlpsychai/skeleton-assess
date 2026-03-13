"""
Database connection management for Neon Postgres.
"""
import os
from pathlib import Path
from contextlib import contextmanager
import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def get_connection(schema="mmpi3"):
    """
    Yield a psycopg2 connection with search_path set to the given schema.
    Auto-commits on success, rolls back on exception.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in .env")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO %s, corpus, public;", (schema,))
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
