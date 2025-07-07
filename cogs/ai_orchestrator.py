import time
import asyncio
from utils.ai_helpers import ask_openai, ask_gemini, ask_huggingface, ask_cohere
from utils.error_logging_helper import log_error
from cogs.ai import analyze, get_available_ai_providers
from utils.request_recovery_manager import log_failed_request

AI_PROVIDERS = [
    {
        "name": "openai",
        "func": ask_openai,
        "priority": 1,
        "best_for": {"general", "qa", "summarize", "creative"},
        "quota": 1000,
        "reset_interval": 24 * 60 * 60,
    },
    {
        "name": "gemini",
        "func": ask_gemini,
        "priority": 2,
        "best_for": {"creative", "convo", "qa"},
        "quota": 500,
        "reset_interval": 24 * 60 * 60,
    },
    {
        "name": "huggingface",
        "func": ask_huggingface,
        "priority": 3,
        "best_for": {"qa", "fallback", "summarize"},
        "quota": 2000,
        "reset_interval": 24 * 60 * 60,
    },
    {
        "name": "cohere",
        "func": ask_cohere,
        "priority": 4,
        "best_for": {"embeddings", "semantic", "qa"},
        "quota": 1000,
        "reset_interval": 24 * 60 * 60,
    },
]

_usage = {
    p["name"]: {"used": 0, "reset_time": time.time() + p["reset_interval"]}
    for p in AI_PROVIDERS
}

def _reset_quota_if_needed(provider):
    now = time.time()
    usage = _usage[provider["name"]]
    if now > usage["reset_time"]:
        usage["used"] = 0
        usage["reset_time"] = now + provider["reset_interval"]


async def ai_orchestrate(
    query: str,
    task_type: str = "general",
    ensemble: bool = False,
    options: dict | None = None
) -> dict:
    """
    Routes query to the best AI provider(s) via centralized ai.analyze().
    If ensemble=True, returns merged responses from all available providers.
    Always returns a dict with keys: provider, result, details, error.
    """
    if options is None:
        options = {}
    options["task_type"] = task_type

    if ensemble:
        available_providers = get_available_ai_providers()
        results = []
        errors = []
        for provider in available_providers:
            try:
                opts = options.copy()
                opts["provider"] = provider
                ai_result = await analyze(query, opts)
                result = ai_result["result"]["text"] if "result" in ai_result else None
                if ai_result["result"].get("error"):
                    errors.append(f"{provider}: {ai_result['result']['error']}")
                    continue
                if result:
                    results.append({"provider": provider, "result": result})
            except Exception as e:
                await log_failed_request(options.get("user_id", "unknown"), f"ai ensemble {query}", str(e))
                log_error(f"ai_orchestrate.{provider}", e)
                errors.append(f"{provider}: {str(e)}")
        if results:
            merged = " ".join([r["result"] for r in results if r["result"]])
            return {
                "provider": [r["provider"] for r in results],
                "result": merged,
                "details": None,
                "error": None if merged else "; ".join(errors) or "All providers failed."
            }
        return {
            "provider": None,
            "result": None,
            "details": "; ".join(errors) if errors else "All providers failed.",
            "error": "; ".join(errors) if errors else "All providers failed."
        }

    try:
        ai_result = await analyze(query, options)
        provider = ai_result["details"].get("provider") if "details" in ai_result else None
        result = ai_result["result"]["text"] if "result" in ai_result else None
        error = ai_result["result"].get("error") if "result" in ai_result else None
        return {
            "provider": provider,
            "result": result,
            "details": ai_result.get("details"),
            "error": error
        }
    except Exception as e:
        await log_failed_request(options.get("user_id", "unknown"), f"ai {query}", str(e))
        log_error("ai_orchestrate", e)
        return {
            "provider": None,
            "result": None,
            "details": str(e),
            "error": str(e)
        }

def get_provider_status():
    status = {}
    for provider in AI_PROVIDERS:
        usage = _usage[provider["name"]]
        status[provider["name"]] = {
            "used": usage["used"],
            "quota": provider["quota"],
            "resets_in": int(usage["reset_time"] - time.time())
        }
    return status

def reset_provider_usage(provider_name=None):
    now = time.time()
    if provider_name:
        for provider in AI_PROVIDERS:
            if provider["name"] == provider_name:
                _usage[provider_name] = {"used": 0, "reset_time": now + provider["reset_interval"]}
    else:
        for provider in AI_PROVIDERS:
            _usage[provider["name"]] = {"used": 0, "reset_time": now + provider["reset_interval"]}
