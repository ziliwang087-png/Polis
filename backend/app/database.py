"""
Database connection and utilities
"""
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from contextlib import contextmanager
from app.config import settings

# 注册 UUID adapter，避免 psycopg2 报 "can't adapt type 'UUID'"
register_uuid()

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_db_cursor(conn):
    """Get cursor from connection"""
    return conn.cursor()

def get_db():
    """Dependency for FastAPI routes - yields database connection"""
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
