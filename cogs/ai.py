# ai.py

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation
from typing import Optional, Dict, Any, List
import cohere
from config import COHERE_API_KEY

AI_AVAILABILITY_FILE = "ai_availability.json"

# --- Setup logger ---
logger = logging.getLogger("ai_provider_fallback")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s][%(asctime)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- Setup Cohere client ---
if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY is not set in config.")
cohere_client = cohere.Client(COHERE_API_KEY)

def load_ai_availability() -> Dict[str, Any]:
    """Load AI provider availability data from file, or initialize if missing."""
    if not os.path.exists(AI_AVAILABILITY_FILE):
        data = {"cohere": {"available": True, "last_limit": None, "limit_type": None, "used": 0}}
        with open(AI_AVAILABILITY_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return data
    with open(AI_AVAILABILITY_FILE, "r") as f:
        return json.load(f)

def save_ai_availability(data: Dict[str, Any]) -> None:
    """Save AI provider availability data to file."""
    with open(AI_AVAILABILITY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def mark_ai_unavailable(limit_type: str = "minute") -> None:
    """Mark Cohere as unavailable, with a limit type and timestamp."""
    data = load_ai_availability()
    data["cohere"]["available"] = False
    data["cohere"]["last_limit"] = datetime.now(timezone.utc).isoformat()
    data["cohere"]["limit_type"] = limit_type
    save_ai_availability(data)

def mark_ai_available() -> None:
    """Mark Cohere as available."""
    data = load_ai_availability()
    data["cohere"]["available"] = True
    data["cohere"]["last_limit"] = None
    data["cohere"]["limit_type"] = None
    save_ai_availability(data)

def is_ai_available() -> bool:
    """Check if Cohere is currently available, auto-resets if minute/daily limit expired."""
    data = load_ai_availability()
    info = data.get("cohere", {})
    if not info.get("available", True):
        last_limit = info.get("last_limit")
        limit_type = info.get("limit_type")
        if last_limit:
            last_dt = datetime.fromisoformat(last_limit)
            now = datetime.now(timezone.utc)
            if limit_type == "minute" and (now - last_dt) > timedelta(minutes=1):
                mark_ai_available()
                logger.info("[AI] Cohere auto-recovered after 1 minute.")
                return True
            if limit_type == "daily" and (now - last_dt) > timedelta(days=1):
                mark_ai_available()
                logger.info("[AI] Cohere auto-recovered after 1 day.")
                return True
        return False
    return True

def normalize_ai_output(raw_output: Any) -> Dict[str, Any]:
    """Standardize the AI output format."""
    output = {
        "text": "",
        "images": [],
        "audio": [],
        "video": [],
        "links": [],
        "maps": [],
        "files": [],
        "error": None
    }
    if isinstance(raw_output, str):
        if raw_output.lower().startswith("error during cohere completion:"):
            output["error"] = raw_output
        else:
            output["text"] = raw_output
    elif isinstance(raw_output, dict):
        if "text" in raw_output and isinstance(raw_output["text"], str):
            output["text"] = raw_output["text"]
        for key in ["images", "audio", "video", "links", "maps", "files"]:
            if key in raw_output and isinstance(raw_output[key], list):
                output[key] = raw_output[key]
        if "error" in raw_output and raw_output["error"]:
            output["error"] = str(raw_output["error"])
    else:
        output["error"] = "AI output was not recognized"
    return output

async def ask_cohere(prompt: str) -> str:
    """
    Calls Cohere's chat endpoint with the given prompt.
    Handles rate limits and errors gracefully.
    Always returns a string.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    def sync_call():
        try:
            response = cohere_client.chat(
                message=prompt,
                model="command-r",
                max_tokens=1024,
                temperature=0.5,
            )
            return response.text.strip() if response.text else "No answer returned."
        except Exception as e:
            logger.error(f"Cohere ask failed: {str(e)}")
            return f"Error during Cohere completion: {str(e)}"
    if not is_ai_available():
        raise Exception("Cohere AI provider is currently unavailable due to rate limiting or error.")
    return await loop.run_in_executor(None, sync_call)

async def analyze(query: str, options: Optional[dict] = None, ctx=None) -> Dict[str, Any]:
    """
    Main AI orchestration entrypoint. Returns a standardized result dict.
    """
    session_id = str(options.get("session_id") or "") if options else ""
    user_id = str(options.get("user_id") or "") if options else ""
    task_type = options.get("task_type", "general") if options else "general"

    output = {
        "text": "",
        "images": [],
        "audio": [],
        "video": [],
        "links": [],
        "maps": [],
        "files": [],
        "error": None
    }
    confidence = 0.0
    details = {}
    provider = "cohere"
    last_error = None

    if not is_ai_available():
        output["text"] = "Cohere AI provider is unavailable due to rate limiting or error."
        output["error"] = "Provider unavailable."
        confidence = 0.0
    else:
        try:
            logger.info(f"[AI] Trying provider: Cohere")
            answer = await ask_cohere(query)
            norm = normalize_ai_output(answer)
            if norm.get("text") and not norm.get("error") and "error" not in norm.get("text", "").lower():
                for key in output:
                    if key in norm and norm[key]:
                        output[key] = norm[key]
                confidence = 0.8
                details["provider"] = provider
                mark_ai_available()
                logger.info(f"[AI] Provider Cohere succeeded.")
                increment_ai_usage()
            else:
                raise Exception(norm.get("error") or "Provider returned no usable result.")
        except Exception as e:
            last_error = str(e)
            logger.error(f"[AI] Provider Cohere failed: {e}")
            output["error"] = str(e)
            details["error"] = str(e)
            output["text"] = f"Cohere AI provider failed or is rate-limited: {str(e)}"
            # Detect Cohere rate limit error and set limit_type to "minute"
            if "429" in str(e) or "rate limit" in str(e).lower():
                mark_ai_unavailable(limit_type="minute")
            else:
                mark_ai_unavailable(limit_type="hard")
            confidence = 0.0

    # Log conversation
    log_conversation(
        session_id=session_id,
        user_query=query,
        processed_query=query,
        bot_response=output["text"] or output["error"] or "",
        provider=provider,
        provider_version="v1",
        context=options if options else {},
        user_info={"user_id": user_id}
    )

    return {
        "result": output,
        "confidence": confidence,
        "details": details,
        "source": "ai",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def get_ai_status() -> Dict[str, Any]:
    """Return the current status of Cohere."""
    data = load_ai_availability()
    info = data.get("cohere", {})
    return {
        "available": info.get("available"),
        "last_limit": info.get("last_limit"),
        "limit_type": info.get("limit_type")
    }

def get_ai_usage() -> Dict[str, Any]:
    """Return the usage stats of Cohere."""
    data = load_ai_availability()
    info = data.get("cohere", {})
    return {
        "used": info.get("used", 0),
        "available": info.get("available"),
        "last_limit": info.get("last_limit"),
        "limit_type": info.get("limit_type")
    }

def reset_ai_usage() -> None:
    """Reset usage counters for Cohere."""
    data = load_ai_availability()
    data["cohere"]["used"] = 0
    save_ai_availability(data)

def increment_ai_usage() -> None:
    """Increment usage counter for Cohere."""
    data = load_ai_availability()
    data["cohere"]["used"] = data["cohere"].get("used", 0) + 1
    save_ai_availability(data)

def reset_ai_availability() -> None:
    """Reset Cohere to available."""
    data = {"cohere": {"available": True, "last_limit": None, "limit_type": None, "used": 0}}
    save_ai_availability(data)
    logger.info("AI availability data has been reset.")

def get_available_ai_providers() -> List[str]:
    """Return a list of currently available providers (only Cohere)."""
    data = load_ai_availability()
    return ["cohere"] if data.get("cohere", {}).get("available", True) else []

def get_ai_provider_info() -> Optional[Dict[str, Any]]:
    """Get info for Cohere provider."""
    data = load_ai_availability()
    info = data.get("cohere")
    if info:
        return {
            "name": "cohere",
            "available": info["available"],
            "last_limit": info["last_limit"],
            "limit_type": info["limit_type"]
        }
    else:
        log_error("ai.get_provider_info", "Cohere not found in AI availability data.")
        return None

def get_ai_provider_list() -> List[Dict[str, Any]]:
    """Get a list of all AI providers with their availability status."""
    data = load_ai_availability()
    providers = []
    for name, info in data.items():
        providers.append({
            "name": name,
            "available": info.get("available", True),
            "last_limit": info.get("last_limit"),
            "limit_type": info.get("limit_type")
        })
    return providers
def reset_ai_provider(provider: str) -> None:
    """Reset a specific AI provider's availability."""
    data = load_ai_availability()
    if provider in data:
        data[provider] = {"available": True, "last_limit": None, "limit_type": None, "used": 0}
        save_ai_availability(data)
        logger.info(f"AI provider '{provider}' has been reset.")
    else:
        log_error("ai.reset_provider", f"Provider '{provider}' not found in AI availability data.")
def reset_all_ai_providers() -> None:
    """Reset all AI providers' availability."""
    data = {"cohere": {"available": True, "last_limit": None, "limit_type": None, "used": 0}}
    save_ai_availability(data)
    logger.info("All AI providers have been reset to available state.")
def get_ai_provider_usage(provider: str) -> Optional[Dict[str, Any]]:
    """Get usage stats for a specific AI provider."""
    data = load_ai_availability()
    if provider in data:
        info = data[provider]
        return {
            "used": info.get("used", 0),
            "available": info.get("available", True),
            "last_limit": info.get("last_limit"),
            "limit_type": info.get("limit_type")
        }
    else:
        log_error("ai.get_provider_usage", f"Provider '{provider}' not found in AI availability data.")
        return None
