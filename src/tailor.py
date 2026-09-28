import os
import re
import json
import unicodedata
from pathlib import Path
from typing import Tuple, Dict, Any
from groq import Groq
from dotenv import load_dotenv

from src.config import (
    get_user_profile_path,
    get_user_config_path,
    OUTPUT_DIR
)
from src.pdf_builder import build_pdf_resume
from src.database import update_job_status

load_dotenv()

TAILOR_PROMPT = """You are an experienced Staff Engineering Recruiter.
Your objective: Tailor the candidate's master technical background to generate a comprehensive, full-length, perfectly balanced 1-page resume.

PAGE-FILLING DEPTH MANDATE:
1. THE RESUME MUST OCCUPY THE FULL SINGLE PAGE. Never produce sparse or half-page resumes.
2. For each Work Experience entry, write exactly 4 comprehensive technical bullets (1.5 to 2 lines each). Detail engineering architecture, QA/automation workflows, API validation, and technical results.
3. Include 3 distinct Key Technical Projects from the candidate's background. For each project, write 2 to 3 substantive bullets detailing system components, database choices, test coverage, and execution.
4. Provide a strong 3-4 sentence Technical Summary highlighting technical skills and domain strengths.
5. PURE PLAIN ASCII ONLY: Never output em-dashes, en-dashes, or special unicode symbols. Use standard hyphens (-) for date ranges.

Output strictly valid JSON with this schema:
{
  "match_score": 85.0,
  "tailored_profile": {
     "contact": {
       "full_name": "string",
       "email": "string",
       "phone": "string",
       "location": "string",
       "linkedin_url": "string or null",
       "github_url": "string or null",
       "portfolio_url": "string or null"
     },
     "summary": "3-4 cohesive sentences outlining core technical strengths and practical capabilities.",
     "skills": {
       "Languages": ["Python", "JavaScript", "SQL", "C", "Java"],
       "Frameworks & Web": ["FastAPI", "React", "Next.js", "WordPress", "Shopify Liquid"],
       "Testing, QA & Automation": ["Playwright", "Selenium", "Postman", "API Testing", "Unit Testing"],
       "Tools & Platforms": ["Git", "Docker", "Linux", "PostgreSQL", "SQLite"]
     },
     "experience": [
       {
         "company": "Company Name",
         "role": "Role Title",
         "location": "Location",
         "start_date": "Start Date",
         "end_date": "Present",
         "highlights": [
           "Action verb + concrete engineering workflow + technical design + performance impact.",
           "Action verb + automated testing/QA pipeline + edge cases validated + reliability metric.",
           "Action verb + backend service/API integration + schema design + execution efficiency.",
           "Action verb + collaboration + deployment automation + code quality standards maintained."
         ]
       }
     ],
     "projects": [
       {
         "name": "Project Name",
         "role": "Tech Stack",
         "url": "Project URL from master profile",
         "highlights": [
           "Architectural workflow and core technical features implemented.",
           "Testing coverage, reliability metrics, or automated validations."
         ]
       }
     ],
     "education": [
       {
         "institution": "University / Institute",
         "degree": "Degree Program",
         "graduation_year": "Year"
       }
     ]
  }
}"""

def clean_ascii_only(text: str) -> str:
    if not isinstance(text, str):
        return text
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u00a0": " ", "\u2026": "...",
        "\u200b": "", "\ufeff": "", "•": "", "↗": "->", "→": "->"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if ord(c) < 128])
    return re.sub(r' +', ' ', text).strip()

def sanitize_json_payload(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: sanitize_json_payload(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_payload(x) for x in data]
    elif isinstance(data, str):
        return clean_ascii_only(data)
    return data

def evaluate_and_tailor_job(username: str, job: Dict[str, Any]) -> Tuple[float, str]:
    profile_path = get_user_profile_path(username)
    config_path = get_user_config_path(username)

    with open(profile_path, "r", encoding="utf-8") as f:
        master_profile = json.load(f)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    min_threshold = config.get("min_match_score", 65.0)
    target_roles = config.get("job_titles", ["Software Engineer"])
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    payload = {
        "target_roles": target_roles,
        "master_profile": master_profile,
        "job_title": job.get("title"),
        "company": job.get("company"),
        "job_description": job.get("raw_description", "")
    }

    print(f"[*] Deep 1-Page Tailoring for: '{job.get('title')}' @ '{job.get('company')}'...")

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": TAILOR_PROMPT},
            {"role": "user", "content": json.dumps(payload)}
        ],
        model=model_name,
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    data = json.loads(response.choices[0].message.content.strip())
    clean_data = sanitize_json_payload(data)

    # Re-attach master project URLs
    master_projects = {p.get("name", "").lower(): p.get("url") for p in master_profile.get("projects", []) if p.get("url")}
    if clean_data.get("tailored_profile", {}).get("projects"):
        for p in clean_data["tailored_profile"]["projects"]:
            p_name = p.get("name", "").lower()
            if not p.get("url") and p_name in master_projects:
                p["url"] = master_projects[p_name]

    match_score = float(clean_data.get("match_score", 0.0))
    pdf_path = None

    if match_score >= min_threshold and clean_data.get("tailored_profile"):
        job_id = job.get("job_id")
        user_resumes_dir = OUTPUT_DIR / username
        user_resumes_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(user_resumes_dir / f"resume_{job_id}.pdf")

        build_pdf_resume(clean_data["tailored_profile"], pdf_path)
        update_job_status(
            user_id=username,
            job_id=job_id,
            status="TAILORED",
            match_score=match_score,
            resume_path=pdf_path
        )
        print(f"  [✓] Verified 1-Page PDF Built: {pdf_path} (Score: {match_score}%)")
    else:
        update_job_status(
            user_id=username,
            job_id=job.get("job_id"),
            status="REJECTED_LOW_SCORE",
            match_score=match_score
        )
        print(f"  [-] Skipped. Score: {match_score}% < {min_threshold}%")

    return match_score, pdf_path
