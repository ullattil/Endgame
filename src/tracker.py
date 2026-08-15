"""SQLite tracking of applications drafted/sent by the pipeline."""

import sqlite3
from datetime import datetime, timezone


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            company TEXT,
            role_title TEXT,
            application_method TEXT,
            status TEXT NOT NULL DEFAULT 'drafted',
            output_dir TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def record_application(conn: sqlite3.Connection, url: str, job_spec: dict, output_dir: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO applications (url, company, role_title, application_method, status, output_dir, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'drafted', ?, ?, ?)
        """,
        (
            url,
            job_spec.get("company"),
            job_spec.get("role_title"),
            job_spec.get("application_method"),
            output_dir,
            now,
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_status(conn: sqlite3.Connection, application_id: int, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, application_id),
    )
    conn.commit()


def list_applications(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT id, company, role_title, application_method, status, created_at FROM applications ORDER BY created_at DESC"
    ).fetchall()
