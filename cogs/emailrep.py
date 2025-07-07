# Cog for email reputation analysis using EmailRep.io API.
# Provides commands to check email risk and abuse status.
# Uses utils/emailrep_helpers.py.
# cogs/emailrep.py
import datetime
from utils.emailrep_helpers import email_reputation_check
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision

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
    confidence = 0.0
    session_id = str(options.get("session_id") or "") if options else ""
    user_id = str(options.get("user_id") or "") if options else ""

    try:
        rep = await email_reputation_check(query)
        verdicts = [f"{src['source']}: {src['verdict']} (score: {src['score']})" for src in rep["sources"]]
        result["text"] = "Email Reputation Analysis:\n" + "\n".join(verdicts)
        details["confidence"] = rep["confidence"]
        confidence = rep["confidence"]

        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=["emailrep"],
            provider_results=rep["sources"],
            final_provider="emailrep",
            final_result="success"
        )

        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=result["text"],
            provider="emailrep",
            provider_version="v1",
            context=options or {},
            user_info={"user_id": user_id}
        )

    except Exception as e:
        log_error("emailrep.analyze", e)
        err_msg = f"EmailRep module error: {e}"
        result["text"] = err_msg
        result["error"] = str(e)
        details["error"] = str(e)

        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=err_msg,
            provider="emailrep",
            provider_version="v1",
            context=options or {},
            user_info={"user_id": user_id}
        )

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "emailrep",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
