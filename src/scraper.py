import os
import json
import hashlib
import asyncio
from typing import List, Dict, Any
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from src.config import get_user_config_path
from src.database import insert_job

def generate_job_id(company: str, title: str) -> str:
    seed = f"{company.strip().lower()}-{title.strip().lower()}"
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]

def matches_location(job_loc: str, user_loc: str) -> bool:
    """Checks if job location matches user's preferred location setting."""
    if not user_loc or user_loc.lower() in ["remote", "worldwide", "any"]:
        return True

    j_clean = job_loc.lower()
    u_clean = user_loc.lower()
    return u_clean in j_clean or "remote" in j_clean

async def scrape_remoteok_jobs(target_title: str, preferred_location: str = "Remote") -> List[Dict[str, Any]]:
    jobs = []
    query = quote_plus(target_title)
    url = f"https://remoteok.com/remote-{query}-jobs"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            rows = soup.find_all("tr", class_="job")

            for row in rows[:15]:
                title_elem = row.find("h2", itemprop="title")
                company_elem = row.find("h3", itemprop="name")
                location_elem = row.find("div", class_="location")
                link_elem = row.find("a", class_="preventLink")

                title = title_elem.get_text(strip=True) if title_elem else "Software Engineer"
                company = company_elem.get_text(strip=True) if company_elem else "Remote Org"
                location = location_elem.get_text(strip=True) if location_elem else "Remote"
                apply_link = "https://remoteok.com" + link_elem["href"] if link_elem and "href" in link_elem.attrs else url

                # Filter by user's location preference
                if not matches_location(location, preferred_location):
                    continue

                raw_desc = f"Job Title: {title}\nCompany: {company}\nLocation: {location}\nApply URL: {apply_link}\nDescription: Engineering role focusing on modern software development."

                jobs.append({
                    "job_id": generate_job_id(company, title),
                    "title": title,
                    "company": company,
                    "location": location,
                    "raw_description": raw_desc
                })

        except Exception as e:
            print(f"[!] Scrape error for '{target_title}': {e}")
        finally:
            await browser.close()

    return jobs

async def run_discovery_pipeline(username: str) -> int:
    config_path = get_user_config_path(username)
    if not config_path.exists():
        raise FileNotFoundError(f"Config for user {username} does not exist. Ingest CV first.")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    target_roles = cfg.get("job_titles", ["Software Engineer"])
    preferred_loc = cfg.get("location", "Remote")
    total_saved = 0

    print(f"[*] Starting Discovery Pipeline for '{username}' across roles: {target_roles} | Location: '{preferred_loc}'")

    for role in target_roles:
        print(f"[*] Scraping opportunities for role: '{role}'...")
        discovered_jobs = await scrape_remoteok_jobs(role, preferred_location=preferred_loc)

        for job in discovered_jobs:
            saved = insert_job(
                user_id=username,
                job_id=job["job_id"],
                title=job["title"],
                company=job["company"],
                location=job["location"],
                raw_description=job["raw_description"]
            )
            if saved:
                total_saved += 1
                print(f"  [+] Saved new job: {job['title']} @ {job['company']} ({job['location']})")

    print(f"[SUCCESS] Pipeline complete. {total_saved} unique jobs inserted into SQLite.")
    return total_saved
