# tineye_helpers.py
# Helper functions for TinEye reverse image search API.
# Handles search requests and result parsing.
import aiohttp
from urllib.parse import quote
from utils.error_logging_helper import log_error

BING_REVERSE_IMAGE_URL = "https://www.bing.com/images/searchbyimage?cbir=sbi&imgurl={url}"  # URL must be public

async def reverse_image_search_bing(image_url: str) -> dict:
    """
    Perform reverse image search using Bing (image URL only).
    Returns list of result page URLs or titles.
    """
    search_url = BING_REVERSE_IMAGE_URL.format(url=quote(image_url))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                html = await resp.text()

        # Basic parsing (avoid full HTML parsing for speed/memory)
        links = []
        for line in html.split("\n"):
            if "<a href=\"http" in line:
                parts = line.split("href=\"")
                for part in parts[1:]:
                    url_part = part.split("\"")[0]
                    if url_part.startswith("http") and "bing.com" not in url_part:
                        links.append(url_part)

        unique_links = sorted(set(links))[:5]

        return {
            "found": bool(unique_links),
            "source": "bing_reverse_image",
            "links": unique_links,
            "count": len(unique_links)
        }

    except Exception as e:
        log_error("bing_reverse_image", e)
        return {
            "found": False,
            "source": "bing_reverse_image",
            "error": str(e)
        }
