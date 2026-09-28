import os
import json
import sqlite3
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from src.database import init_db, get_user_jobs
from src.config import get_user_config_path, DB_PATH
from src.cv_parser import ingest_user_cv
from src.safe_scraper import run_safe_discovery
from src.tailor import evaluate_and_tailor_job
from src.cover_letter import generate_cover_letter_from_jd, extract_text_from_jd_image

load_dotenv()
init_db()

app = FastAPI(title="AutoJob Platform API")

Path("static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConfigUpdateRequest(BaseModel):
    job_titles: List[str]
    experience_levels: List[str]
    workplace_type: Optional[str] = "Any"
    country: Optional[str] = "Pakistan"
    city: Optional[str] = "Lahore"
    daily_application_limit: int = 15
    min_match_score: float = 65.0

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = Path("static/index.html")
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/api/users/{username}/config")
async def get_config_endpoint(username: str, response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    config_path = get_user_config_path(username)
    if not config_path.exists():
        return {
            "user_id": username,
            "job_titles": ["SQA"],
            "experience_levels": ["associate"],
            "workplace_type": "Any",
            "country": "Pakistan",
            "city": "Lahore",
            "daily_application_limit": 15,
            "min_match_score": 65.0
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.put("/api/users/{username}/config")
async def update_config_endpoint(username: str, req: ConfigUpdateRequest):
    config_path = get_user_config_path(username)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    current_cfg = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            current_cfg = json.load(f)

    current_cfg["user_id"] = username
    current_cfg["job_titles"] = req.job_titles
    current_cfg["experience_levels"] = req.experience_levels
    current_cfg["workplace_type"] = req.workplace_type
    current_cfg["country"] = req.country
    current_cfg["city"] = req.city
    current_cfg["location"] = f"{req.city}, {req.country}"
    current_cfg["daily_application_limit"] = req.daily_application_limit
    current_cfg["min_match_score"] = req.min_match_score

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(current_cfg, f, indent=2)

    return {"status": "success", "config": current_cfg}

@app.post("/api/pipeline/discover/{username}")
async def trigger_discovery_endpoint(username: str):
    try:
        saved_count = await run_safe_discovery(username)
        return {"status": "success", "saved_jobs": saved_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/tailor/{username}")
async def trigger_tailoring_endpoint(username: str):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE user_id = ? AND status = 'DISCOVERED'", (username,))
        discovered_jobs = [dict(r) for r in cursor.fetchall()]
        conn.close()

        tailored_count = 0
        for job in discovered_jobs:
            score, pdf = evaluate_and_tailor_job(username, job)
            if pdf:
                tailored_count += 1

        return {"status": "success", "processed": len(discovered_jobs), "tailored": tailored_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# STANDALONE COVER LETTER STUDIO ENDPOINT (TEXT OR SCREENSHOT)
@app.post("/api/cover-letter/standalone")
async def standalone_cover_letter_endpoint(
    username: str = Form(...),
    jd_text: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None)
):
    final_jd = jd_text or ""

    if screenshot and screenshot.filename:
        content = await screenshot.read()
        mime = screenshot.content_type or "image/png"
        extracted = extract_text_from_jd_image(content, mime)
        final_jd = f"{final_jd}\n\n[Extracted from Screenshot]:\n{extracted}".strip()

    if not final_jd.strip():
        raise HTTPException(status_code=400, detail="Please provide either Job Description text or a screenshot.")

    try:
        result = generate_cover_letter_from_jd(username, final_jd)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/{username}")
async def get_dashboard_endpoint(username: str, response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    apps = get_user_jobs(username)
    return {"username": username, "applications": apps}

@app.get("/api/resumes/download/{job_id}")
async def download_resume_endpoint(job_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT tailored_resume_path FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(status_code=404, detail="Tailored resume PDF not found.")

    return FileResponse(path=row[0], media_type="application/pdf", filename=f"Resume_{job_id}.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
