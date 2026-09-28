import os
import json
from pathlib import Path
from typing import Dict, Any
from pypdf import PdfReader
from groq import Groq
from dotenv import load_dotenv

from src.schemas import MasterProfile

load_dotenv()

SYSTEM_PROMPT = """You are an elite Technical Recruiter and ATS Optimization Specialist.
Extract candidate information with 100% factual accuracy. If an ongoing role has no end date, set "end_date": "Present" and "is_current": true.
Always output strictly valid JSON matching the requested schema."""

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()

def sanitize_experience_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes parsed fields to ensure Pydantic validation passes."""
    if "experience" in data and isinstance(data["experience"], list):
        for item in data["experience"]:
            if item.get("end_date") is None or str(item.get("end_date")).strip().lower() in ["none", "null", ""]:
                item["end_date"] = "Present"
                item["is_current"] = True
    return data

def parse_cv_with_llm(raw_text: str, model_name: str = None) -> Dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment or .env file!")

    client = Groq(api_key=api_key)
    chosen_model = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    print(f"[*] Dispatching Groq API completion with model: {chosen_model}")

    user_prompt = f"""
Extract all information from the following raw CV text into a single valid JSON object adhering strictly to this schema:

{{
  "detected_target_roles": ["Primary Role Title", "Secondary Role Title"],
  "suggested_experience_level": "entry_level" | "associate" | "mid_senior" | "director",
  "contact": {{
    "full_name": "string",
    "email": "string@domain.com",
    "phone": "string or null",
    "location": "string or null",
    "linkedin_url": "url or null",
    "github_url": "url or null",
    "portfolio_url": "url or null"
  }},
  "summary": "string",
  "skills": ["Skill 1", "Skill 2"],
  "experience": [
    {{
      "company": "string",
      "role": "string",
      "location": "string or null",
      "start_date": "string or null",
      "end_date": "Present",
      "is_current": true,
      "highlights": ["highlight 1"]
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "role": "string or null",
      "url": "url or null",
      "year": "string or null",
      "highlights": ["highlight 1"]
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field_of_study": "string or null",
      "graduation_year": "string or null"
    }}
  ],
  "certifications": ["cert 1"]
}}

RAW CV TEXT:
{raw_text}
"""
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        model=chosen_model,
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    content = chat_completion.choices[0].message.content.strip()
    raw_dict = json.loads(content)
    return sanitize_experience_data(raw_dict)

def ingest_user_cv(username: str, pdf_path: str, model_name: str = None) -> MasterProfile:
    user_dir = Path(f"data/users/{username}")
    user_dir.mkdir(parents=True, exist_ok=True)

    raw_text = extract_text_from_pdf(pdf_path)
    parsed_dict = parse_cv_with_llm(raw_text, model_name=model_name)

    profile = MasterProfile(**parsed_dict)

    with open(user_dir / "master_profile.json", "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))

    user_config = {
        "user_id": username,
        "job_titles": profile.detected_target_roles,
        "experience_levels": [profile.suggested_experience_level],
        "location": "Remote",
        "daily_application_limit": 15,
        "min_match_score": 65.0,
        "llm_provider": "groq",
        "model": model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    }
    with open(user_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(user_config, f, indent=2)

    return profile
