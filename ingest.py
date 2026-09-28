import sys
from pathlib import Path

# Dynamically add project root to Python module search path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import os
from src.cv_parser import ingest_user_cv
from src.database import init_db
from src.config import get_user_dir, DEFAULT_MODEL

def main():
    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  python ingest.py <username> <path_to_cv_pdf> [optional_model_name]")
        print("\nExample:")
        print("  python ingest.py candidate_one ./my_resume.pdf")
        sys.exit(1)

    username = sys.argv[1].strip()
    pdf_path = Path(sys.argv[2].strip()).resolve()
    model_name = sys.argv[3].strip() if len(sys.argv) > 3 else DEFAULT_MODEL

    if not pdf_path.exists():
        print(f"\n[ERROR] Provided CV path does not exist: {pdf_path}")
        sys.exit(1)

    init_db()

    print(f"\n[*] Processing CV for: '{username}' using model: '{model_name}'")
    profile = ingest_user_cv(username=username, pdf_path=str(pdf_path), model_name=model_name)

    user_folder = get_user_dir(username)
    print(f"\n[SUCCESS] Profile and configs dynamically generated for user: {username}")
    print(f"  -> Profile: {user_folder / 'master_profile.json'}")
    print(f"  -> Config:  {user_folder / 'config.json'}")
    print(f"  -> Target Roles Detected: {profile.detected_target_roles}")
    print(f"  -> Inferred Level: {profile.suggested_experience_level}")

if __name__ == "__main__":
    main()
