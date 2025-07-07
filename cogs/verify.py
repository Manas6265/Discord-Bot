import discord
from discord.ext import commands
from utils.web_search_helpers import duckduckgo_search
from utils.usage_monitor import track_usage
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision
from cogs.ai import analyze as ai_analyze
from datetime import datetime
from typing import Optional
class VerifyClaim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="verify")
    async def verify_claim(self, ctx, *, claim: str):
        await ctx.trigger_typing()
        session_id = f"{ctx.author.id}-{ctx.channel.id}"
        user_id = str(ctx.author.id)

        try:
            search_results = await duckduckgo_search(claim, max_results=5)
        except Exception as e:
            log_error("verify.verify_claim.duckduckgo_search", e)
            await ctx.send("Error during web search.")
            log_provider_decision(
                session_id=session_id,
                query=claim,
                providers_tried=["duckduckgo_search"],
                provider_results=[],
                final_provider="duckduckgo_search",
                final_result="error"
            )
            log_conversation(
                session_id=session_id,
                user_query=claim,
                processed_query=claim,
                bot_response="Error during web search.",
                provider="verify",
                provider_version="v1",
                context={"channel_id": ctx.channel.id, "guild_id": getattr(ctx.guild, 'id', None)},
                user_info={"user_id": user_id}
            )
            return

        if not search_results:
            await ctx.send("No relevant sources found to verify this claim.")
            log_provider_decision(
                session_id=session_id,
                query=claim,
                providers_tried=["duckduckgo_search"],
                provider_results=[],
                final_provider="duckduckgo_search",
                final_result="no_results"
            )
            log_conversation(
                session_id=session_id,
                user_query=claim,
                processed_query=claim,
                bot_response="No relevant sources found to verify this claim.",
                provider="verify",
                provider_version="v1",
                context={"channel_id": ctx.channel.id, "guild_id": getattr(ctx.guild, 'id', None)},
                user_info={"user_id": user_id}
            )
            return

        combined_snippets = "\n".join([result['body'] for result in search_results if 'body' in result])

        try:
            await track_usage(ctx, "verify_claim")
            summary_result = await ai_analyze(claim, {"task_type": "summarize"})
            facts_result = await ai_analyze(claim, {"task_type": "extract"})
            summary = summary_result["result"]["text"] if summary_result and summary_result.get("result") else ""
            facts = facts_result["result"]["text"] if facts_result and facts_result.get("result") else ""
        except Exception as e:
            log_error("verify.verify_claim.summarize_extract", e)
            await ctx.send(f"Error during summarization: {str(e)}")
            log_provider_decision(
                session_id=session_id,
                query=claim,
                providers_tried=["ai.analyze"],
                provider_results=[{"error": str(e)}],
                final_provider="ai.analyze",
                final_result="error"
            )
            log_conversation(
                session_id=session_id,
                user_query=claim,
                processed_query=claim,
                bot_response=f"Error during summarization: {str(e)}",
                provider="verify",
                provider_version="v1",
                context={"channel_id": ctx.channel.id, "guild_id": getattr(ctx.guild, 'id', None)},
                user_info={"user_id": user_id}
            )
            return

        embed = discord.Embed(title="🕵️ Claim Verification Report", description=f"**Claim:** {claim}", color=0x3498db)
        embed.add_field(name="🔍 Summary of Findings", value=summary or "No summary available.", inline=False)
        embed.add_field(name="📌 Extracted Facts", value=facts or "No factual info extracted.", inline=False)

        for result in search_results:
            title = result.get("title", "[No Title]")
            url = result.get("url", "")
            embed.add_field(name=title, value=url, inline=False)

        await ctx.send(embed=embed)

        log_provider_decision(
            session_id=session_id,
            query=claim,
            providers_tried=["duckduckgo_search", "ai.analyze"],
            provider_results=[{"summary": summary, "facts": facts}],
            final_provider="verify",
            final_result="success"
        )
        log_conversation(
            session_id=session_id,
            user_query=claim,
            processed_query=claim,
            bot_response=f"Summary: {summary}\nFacts: {facts}",
            provider="verify",
            provider_version="v1",
            context={"channel_id": ctx.channel.id, "guild_id": getattr(ctx.guild, 'id', None)},
            user_info={"user_id": user_id}
        )

async def analyze(query: str, options: Optional[dict] = None) -> dict:
    """
    Standardized analyze interface for orchestration.
    options: can include {"max_results": int}
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

    try:
        max_results = options.get("max_results", 5) if options and "max_results" in options else 5
        search_results = await duckduckgo_search(query, max_results=max_results)
        if not search_results:
            details["error"] = "No relevant sources found to verify this claim."
            result["error"] = details["error"]
            log_provider_decision(
                session_id=session_id,
                query=query,
                providers_tried=["duckduckgo_search"],
                provider_results=[],
                final_provider="duckduckgo_search",
                final_result="no_results"
            )
            log_conversation(
                session_id=session_id,
                user_query=query,
                processed_query=query,
                bot_response="No relevant sources found to verify this claim.",
                provider="verify",
                provider_version="v1",
                context=options if options else {},
                user_info={"user_id": user_id or ""}
            )
            return {
                "result": result,
                "confidence": confidence,
                "details": details,
                "source": "verify",
                "timestamp": datetime.utcnow().isoformat()
            }

        combined_snippets = "\n".join([r['body'] for r in search_results if 'body' in r])

        try:
            summary_result = await ai_analyze(query, {"task_type": "summarize"})
            facts_result = await ai_analyze(query, {"task_type": "extract"})
            summary = summary_result["result"]["text"] if summary_result and summary_result.get("result") else ""
            facts = facts_result["result"]["text"] if facts_result and facts_result.get("result") else ""
        except Exception as e:
            log_error("verify.analyze.summarize_extract", e)
            summary = f"Summary failed: {str(e)}"
            facts = "Fact extraction failed."
            details["error"] = str(e)
            result["error"] = str(e)

        result["text"] = f"Summary: {summary}\nFacts: {facts}"

        for r in search_results:
            url = r.get("url") or ""
            if url:
                result["links"].append(url)
            title = r.get("title", "[No Title]")
            result["text"] += f"\n{title}: {url}"

        confidence = min(1.0, len(search_results) / max_results)
        details["sources_count"] = len(search_results)

        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=["duckduckgo_search", "ai.analyze"],
            provider_results=[{"summary": summary, "facts": facts}],
            final_provider="verify",
            final_result="success"
        )
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=result["text"] or "",
            provider="verify",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id or ""}
        )

    except Exception as e:
        log_error("verify.analyze", e)
        details["error"] = str(e)
        result["error"] = str(e)
        log_provider_decision(
            session_id=session_id,
            query=query,
            providers_tried=["duckduckgo_search", "ai.analyze"],
            provider_results=[{"error": str(e)}],
            final_provider="verify",
            final_result="error"
        )
        log_conversation(
            session_id=session_id,
            user_query=query,
            processed_query=query,
            bot_response=f"[ERROR] {e}",
            provider="verify",
            provider_version="v1",
            context=options if options else {},
            user_info={"user_id": user_id or ""}
        )

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "verify",
        "timestamp": datetime.utcnow().isoformat()
    }

async def setup(bot):
    await bot.add_cog(VerifyClaim(bot))
