# image_analysis.py
# Cog for image and media analysis commands.
# Integrates Yandex Vision, TinEye, OpenCV, etc.
# Uses corresponding helpers in utils/.
import aiohttp
import os
from bs4 import BeautifulSoup
from datetime import datetime
from utils.disk_cache import cache_get, cache_set, make_cache_key
from utils.error_logging_helper import log_error

CACHE_PREFIX = "image_reverse"

async def check_bing_reverse(image_url: str):
    if not image_url:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:bing", image_url)
    if cache_get(cache_key):
        return cache_get(cache_key)

    search_url = f"https://www.bing.com/images/search?q=imgurl:{image_url}&view=detailv2&iss=sbi"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                links = [a["href"] for a in soup.select("a.iusc") if a.get("href")]
                result = {
                    "source": "bing_reverse",
                    "matches": links,
                    "score": 0.75 if links else 0.3,
                    "details": {"preview_url": search_url}
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("check_bing_reverse", e)
        return None


async def check_yandex_reverse(image_url: str):
    if not image_url:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:yandex", image_url)
    if cache_get(cache_key):
        return cache_get(cache_key)

    search_url = f"https://yandex.com/images/search?rpt=imageview&url={image_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                related = soup.find_all("a", class_="Link Theme_none")
                links = [a.get("href") for a in related if a.get("href") and a.get("href").startswith("http")]
                result = {
                    "source": "yandex_reverse",
                    "matches": links,
                    "score": 0.72 if links else 0.3,
                    "details": {"preview_url": search_url}
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("check_yandex_reverse", e)
        return None


async def image_reputation_check(image_url: str):
    results = []
    confidence = 0.0

    for checker in [check_bing_reverse, check_yandex_reverse]:
        res = await checker(image_url)
        if res:
            results.append(res)
            confidence = max(confidence, res["score"])
            if res["score"] >= 0.85:
                break

    return {
        "confidence": round(confidence, 2),
        "sources": results
    }


# --- Orchestrator-compatible analyze() ---
async def analyze(query: str, options: dict | None = None) -> dict:
    if not (query.startswith("http://") or query.startswith("https://")):
        return {
            "result": {"error": ["Invalid image URL."]},
            "confidence": 0.0,
            "details": {},
            "source": "image_analysis",
            "timestamp": datetime.utcnow().isoformat()
        }

    results = await image_reputation_check(query)

    return {
        "result": {
            "links": [m for src in results["sources"] for m in src.get("matches", [])],
            "texts": [],
            "images": [],
            "error": []
        },
        "confidence": results["confidence"],
        "details": results,
        "source": "image_analysis",
        "timestamp": datetime.utcnow().isoformat()
    }
