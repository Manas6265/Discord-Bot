import logging
import asyncio
import aiohttp
import json
import os
import ipaddress
import hashlib
from urllib.parse import quote
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from utils.error_logging_helper import log_error
from utils.disk_cache import cache_get, cache_set, make_cache_key
from config import ABUSEIPDB_KEY, APILAYER_WHOIS_KEY, SHODAN_API_KEY, GREYNOISE_API_KEY

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

        batch = tasks[:30]

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

async def check_abuseipdb_report(ip: str) -> dict | None:
    try:
        ipaddress.ip_address(ip)
        if not ABUSEIPDB_KEY:
            return None

        cache_key = make_cache_key("abuseipdb", ip)
        if cache_get(cache_key):
            return cache_get(cache_key)

        url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90"
        headers = {"Key": ABUSEIPDB_KEY, "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    abuse_score = data["data"].get("abuseConfidenceScore", 0)
                    country = data["data"].get("countryCode")
                    text = f"Abuse Score: {abuse_score}, Country: {country}"
                    result = {"text": text, "raw": data}
                    cache_set(cache_key, result)
                    return result
    except Exception as e:
        log_error("check_abuseipdb_report", e)
    return None

async def check_apilayer_whois(domain: str) -> dict | None:
    try:
        if not APILAYER_WHOIS_KEY:
            return None

        cache_key = make_cache_key("whois", domain)
        if cache_get(cache_key):
            return cache_get(cache_key)

        url = f"https://api.apilayer.com/whois/query?domain={domain}"
        headers = {"apikey": APILAYER_WHOIS_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    registrar = data.get("registrar_name", "N/A")
                    created = data.get("created_date", "N/A")
                    updated = data.get("updated_date", "N/A")
                    text = f"Registrar: {registrar}, Created: {created}, Updated: {updated}"
                    result = {"text": text, "raw": data}
                    cache_set(cache_key, result)
                    return result
    except Exception as e:
        log_error("check_apilayer_whois", e)
    return None

async def check_shodan_info(ip: str) -> dict | None:
    try:
        ipaddress.ip_address(ip)
        if not SHODAN_API_KEY:
            return None

        cache_key = make_cache_key("shodan", ip)
        if cache_get(cache_key):
            return cache_get(cache_key)

        url = f"https://api.shodan.io/shodan/host/{ip}?key={SHODAN_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    org = data.get("org", "N/A")
                    isp = data.get("isp", "N/A")
                    ports = data.get("ports", [])
                    text = f"Org: {org}, ISP: {isp}, Ports: {ports}"
                    result = {"text": text, "raw": data}
                    cache_set(cache_key, result)
                    return result
    except Exception as e:
        log_error("check_shodan_info", e)
    return None

async def check_greynoise_info(ip: str) -> dict | None:
    try:
        ipaddress.ip_address(ip)
        if not GREYNOISE_API_KEY:
            return None

        cache_key = make_cache_key("greynoise", ip)
        if cache_get(cache_key):
            return cache_get(cache_key)

        url = f"https://api.greynoise.io/v3/community/{ip}"
        headers = {"key": GREYNOISE_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    category = data.get("classification", "N/A")
                    name = data.get("name", "N/A")
                    text = f"Noise Class: {category}, Actor: {name}"
                    result = {"text": text, "raw": data}
                    cache_set(cache_key, result)
                    return result
    except Exception as e:
        log_error("check_greynoise_info", e)
    return None
