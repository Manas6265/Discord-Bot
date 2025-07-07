import asyncio
import logging
from datetime import datetime
from discord import Embed, Color
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
from utils.osint_helpers import OSINT_CHECKS, advanced_confidence_score
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision
from cogs.ai import analyze  # <--- Centralized AI import
from utils.request_recovery_manager import log_failed_request

logger = logging.getLogger("footprint_cog")

class FootprintCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
@commands.command()
@cooldown(2, 60, BucketType.user)
async def footprint(self, ctx, type: str, query: str):
    try:
        type = type.lower()
        if type not in OSINT_CHECKS:
            await ctx.send("Invalid type. Use: email, username, ip, domain, or url.")
            return

        embed = Embed(title=f"Footprint — {type}: {query}", color=Color.blue())

        check_funcs = OSINT_CHECKS[type]
        results = await _run_checks_parallel(check_funcs, query)

        for result in results:
            status = result.get("status")
            val = (
                "[+] Positive" if status is True else
                "[-] Negative" if status is False else
                "[!] Error: " + str(result.get("details", "No data")) if status is None else
                str(result)[:1024]
            )
            embed.add_field(name=result.get("source", "Unknown"), value=val, inline=False)

        confidence_data = advanced_confidence_score(results)
        confidence = confidence_data.get("confidence", 0.0)
        embed.add_field(name="Confidence", value=f"{confidence}/100")

        summary_query = "\n".join(
            f"{r.get('source', 'Unknown')}: {r.get('status')}, {r.get('details', '')}" for r in results
        )
        summary_options = {
            "session_id": f"{ctx.author.id}-{ctx.channel.id}",
            "user_id": str(ctx.author.id),
            "task_type": "summarize"
        }

        try:
            ai_summary = await analyze(summary_query, summary_options)
            summary_text = ai_summary["result"]["text"]
            if summary_text:
                embed.add_field(name="AI Summary", value=summary_text[:1024], inline=False)
        except Exception as e:
            log_error("footprint.footprint.summarize", e)

        await ctx.send(embed=embed)

        session_id = f"{ctx.author.id}-{ctx.channel.id}"
        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=[f"footprint:{type}"],
            provider_results=results,
            final_provider="footprint",
            final_result="success"
        )
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response="; ".join([r.get("source", "Unknown") + ": " + str(r.get("status")) for r in results]),
            provider="footprint",
            provider_version="v1",
            context={"channel_id": ctx.channel.id, "guild_id": getattr(ctx.guild, 'id', None)},
            user_info={"user_id": str(ctx.author.id)}
        )

    except Exception as e:
        await log_failed_request(ctx.author.id, ctx.message.content, str(e))
        await ctx.send("❌ Something went wrong. We'll retry and DM you when it's ready.")
    
    @footprint.error
    async def on_error(self, ctx, exc):
        if isinstance(exc, commands.CommandOnCooldown):
            await ctx.send(f"Rate-limited! Try again in {int(exc.retry_after)}s.")
        else:
            log_error("footprint.footprint.on_error", exc)
            await ctx.send("Something went wrong. Try later.")

async def _run_checks_parallel(check_funcs, query):
    async def run_check(func):
        try:
            result = await func(query)
            return {
                "source": func.__name__,
                "status": result.get("status") if isinstance(result, dict) else result,
                "details": result.get("details") if isinstance(result, dict) else "",
            }
        except Exception as e:
            log_error(f"footprint.run_check.{func.__name__}", e)
            return {
                "source": func.__name__,
                "status": None,
                "details": str(e)
            }

    return await asyncio.gather(*(run_check(f) for f in check_funcs))

# --- Bulletproof orchestration-ready analyze function ---
async def analyze(query: str, options: dict | None = None) -> dict:
    """
    Standardized analyze interface for automation/orchestration.
    options: should include {"type": "email"|"username"|"ip"|"domain"|"url"}
    """
    # Always return all keys
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

    try:
        type_ = options["type"].lower() if options and "type" in options else None
        if not type_ or type_ not in OSINT_CHECKS:
            details["error"] = "Invalid or missing type in options."
            result["error"] = details["error"]
            return {
                "result": result,
                "confidence": confidence,
                "details": details,
                "source": "footprint",
                "timestamp": datetime.utcnow().isoformat()
            }

        check_funcs = OSINT_CHECKS[type_]
        checks = await _run_checks_parallel(check_funcs, query)

        # Aggregate results as text
        text_lines = []
        for check in checks:
            if check.get("status") is True:
                text_lines.append(f"{check['source']}: Positive")
            elif check.get("status") is False:
                text_lines.append(f"{check['source']}: Negative")
            elif check.get("status") is None:
                text_lines.append(f"{check['source']}: Error - {check.get('details', 'No data')}")
            else:
                text_lines.append(f"{check['source']}: {str(check)[:256]}")
        result["text"] = "\n".join(text_lines)

        # Confidence
        confidence_data = advanced_confidence_score(checks)
        confidence = confidence_data.get("confidence", 0.0)
        details["confidence_breakdown"] = confidence_data

        # AI summary (centralized)
        try:
            summary_query = "\n".join(
                f"{c.get('source', 'Unknown')}: {c.get('status')}, {c.get('details', '')}" for c in checks
            )
            summary_options = {
                "session_id": session_id,
                "user_id": user_id,
                "task_type": "summarize"
            }
            ai_summary = await analyze(summary_query, summary_options)
            summary_text = ai_summary["result"]["text"]
            if summary_text:
                result["text"] += f"\n\nAI Summary: {summary_text[:1024]}"
        except Exception as e:
            log_error("footprint.analyze.summarize", e)

        details["checks"] = checks

        # Logging
        log_provider_decision(
            session_id=str(session_id or ""),
            query=query,
            providers_tried=[f"footprint:{type_}"],
            provider_results=checks,
            final_provider="footprint",
            final_result="success"
        )
        log_conversation(
            session_id=str(session_id or ""),
            user_query=query,
            processed_query=query,
            bot_response=result["text"],
            provider="footprint",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": str(user_id)}
        )

    except Exception as e:
        log_error("footprint.analyze", e)
        details["error"] = str(e)
        result["error"] = str(e)
        # Log error conversation
        log_conversation(
            session_id=str(session_id or ""),
            user_query=query,
            processed_query=query,
            bot_response=f"[ERROR] {e}",
            provider="footprint",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": str(user_id)}
        )

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "footprint",
        "timestamp": datetime.utcnow().isoformat()
    }

async def setup(bot):
    await bot.add_cog(FootprintCog(bot))
