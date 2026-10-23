"""Lightweight, thread-safe SQLite database manager."""

import sqlite3
import threading
from typing import Any, Dict, List, Optional
from app.config import settings

_thread_local = threading.local()


def get_db_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with dictionary row access."""
    if not hasattr(_thread_local, "connection") or _thread_local.connection is None:
        conn = sqlite3.connect(
            settings.DB_PATH,
            check_same_thread=False,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row
        _thread_local.connection = conn
    return _thread_local.connection


def close_db_connection() -> None:
    """Close the active thread-local connection."""
    if hasattr(_thread_local, "connection") and _thread_local.connection is not None:
        try:
            _thread_local.connection.close()
        except Exception:
            pass
        _thread_local.connection = None


def init_db() -> None:
    """Initialize database tables with necessary indexes."""
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);"
        )


def check_db_health() -> bool:
    """Verify that the database responds to a basic query."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        return bool(result and result[0] == 1)
    except Exception:
        return False


def insert_payment(payment_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new payment record securely."""
    conn = get_db_connection()
    query = """
        INSERT INTO payments (
            payment_id, order_id, customer_id, amount,
            currency, payment_method, status, failure_reason,
            created_at, updated_at
        ) VALUES (
            :payment_id, :order_id, :customer_id, :amount,
            :currency, :payment_method, :status, :failure_reason,
            :created_at, :updated_at
        );
    """
    with conn:
        conn.execute(query, payment_dict)
    return payment_dict


def get_payment_by_id(payment_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single payment record by payment_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM payments WHERE payment_id = ?;",
        (payment_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def list_payments(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List payment records with optional filtering and pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions: List[str] = []
    params: List[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status.upper())
    if customer_id:
        conditions.append("customer_id = ?")
        params.append(customer_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT * FROM payments
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def count_payments(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> int:
    """Return total count of payments matching the given criteria."""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions: List[str] = []
    params: List[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status.upper())
    if customer_id:
        conditions.append("customer_id = ?")
        params.append(customer_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"SELECT COUNT(*) FROM payments {where_clause};"
    cursor.execute(query, tuple(params))
    result = cursor.fetchone()
    return int(result[0]) if result else 0
