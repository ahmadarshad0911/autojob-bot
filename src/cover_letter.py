import os
import json
import base64
from typing import Optional, Dict, Any
from groq import Groq
from dotenv import load_dotenv
from src.config import get_user_profile_path

load_dotenv()

COVER_LETTER_DIRECTOR_PROMPT = """You are an elite Senior Staff Engineer and Technical Hiring Director.
Analyze the target Job Description (or extracted screenshot requirements) against the candidate's master engineering background.
Write a targeted, high-conversion technical cover letter.

STRICT CRITERIA:
1. ZERO AI FLUFF: Ban words/phrases like "I am writing to express my enthusiasm", "testament to", "honed my skills", "spearheaded", "delighted to apply". Start immediately with the technical match.
2. KEYWORD TARGETING: Extract 4-6 primary technical and domain keywords from the JD and naturally weave them into the narrative.
3. PROVABLE ARCHITECTURAL IMPACT: Reference the candidate's actual projects, tools, frameworks, and testing methods from their master profile.
4. STRUCTURE:
   - Paragraph 1: Direct technical positioning (2 sentences).
   - Paragraph 2: Real project execution details mapping to the JD's stack.
   - Paragraph 3: Reliability, automation, API/data handling, and engineering velocity.
   - Paragraph 4: Confident, professional close requesting a technical interview.
5. PLAIN ASCII ONLY: Standard hyphens (-). Length: 250-320 words max.

Output strictly valid JSON with this schema:
{
  "targeted_keywords": ["Keyword 1", "Keyword 2", "Keyword 3"],
  "subject_line": "Role Application - Full Name",
  "extracted_role": "Identified Job Title from JD",
  "extracted_company": "Identified Company from JD or 'Hiring Team'",
  "cover_letter_text": "Full cover letter text with proper paragraph formatting."
}"""

def extract_text_from_jd_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Uses Groq Vision to read text directly from a job description screenshot."""
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    vision_model = "llama-3.2-11b-vision-preview"

    response = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract all job details, role title, required technical skills, responsibilities, and qualifications from this job posting screenshot as clean text."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()

def generate_cover_letter_from_jd(username: str, jd_text: str) -> Dict[str, Any]:
    profile_path = get_user_profile_path(username)
    if not profile_path.exists():
        raise FileNotFoundError(f"Master profile for {username} not found. Ingest CV first.")

    with open(profile_path, "r", encoding="utf-8") as f:
        master_profile = json.load(f)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    payload = {
        "candidate_profile": master_profile,
        "job_description_raw": jd_text
    }

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": COVER_LETTER_DIRECTOR_PROMPT},
            {"role": "user", "content": json.dumps(payload)}
        ],
        model=model_name,
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    data = json.loads(response.choices[0].message.content.strip())
    raw_text = data.get("cover_letter_text", "")
    data["cover_letter_text"] = raw_text.replace("—", "-").replace("–", "-").strip()
    return data
