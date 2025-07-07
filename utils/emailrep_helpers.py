import aiohttp
import os
from utils.disk_cache import cache_get, cache_set, make_cache_key
from utils.error_logging_helper import log_error
from config import (
    KICKBOX_API_KEY,
    MAILBOXLAYER_KEY,
    ABSTRACT_EMAIL_KEY,
    EMAILABLE_API_KEY,
    ZEROBOUNCE_API_KEY
)

CACHE_PREFIX = "emailrep"

async def check_kickbox(email: str):
    if not KICKBOX_API_KEY:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:kickbox", email)
    if cache_get(cache_key):
        return cache_get(cache_key)

    url = f"https://api.kickbox.com/v2/verify?email={email}&apikey={KICKBOX_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                result = {
                    "source": "kickbox",
                    "verdict": data.get("result"),
                    "score": 0.9 if data.get("result") == "deliverable" else 0.3,
                    "details": data
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("kickbox_email_check", e)
        return None

async def check_mailboxlayer(email: str):
    if not MAILBOXLAYER_KEY:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:mailboxlayer", email)
    if cache_get(cache_key):
        return cache_get(cache_key)

    url = f"http://apilayer.net/api/check?access_key={MAILBOXLAYER_KEY}&email={email}&smtp=1&format=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                deliverable = data.get("smtp_check")
                result = {
                    "source": "mailboxlayer",
                    "verdict": "deliverable" if deliverable else "undeliverable",
                    "score": 0.85 if deliverable else 0.4,
                    "details": data
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("mailboxlayer_email_check", e)
        return None

async def check_abstract(email: str):
    if not ABSTRACT_EMAIL_KEY:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:abstract", email)
    if cache_get(cache_key):
        return cache_get(cache_key)

    url = f"https://emailvalidation.abstractapi.com/v1/?api_key={ABSTRACT_EMAIL_KEY}&email={email}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                deliverability = data.get("deliverability")
                result = {
                    "source": "abstract",
                    "verdict": deliverability,
                    "score": 0.88 if deliverability == "DELIVERABLE" else 0.4,
                    "details": data
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("abstract_email_check", e)
        return None

async def check_emailable(email: str):
    if not EMAILABLE_API_KEY:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:emailable", email)
    if cache_get(cache_key):
        return cache_get(cache_key)

    url = f"https://api.emailable.com/v1/verify?email={email}&api_key={EMAILABLE_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                deliverable = data.get("deliverable")
                result = {
                    "source": "emailable",
                    "verdict": deliverable,
                    "score": 0.87 if deliverable == True else 0.4,
                    "details": data
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("emailable_email_check", e)
        return None

async def check_zerobounce(email: str):
    if not ZEROBOUNCE_API_KEY:
        return None

    cache_key = make_cache_key(f"{CACHE_PREFIX}:zerobounce", email)
    if cache_get(cache_key):
        return cache_get(cache_key)

    url = f"https://api.zerobounce.net/v2/validate?email={email}&apikey={ZEROBOUNCE_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                status = data.get("status")
                result = {
                    "source": "zerobounce",
                    "verdict": status,
                    "score": 0.89 if status == "valid" else 0.4,
                    "details": data
                }
                cache_set(cache_key, result)
                return result
    except Exception as e:
        log_error("zerobounce_email_check", e)
        return None

async def email_reputation_check(email: str) -> dict:
    sources = []
    confidence = 0.0

    for checker in [
        check_kickbox,
        check_mailboxlayer,
        check_abstract,
        check_emailable,
        check_zerobounce
    ]:
        result = await checker(email)
        if result:
            sources.append(result)
            confidence = max(confidence, result["score"])
            if result["score"] >= 0.85:
                break

    safe = confidence >= 0.75
    return {
        "safe": safe,
        "confidence": round(confidence, 2),
        "sources": sources
    }
