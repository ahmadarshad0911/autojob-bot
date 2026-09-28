import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import DB_PATH
from src.tailor import evaluate_and_tailor_job

def main():
    username = sys.argv[1].strip() if len(sys.argv) > 1 else "ahmad_arshad"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT job_id, title, company, location, raw_description
        FROM jobs
        WHERE user_id = ? AND status = 'DISCOVERED'
    """, (username,))
    discovered_jobs = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not discovered_jobs:
        print(f"[!] No jobs in 'DISCOVERED' status for user: {username}")
        return

    print(f"[*] Found {len(discovered_jobs)} jobs to evaluate for '{username}'")
    for job in discovered_jobs:
        try:
            evaluate_and_tailor_job(username, job)
        except Exception as e:
            print(f"[!] Error processing job {job.get('job_id')}: {e}")

if __name__ == "__main__":
    main()
