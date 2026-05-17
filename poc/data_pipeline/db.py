"""Supabase Postgres connection helper (psycopg3 + pgvector adapter)."""
import os

import psycopg
from pgvector.psycopg import register_vector


def connect() -> psycopg.Connection:
    """Open a Supabase connection with the pgvector adapter registered."""
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError(
            "SUPABASE_DB_URL not set. Project Settings → Database → "
            "Connection string → URI (Session pooler)."
        )
    conn = psycopg.connect(url)
    register_vector(conn)
    return conn
