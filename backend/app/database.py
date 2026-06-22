"""
Database connection and utilities
"""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, register_uuid
from contextlib import contextmanager
from app.config import settings

# 注册 UUID adapter，避免 psycopg2 报 "can't adapt type 'UUID'"
register_uuid()

# 创建全局连接池
connection_pool = pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    dsn=settings.DATABASE_URL
)

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = connection_pool.getconn()
    try:
        # 设置 cursor_factory 为 RealDictCursor
        conn.cursor_factory = RealDictCursor
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        connection_pool.putconn(conn)

def get_db_cursor(conn):
    """Get cursor from connection"""
    return conn.cursor()

def get_db():
    """Dependency for FastAPI routes - yields database connection"""
    conn = connection_pool.getconn()
    try:
        # 设置 cursor_factory 为 RealDictCursor
        conn.cursor_factory = RealDictCursor
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)
