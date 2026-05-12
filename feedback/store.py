import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "feedback.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_url       TEXT    NOT NULL,
            finding_id   TEXT    NOT NULL,
            correct      BOOLEAN NOT NULL,
            comment      TEXT,
            created_at   TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_feedback(data: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO feedback (pr_url, finding_id, correct, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                data["pr_url"],
                data["finding_id"],
                data["correct"],
                data.get("comment"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_feedback_for_pr(pr_url: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT pr_url, finding_id, correct, comment, created_at FROM feedback WHERE pr_url = ?",
            (pr_url,),
        ).fetchall()
        return [
            {"pr_url": r[0], "finding_id": r[1], "correct": r[2], "comment": r[3], "created_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()
