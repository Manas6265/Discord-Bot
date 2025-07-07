import asyncio
from datetime import datetime
from discord.ext import commands
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision
from utils.satellite_helpers import (
    satellite_image_verify,
    satellite_metadata_lookup,
    satellite_reverse_search,
)
from typing import Optional

class TimelineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # (Optional) Add Discord commands here if you want, otherwise just keep the analyze function below

async def analyze(query: str, options: Optional[dict] = None) -> dict:
    """
    Standardized analyze interface for timeline queries.
    options: can include {"mode": "image"|"metadata"|"reverse"}
    """
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
    confidence = 0.0
    details = {}
    session_id = str(options.get("session_id") or "") if options else ""
    user_id = str(options.get("user_id") or "") if options else ""

    mode = (options.get("mode") if options and "mode" in options else "image") or "image"
    prompt = ""

    try:
        if mode == "image":
            prompt = f"Satellite image verification for: {query}"
            try:
                verify_result = await satellite_image_verify(query)
                img_url = verify_result.get("image_url", "")
                summary = verify_result.get("summary", "No summary.")
                if img_url:
                    result["images"].append(img_url)
                result["text"] = summary or ""
                confidence = verify_result.get("confidence", 0.0)
                details["raw"] = verify_result
            except Exception as e:
                log_error("timeline.analyze.image", e)
                result["text"] = f"Error: {e}"
                result["error"] = str(e)
        elif mode == "metadata":
            prompt = f"Satellite metadata lookup for: {query}"
            try:
                meta_result = await satellite_metadata_lookup(query)
                meta = meta_result.get("metadata", "No metadata found.")
                result["text"] = meta or ""
                confidence = meta_result.get("confidence", 0.0)
                details["raw"] = meta_result
            except Exception as e:
                log_error("timeline.analyze.metadata", e)
                result["text"] = f"Error: {e}"
                result["error"] = str(e)
        elif mode == "reverse":
            prompt = f"Satellite reverse search for: {query}"
            try:
                reverse_result = await satellite_reverse_search(query)
                links = reverse_result.get("links", [])
                summary = reverse_result.get("summary", "No summary.")
                if links:
                    result["links"].extend(links)
                result["text"] = summary or ""
                confidence = reverse_result.get("confidence", 0.0)
                details["raw"] = reverse_result
            except Exception as e:
                log_error("timeline.analyze.reverse", e)
                result["text"] = f"Error: {e}"
                result["error"] = str(e)
        else:
            result["text"] = f"Unknown mode: {mode}"
            result["error"] = f"Unknown mode: {mode}"
            details["error"] = f"Unknown mode: {mode}"

        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=[f"timeline:{mode}"],
            provider_results=[details.get("raw", {})],
            final_provider="timeline",
            final_result="success" if not result["error"] else "error"
        )
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=prompt,
            bot_response=result["text"] or "",
            provider="timeline",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id or ""}
        )

    except Exception as e:
        log_error("timeline.analyze", e)
        details["error"] = str(e)
        result["error"] = str(e)
        result["text"] = f"[ERROR] {e}"
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=prompt,
            bot_response=result["text"] or "",
            provider="timeline",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id or ""}
        )

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "timeline",
        "timestamp": datetime.utcnow().isoformat()
    }

async def setup(bot):
    await bot.add_cog(TimelineCog(bot))
