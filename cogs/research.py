import discord
from discord.ext import commands
from utils.usage_monitor import usage_monitor
from utils.web_search_helpers import duckduckgo_search
from utils.error_logging_helper import log_error
from datetime import datetime
from cogs.ai import analyze  # <-- Centralized AI entry point

CACHE = {}

class Research(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def try_ensemble(self, prompt, mode):
        """
        Calls ai.analyze in ensemble mode, merges results from all available providers.
        """
        options = {"mode": mode, "ensemble": True}
        ai_result = await analyze(prompt, options)
        if ai_result["result"].get("error"):
            return ai_result["result"]["error"]
        return ai_result["result"]["text"] or "No answer found."

    @commands.command()
    async def ask(self, ctx, *, query):
        """Multi-LLM research Q&A: answers complex questions, connects dots, cross-checks facts."""
        web_results = await duckduckgo_search(query)
        web_context = "\n".join(web_results)
        prompt = f"Answer the following question using the latest information:\nQuestion: {query}\n\nWeb results:\n{web_context}\n\nAnswer:"
        response = await self.try_ensemble(prompt, "ask")
        await ctx.send(response)

    @commands.command()
    async def summarize(self, ctx, *, text):
        """Summarize documents, articles, or web pages."""
        web_results = await duckduckgo_search(text)
        web_context = "\n".join(web_results)
        prompt = f"Summarize the following content using the latest information:\nContent: {text}\n\nWeb results:\n{web_context}\n\nSummary:"
        response = await self.try_ensemble(prompt, "summarize")
        await ctx.send(response)

    @commands.command()
    async def compare(self, ctx, *, items):
        """Compare two concepts, products, or entities across sources."""
        web_results = await duckduckgo_search(items)
        web_context = "\n".join(web_results)
        prompt = f"Compare the following using the latest information:\nItems: {items}\n\nWeb results:\n{web_context}\n\nComparison:"
        response = await self.try_ensemble(prompt, "compare")
        await ctx.send(response)

    @commands.command()
    async def extract(self, ctx, *, args):
        """Extract key facts, data points, or statistics from text or web sources."""
        web_results = await duckduckgo_search(args)
        web_context = "\n".join(web_results)
        prompt = f"Extract key facts and data from the following using the latest information:\nInput: {args}\n\nWeb results:\n{web_context}\n\nFacts:"
        response = await self.try_ensemble(prompt, "extract")
        await ctx.send(response)

    @commands.command()
    async def cite(self, ctx, *, query):
        """Provide sources and citations for answers or summaries."""
        web_results = await duckduckgo_search(query)
        web_context = "\n".join(web_results)
        prompt = f"Provide sources and citations for the following using the latest information:\nQuery: {query}\n\nWeb results:\n{web_context}\n\nCitations:"
        response = await self.try_ensemble(prompt, "cite")
        await ctx.send(response)

    @commands.command()
    async def recommend(self, ctx, *, topic):
        """Suggest relevant papers, articles, or resources (arXiv, PubMed, etc.)."""
        web_results = await duckduckgo_search(topic)
        web_context = "\n".join(web_results)
        prompt = f"Recommend relevant resources for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nRecommendations:"
        response = await self.try_ensemble(prompt, "recommend")
        await ctx.send(response)

    @commands.command()
    async def timeline(self, ctx, *, topic):
        """Generate a timeline of events or developments for a topic."""
        web_results = await duckduckgo_search(topic)
        web_context = "\n".join(web_results)
        prompt = f"Generate a timeline for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nTimeline:"
        response = await self.try_ensemble(prompt, "timeline")
        await ctx.send(response)

    @commands.command()
    async def trend(self, ctx, *, topic):
        """Analyze trends or patterns over time from multiple sources."""
        web_results = await duckduckgo_search(topic)
        web_context = "\n".join(web_results)
        prompt = f"Analyze trends for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nTrend analysis:"
        response = await self.try_ensemble(prompt, "trend")
        await ctx.send(response)

# --- Bulletproof orchestration-ready analyze function ---
async def analyze(query: str, options: dict | None = None) -> dict:
    """
    Standardized analyze interface for orchestration.
    options: should include {"mode": "ask"|"summarize"|"compare"|"extract"|"cite"|"recommend"|"timeline"|"trend"}
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

    try:
        mode = options["mode"] if options and "mode" in options else "ask"
        web_results = await duckduckgo_search(query)
        web_context = "\n".join(web_results)
        prompt = f"{mode.title()} the following using the latest information:\nInput: {query}\n\nWeb results:\n{web_context}\n\n{mode.title()}:"
        ai_options = {"task_type": mode}
        ai_result = await analyze(prompt, ai_options)
        if ai_result["result"].get("error"):
            result["error"] = ai_result["result"]["error"]
        else:
            result["text"] = ai_result["result"]["text"]
            confidence = ai_result.get("confidence", 0.0)
            details.update(ai_result.get("details", {}))
    except Exception as e:
        log_error("research.analyze", e)
        details["error"] = str(e)
        result["error"] = str(e)

    return {
        "result": result,
        "confidence": confidence,
        "details": details,
        "source": "research",
        "timestamp": datetime.utcnow().isoformat()
    }

async def setup(bot):
    await bot.add_cog(Research(bot))
