import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.config import DB_PATH

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            raw_description TEXT,
            status TEXT DEFAULT 'DISCOVERED',
            match_score REAL DEFAULT 0.0,
            tailored_resume_path TEXT,
            applied_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def insert_job(user_id: str, job_id: str, title: str, company: str, location: str, raw_description: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO jobs (job_id, user_id, title, company, location, raw_description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'DISCOVERED')
        """, (job_id, user_id, title, company, location, raw_description))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_job_status(user_id: str, job_id: str, status: str, match_score: Optional[float] = None, resume_path: Optional[str] = None):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    applied_at = datetime.utcnow().isoformat() if status == "APPLIED" else None

    if match_score is not None and resume_path is not None:
        cursor.execute("""
            UPDATE jobs
            SET status = ?, match_score = ?, tailored_resume_path = ?, applied_at = COALESCE(?, applied_at)
            WHERE user_id = ? AND job_id = ?
        """, (status, match_score, resume_path, applied_at, user_id, job_id))
    elif match_score is not None:
        cursor.execute("""
            UPDATE jobs
            SET status = ?, match_score = ?, applied_at = COALESCE(?, applied_at)
            WHERE user_id = ? AND job_id = ?
        """, (status, match_score, applied_at, user_id, job_id))
    else:
        cursor.execute("""
            UPDATE jobs
            SET status = ?, applied_at = COALESCE(?, applied_at)
            WHERE user_id = ? AND job_id = ?
        """, (status, applied_at, user_id, job_id))

    conn.commit()
    conn.close()

def get_user_jobs(username: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM jobs
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (username,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
