import logging
import asyncio
import aiohttp
import json
import os
from urllib.parse import quote

logger = logging.getLogger("osint_helpers")

WHATS_MY_NAME_JSON = os.path.join(os.path.dirname(__file__), "wmn-data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DiscordBot/1.0)"
}

# === Platform Checks ===

async def check_github(query, session):
    url = f"https://api.github.com/users/{quote(query)}"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"found": True, "url": data.get("html_url", "")}
    except Exception as e:
        logger.warning(f"GitHub check failed: {e}")
    return {"found": False}

async def check_reddit(query, session):
    url = f"https://www.reddit.com/user/{quote(query)}/about.json"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                karma = data.get("data", {}).get("total_karma", 0)
                return {"found": True, "karma": karma, "url": f"https://www.reddit.com/user/{query}"}
    except Exception as e:
        logger.warning(f"Reddit check failed: {e}")
    return {"found": False}

async def check_pastebin(query, session):
    url = f"https://pastebin.com/u/{quote(query)}"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                text = await resp.text()
                if query.lower() in text.lower():
                    return {"found": True, "url": url}
    except Exception as e:
        logger.warning(f"Pastebin check failed: {e}")
    return {"found": False}

async def check_google_search(email, platform, session):
    query = f'site:{platform}.com "{email}"'
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                text = await resp.text()
                if email.lower() in text.lower():
                    return {"found": True, "query": query}
    except Exception as e:
        logger.warning(f"Google search for {platform} failed: {e}")
    return {"found": False}

async def check_theharvester(email):
    try:
        domain = email.split('@')[-1]
        cmd = [
            "docker", "run", "--rm", "brentclark/theharvester",
            "-d", domain,
            "-b", "google",
            "-l", "50"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"theHarvester error: {stderr.decode()}")
            return {"found": False, "error": stderr.decode()}
        output = stdout.decode()
        return {"found": True, "raw": output}
    except Exception as e:
        logger.error(f"theHarvester check failed: {e}")
        return {"found": False, "error": str(e)}

async def check_whatsmyname(username):
    try:
        with open(WHATS_MY_NAME_JSON, encoding="utf-8") as f:
            db = json.load(f)
        sites = db.get("sites", {})
    except Exception as e:
        logger.error(f"Error loading WhatsMyName DB: {e}")
        return {"found": False, "error": str(e)}

    results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for site in sites.values():
            url = site.get("urlMain", "").replace("{}", username)
            if not url or "missing" in site.get("errorType", "").lower():
                continue
            tasks.append((site["name"], url))

        batch = tasks[:30]  # Limit to 30 for rate control

        async def check_site(name, url):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        return name
            except Exception:
                pass
            return None

        results_raw = await asyncio.gather(*(check_site(name, url) for name, url in batch))
        found = [r for r in results_raw if r]

    return {"found": bool(found), "platforms": found}

# === Confidence Scoring ===

def confidence_score(results: dict) -> int:
    score = 0
    for res in results.values():
        if isinstance(res, dict) and res.get("found"):
            score += 10
    return min(score, 100)
