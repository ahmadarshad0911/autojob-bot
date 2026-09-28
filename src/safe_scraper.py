import os
import re
import json
import hashlib
import sqlite3
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

from src.config import get_user_config_path, DB_PATH
from src.database import insert_job

load_dotenv()

# Irrelevant non-tech categories to strictly eliminate
NEGATIVE_DOMAINS = [
    "video editor", "video editing", "medical", "scheduler", "transcription",
    "customer support", "call center", "virtual assistant", "content writer",
    "copywriter", "graphic designer", "sales", "marketing", "telecaller",
    "accountant", "billing", "receptionist", "data entry"
]

# Strict Seniority Keyword Maps
LEVEL_RULES = {
    "fresher": {
        "forbidden": ["senior", "sr.", "sr ", "lead", "principal", "staff", "director", "head of", "architect", "manager", "vp", "expert", "specialist"],
        "required_or_neutral": True
    },
    "associate": {
        "forbidden": ["senior", "sr.", "sr ", "lead", "principal", "staff", "director", "head of", "architect", "manager", "vp"],
        "required_or_neutral": True
    },
    "junior": {
        "forbidden": ["senior", "sr.", "sr ", "lead", "principal", "staff", "director", "head of", "architect", "manager", "vp"],
        "required_or_neutral": True
    },
    "intermediate": {
        "forbidden": ["intern", "internship", "trainee", "fresh", "fresher", "principal", "staff", "director", "head of", "architect", "vp"],
        "required_or_neutral": True
    },
    "expert": {
        "forbidden": ["junior", "intern", "trainee", "associate", "fresh", "fresher", "entry level", "entry-level"],
        "required_or_neutral": True
    }
}

def generate_job_id(company: str, title: str) -> str:
    seed = f"{company.strip().lower()}-{title.strip().lower()}"
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]

