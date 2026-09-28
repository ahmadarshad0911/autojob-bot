import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "users"
OUTPUT_DIR = BASE_DIR / "output" / "resumes"
DB_PATH = BASE_DIR / os.getenv("DB_NAME", "jobs_tracker.db")

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
DEFAULT_HOST = os.getenv("APP_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("APP_PORT", 8000))

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_user_dir(username: str) -> Path:
    user_path = DATA_DIR / username
    user_path.mkdir(parents=True, exist_ok=True)
    return user_path

def get_user_profile_path(username: str) -> Path:
    return get_user_dir(username) / "master_profile.json"

def get_user_config_path(username: str) -> Path:
    return get_user_dir(username) / "config.json"
