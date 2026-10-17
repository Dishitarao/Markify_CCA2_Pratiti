"""
database.py - SQLite storage management for Markify conversions.
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "storage", "markify.db")


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with dict-like row access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the SQLite schema."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversions (
                id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                md_path TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_conversion(
    conversion_id: str,
    original_filename: str,
    pdf_path: str,
    md_path: str,
    page_count: int,
    created_at: Optional[str] = None
) -> None:
    """Inserts a new conversion record into SQLite."""
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO conversions (id, original_filename, pdf_path, md_path, page_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (conversion_id, original_filename, pdf_path, md_path, page_count, created_at))
        conn.commit()


def get_conversion_by_id(conversion_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single conversion by its UUID."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM conversions WHERE id = ?",
            (conversion_id,)
        ).fetchone()
        return dict(row) if row else None


def get_conversions_by_ids(conversion_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetches multiple conversions by IDs preserving order."""
    if not conversion_ids:
        return []
    placeholders = ",".join("?" for _ in conversion_ids)
    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM conversions WHERE id IN ({placeholders})",
            conversion_ids
        ).fetchall()
        rows_dict = {row["id"]: dict(row) for row in rows}
        return [rows_dict[cid] for cid in conversion_ids if cid in rows_dict]


def get_all_conversions() -> List[Dict[str, Any]]:
    """Fetches all conversions ordered newest first."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversions ORDER BY datetime(created_at) DESC, rowid DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_conversion(conversion_id: str) -> Optional[Dict[str, Any]]:
    """
    Deletes a conversion record and returns its data so physical files can be deleted.
    """
    record = get_conversion_by_id(conversion_id)
    if record:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM conversions WHERE id = ?", (conversion_id,))
            conn.commit()
    return record
