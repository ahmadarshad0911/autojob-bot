import sys
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database import init_db
from src.scraper import run_discovery_pipeline

def main():
    username = sys.argv[1].strip() if len(sys.argv) > 1 else "ahmad_arshad"
    init_db()
    asyncio.run(run_discovery_pipeline(username))

if __name__ == "__main__":
    main()
