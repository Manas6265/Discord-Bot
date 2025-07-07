import asyncio
import datetime
import re
from utils.osint_helpers import (
    OSINT_CHECKS,
    summarize_osint_footprint,
    advanced_confidence_score,
    check_abuseipdb_report,
    check_apilayer_whois,
    check_shodan_info,
    check_greynoise_info
)
from utils.web_search_helpers import duckduckgo_search
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision

def detect_query_type(query):
    if re.match(r"[^@]+@[^@]+\.[^@]+", query):
        return "email"
    if re.match(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", query):
        return "ip"
    if re.match(r"^(?!http)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", query):
        return "domain"
    if re.match(r"^https?://", query):
        return "url"
    return "username"

async def analyze(query: str, options: dict | None = None) -> dict:
    result = {
        "text": "",
        "images": [],
        "audio": [],
        "video": [],
        "links": [],
        "maps": [],
        "files": [],
        "error": None
    }
    details = {}
    osint_results = []
    errors = []
    confidence = 0.0
    session_id = str(options.get("session_id") or "") if options else ""
    user_id = str(options.get("user_id") or "") if options else ""

    try:
        qtype = detect_query_type(query)
        checks = OSINT_CHECKS.get(qtype, [])

        import aiohttp
        async with aiohttp.ClientSession() as session:
            tasks = []
            for check in checks:
                try:
                    try:
                        tasks.append(check(query, session))
                    except TypeError:
                        tasks.append(check(session, query))
                except Exception as e:
                    errors.append(str(e))

            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Inject IP/domain enrichers
            if qtype == "ip":
                for extra_func, label in [
                    (check_abuseipdb_report, "abuseipdb"),
                    (check_greynoise_info, "greynoise"),
                    (check_shodan_info, "shodan")
                ]:
                    try:
                        data = await extra_func(query)
                        if data:
                            osint_results.append({
                                "source": label,
                                "status": True,
                                "details": data["text"],
                                "url": None,
                                "timestamp": datetime.datetime.utcnow().isoformat(),
                                "verified": True,
                                "source_reliability": 0.9
                            })
                    except Exception as e:
                        errors.append(f"{label} error: {e}")

            elif qtype == "domain":
                try:
                    whois_data = await check_apilayer_whois(query)
                    if whois_data:
                        osint_results.append({
                            "source": "whois",
                            "status": True,
                            "details": whois_data["text"],
                            "url": None,
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                            "verified": True,
                            "source_reliability": 0.9
                        })
                except Exception as e:
                    errors.append(f"whois error: {e}")

        text_lines = []
        for idx, res in enumerate(raw_results):
            check_name = getattr(checks[idx], "__name__", f"check_{idx}")
            if isinstance(res, Exception):
                osint_results.append({
                    "source": check_name,
                    "status": None,
                    "details": f"Error: {res}",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "verified": False,
                    "source_reliability": 0.7
                })
                errors.append(f"{check_name}: {res}")
                text_lines.append(f"{check_name}: Error - {res}")
            elif isinstance(res, dict):
                found = res.get("found") or res.get("available", False)
                url = res.get("url") or ""
                details_str = res.get("error", "") or str(res)
                osint_results.append({
                    "source": check_name,
                    "status": found,
                    "details": details_str,
                    "url": url,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "verified": bool(found),
                    "source_reliability": 0.85 if found else 0.7
                })
                if url:
                    result["links"].append(url)
                text_lines.append(f"{check_name}: {'Positive' if found else 'Negative'} {url if url else ''}")
            elif isinstance(res, str):
                osint_results.append({
                    "source": check_name,
                    "status": None,
                    "details": res,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "verified": False,
                    "source_reliability": 0.7
                })
                text_lines.append(f"{check_name}: {res}")
            else:
                osint_results.append({
                    "source": check_name,
                    "status": None,
                    "details": str(res),
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "verified": False,
                    "source_reliability": 0.7
                })
                text_lines.append(f"{check_name}: {str(res)}")

        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=[f"osint:{qtype}"],
            provider_results=osint_results,
            final_provider="osint",
            final_result="success"
        )

        ddg_results = await duckduckgo_search(query, max_results=5)
        if ddg_results:
            text_lines.extend([f"DDG: {r}" for r in ddg_results])

        summary = await summarize_osint_footprint(osint_results)
        if summary:
            text_lines.append(f"**OSINT Summary:**\n{summary}")

        conf = advanced_confidence_score(osint_results)
        confidence = conf.get("confidence", 0.0)
        details["confidence_breakdown"] = conf

        if errors:
            details["errors"] = errors

        result["text"] = "\n".join(text_lines)

        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=summary if summary else result["text"],
            provider="osint",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id}
        )

    except Exception as e:
        log_error("osint.analyze", e)
        result["text"] = f"⚠️ Internal error in OSINT module: {e}"
        result["error"] = str(e)
        details["error"] = str(e)
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=f"[ERROR] {e}",
            provider="osint",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id}
        )

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "osint",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
