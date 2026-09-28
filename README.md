# Auto Job Bot

An in-progress Python and FastAPI application for organising job discovery, CV ingestion, job matching, tailored resumes, and cover-letter generation.

## What it can do

- Store job-search preferences per user.
- Discover and track job opportunities.
- Parse an uploaded CV into a structured profile.
- Score and tailor resumes against job descriptions.
- Generate cover letters from text or a job-description screenshot.
- Provide a local FastAPI interface and browser dashboard.

## Local setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
cp .env.example .env
```

Add your own `GROQ_API_KEY` to `.env`, then run:

```bash
uvicorn server:app --reload
```

Open `http://127.0.0.1:8000`.

## Privacy and safety

This repository deliberately excludes API keys, uploaded CVs, generated resumes, user profiles, and the SQLite job-tracker database. Configure these only on your own machine through `.env` and local runtime folders.

## Status

Work in progress. The project is being actively refined before a production deployment.