def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def purge_previous_unapplied_jobs(username: str):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM jobs
        WHERE user_id = ? AND status IN ('DISCOVERED', 'TAILORED', 'REJECTED_LOW_SCORE', 'READY_TO_APPLY')
    """, (username,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        print(f"[*] [Auto-Purge] Flushed {deleted} previous unapplied search records.")

def dynamically_expand_roles_with_llm(user_roles: List[str], target_level: str) -> List[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return user_roles

    client = Groq(api_key=api_key)
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    prompt = f"""Given target tech role keywords: {user_roles} and level: {target_level}
Return a JSON array of 3-4 exact industry job title synonyms recruiters use for this domain and level.
Format: {{"synonyms": ["Title 1", "Title 2"]}}"""

    try:
        res = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a strict technical recruiter taxonomist. Return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model=model_name,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content.strip())
        return list(set(user_roles + data.get("synonyms", [])))
    except Exception:
        return user_roles

# --- GATEKEEPER 1: STRICT ROLE MATCH ---
def is_strict_role_match(title: str, user_roles: List[str], expanded_roles: List[str]) -> bool:
    t_lower = title.lower()

    # Drop out-of-niche domains immediately
    for neg in NEGATIVE_DOMAINS:
        if neg in t_lower:
            return False

    # Extract all relevant tokens from query
    all_tokens = set()
    for r in user_roles + expanded_roles:
        for w in re.split(r'[\s/,-]+', r.lower()):
            if len(w) > 2:
                all_tokens.add(w)

    # Core tech anchors must match
    has_match = any(token in t_lower for token in all_tokens)
    return has_match

# --- GATEKEEPER 2: STRICT SENIORITY LEVEL MATCH ---
def is_strict_level_match(title: str, target_level: str) -> bool:
    t_lower = title.lower()
    lvl = target_level.lower().strip()
    rule = LEVEL_RULES.get(lvl, LEVEL_RULES["associate"])

    # Check forbidden words for this level
    for forbidden in rule["forbidden"]:
        if re.search(rf"\b{re.escape(forbidden)}\b", t_lower):
            return False

    # If user explicitly asked for 'expert' / 'senior', it must contain a senior anchor
    if lvl == "expert":
        expert_anchors = ["senior", "sr.", "sr ", "lead", "principal", "staff", "architect", "expert", "specialist"]
        if not any(re.search(rf"\b{re.escape(a)}\b", t_lower) for a in expert_anchors):
            return False

    return True

# --- GATEKEEPER 3: STRICT GEO-FENCING ---
def is_strict_geo_match(job_location: str, target_city: str, target_country: str) -> bool:
    loc_lower = job_location.lower()
    city_lower = target_city.lower().strip()
    country_lower = target_country.lower().strip()

    # Disallow common foreign bleed locations
    foreign = ["india", "bangalore", "delhi", "mumbai", "usa", "united states", "uk", "london", "canada", "germany", "dubai", "uae"]
    for f in foreign:
        if f in loc_lower and f not in [city_lower, country_lower]:
            return False

    return (city_lower in loc_lower) or (country_lower in loc_lower)

def fast_resolve_company_portal(company_name: str) -> Optional[str]:
    """Tries to find the official careers portal in < 2 seconds. Returns None if not found."""
    import urllib.request
    try:
        query = f'"{company_name}" official careers jobs'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            soup = BeautifulSoup(resp.read().decode('utf-8', errors='ignore'), 'html.parser')
            for a in soup.select('.result__title a')[:3]:
                href = a.get('href', '')
                if 'uddg=' in href:
                    m = re.search(r'uddg=([^&]+)', href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                if not any(agg in href.lower() for agg in ['linkedin.com', 'indeed.com', 'glassdoor.com', 'rozee.pk', 'facebook.com']):
                    return href
    except Exception:
        pass
    return None

async def scrape_live_companies_strictly(page, role: str, city: str, country: str, target_level: str, user_roles: List[str], expanded_roles: List[str]) -> List[Dict[str, Any]]:
    discovered = []
    location_query = f"{city}, {country}" if city else country

    url = f"https://www.linkedin.com/jobs/search?keywords={urllib.parse.quote_plus(role)}&location={urllib.parse.quote_plus(location_query)}&f_TPR=r604800&position=1&pageNum=0"

    print(f"[*] Crawling live postings for: '{role}' in '{location_query}'...")
    try:
        await page.goto(url, timeout=25000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        job_cards = soup.select("ul.jobs-search__results-list li, div.base-search-card")

        for card in job_cards[:20]:
            title_tag = card.select_one(".base-search-card__title, h3")
            company_tag = card.select_one(".base-search-card__subtitle, h4 a, h4")
            loc_tag = card.select_one(".job-search-card__location")
            link_tag = card.select_one("a.base-card__full-link, a")

            if not (title_tag and company_tag):
                continue

            raw_title = clean_text(title_tag.get_text())
            company = clean_text(company_tag.get_text())
            loc = clean_text(loc_tag.get_text()) if loc_tag else location_query
            ref_link = link_tag.get("href", "") if link_tag else ""

            # 1. STRICT ROLE CHECK
            if not is_strict_role_match(raw_title, user_roles, expanded_roles):
                continue

            # 2. STRICT SENIORITY CHECK
            if not is_strict_level_match(raw_title, target_level):
                continue

            # 3. STRICT GEO-FENCING CHECK
            if not is_strict_geo_match(loc, city, country):
                continue

            # Try to resolve direct link (optional: if not found, use reference link or mark None)
            portal_url = fast_resolve_company_portal(company)
            final_apply_url = portal_url if portal_url else ref_link

            discovered.append({
                "title": raw_title,
                "company": company,
                "location": loc,
                "apply_url": final_apply_url,
                "has_direct_portal": portal_url is not None
            })

    except Exception as e:
        print(f"[!] Scraper notice: {e}")

    return discovered

async def run_safe_discovery(username: str) -> int:
    config_path = get_user_config_path(username)
    if not config_path.exists():
        raise FileNotFoundError(f"Config for {username} not found.")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    raw_roles = cfg.get("job_titles", ["SQA"])
    experience_levels = cfg.get("experience_levels", ["associate"])
    country = cfg.get("country", "Pakistan")
    city = cfg.get("city", "Lahore")
    active_level = experience_levels[0] if experience_levels else "associate"

    # Step 1: Clean old unapplied searches
    purge_previous_unapplied_jobs(username)

    # Step 2: Dynamic expansion
    expanded_roles = dynamically_expand_roles_with_llm(raw_roles, active_level)
    print(f"\n=======================================================")
    print(f"[*] STRICT 3-WAY GATEKEEPER JOB DISCOVERY: {username}")
    print(f"    Target Roles: {raw_roles}")
    print(f"    Target Level: {active_level.upper()} (Enforcing Strict Level Match)")
    print(f"    Strict Geo-Fence: {city}, {country}")
    print(f"=======================================================\n")

    total_saved = 0
    seen_keys = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for role in expanded_roles[:3]:
            live_jobs = await scrape_live_companies_strictly(
                page, role, city, country, active_level, raw_roles, expanded_roles
            )

            for it in live_jobs:
                key = f"{it['company'].lower()}-{it['title'].lower()}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                job_id = generate_job_id(it["company"], it["title"])
                link_status_str = f"Official Career Portal: {it['apply_url']}" if it['has_direct_portal'] else f"Job Listing Ref: {it['apply_url']}"
                raw_desc = (
                    f"Job Title: {it['title']}\n"
                    f"Company: {it['company']}\n"
                    f"Location: {it['location']}\n"
                    f"Seniority Level: {active_level}\n"
                    f"{link_status_str}"
                )

                saved = insert_job(
                    user_id=username,
                    job_id=job_id,
                    title=it["title"],
                    company=it["company"],
                    location=it["location"],
                    raw_description=raw_desc
                )

                if saved:
                    total_saved += 1
                    portal_note = "[Direct Portal]" if it['has_direct_portal'] else "[Listing Link]"
                    print(f"  [✓] MATCH: {it['title']} @ {it['company']} ({it['location']}) {portal_note}")

        await browser.close()

    print(f"\n[DONE] Discovered and saved {total_saved} strictly filtered hiring companies.")
    return total_saved
