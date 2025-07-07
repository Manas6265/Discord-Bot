import aiohttp
import os
from bs4 import BeautifulSoup
from datetime import datetime
from utils.disk_cache import cache_get, cache_set, make_cache_key
from utils.error_logging_helper import log_error
from PIL import Image
import pytesseract
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

CACHE_PREFIX = "image_reverse"

# --- Reverse Search Engines ---

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
                if not links:
                    links = await fallback_scrape_links_basic(html, exclude_domain="bing.com")
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
                if not links:
                    links = await fallback_scrape_links_basic(html, exclude_domain="yandex.com")
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


async def check_telegram_reverse(image_url: str):
    if not image_url:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:telegram", image_url)
    if cache_get(cache_key):
        return cache_get(cache_key)

    search_url = f"https://images.google.com/searchbyimage?image_url={image_url}&encoded_image=&image_content=&filename=&hl=en"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                html = await resp.text()
                links = await fallback_scrape_links_basic(html, exclude_domain="google.com")
                result = {
                    "source": "telegram_reverse",
                    "matches": links,
                    "score": 0.74 if links else 0.3,
                    "details": {"preview_url": search_url}
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("check_telegram_reverse", e)
        return None


async def fallback_scrape_links_basic(html: str, exclude_domain: str = "") -> list:
    lines = html.split("\n")
    links = []
    for line in lines:
        if "href=\"http" in line:
            parts = line.split("href=\"")
            for part in parts[1:]:
                url = part.split("\"")[0]
                if url.startswith("http") and exclude_domain not in url:
                    links.append(url)
    return sorted(set(links))[:5]


async def image_reputation_check(image_url: str):
    results = []
    confidence = 0.0

    for checker in [check_bing_reverse, check_yandex_reverse, check_telegram_reverse]:
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


# --- OCR + AI Caption (optional) ---

def extract_text_from_image(path: str) -> str:
    try:
        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception as e:
        log_error("ocr_extract_text", e)
        return ""

async def ai_image_caption(path: str) -> str:
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        image = Image.open(path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=20)
        caption = processor.tokenizer.decode(out[0], skip_special_tokens=True)
        return caption
    except Exception as e:
        log_error("ai_image_caption", e)
        return ""


# --- Orchestrator-compatible analyze() ---
async def analyze(query: str, options: dict | None = None) -> dict:
    image_url = query
    temp_path = None
    ocr_text = ""
    caption = ""

    if not (query.startswith("http://") or query.startswith("https://")):
        try:
            temp_path = query
            image_url = await upload_to_0x0_st(temp_path)
            ocr_text = extract_text_from_image(temp_path)
            caption = await ai_image_caption(temp_path)
        except Exception as e:
            log_error("image_analysis.upload_fail", e)
            return {
                "result": {"error": ["Failed to upload image for analysis."]},
                "confidence": 0.0,
                "details": {"upload_error": str(e)},
                "source": "image_analysis",
                "timestamp": datetime.utcnow().isoformat()
            }

    results = await image_reputation_check(image_url)

    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception:
            pass

    return {
        "result": {
            "links": [m for src in results["sources"] for m in src.get("matches", [])],
            "texts": [ocr_text, caption],
            "images": [],
            "error": []
        },
        "confidence": results["confidence"],
        "details": results,
        "source": "image_analysis",
        "timestamp": datetime.utcnow().isoformat()
    }


# === Helper: upload image to 0x0.st ===
async def upload_to_0x0_st(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError("Image file not found.")

    url = "https://0x0.st"
    try:
        with open(filepath, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename=os.path.basename(filepath))

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        return (await resp.text()).strip()
                    else:
                        raise Exception(f"Upload failed with status {resp.status}")
    except Exception as e:
        log_error("upload_to_0x0_st", e)
        raise
