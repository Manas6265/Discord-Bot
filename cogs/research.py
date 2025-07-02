import discord
from discord.ext import commands
from utils.usage_monitor import usage_monitor
from utils.web_search_helpers import duckduckgo_search
from utils.ai_helpers import (
    ask_gemini, ask_openai, ask_huggingface, ask_cohere,
    summarize_gemini, summarize_openai, summarize_huggingface, summarize_cohere,
    compare_gemini, compare_openai, compare_huggingface, compare_cohere,
    extract_gemini, extract_openai, extract_huggingface, extract_cohere,
    cite_gemini, cite_openai, cite_huggingface, cite_cohere,
    recommend_gemini, recommend_openai, recommend_huggingface, recommend_cohere,
    timeline_gemini, timeline_openai, timeline_huggingface, timeline_cohere,
    trend_gemini, trend_openai, trend_huggingface, trend_cohere,
)
import logging

CACHE = {}

class Research(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def try_providers_ensemble(self, funcs, *args):
        results = []
        for func in funcs:
            try:
                response = await func(*args)
                if response and "error" not in response.lower():
                    results.append(response[:2000])
                    logging.info(f"Provider {func.__name__} used for query: {args}")
            except Exception as e:
                logging.warning(f"{func.__name__} failed: {e}")
                continue
        if not results:
            return "All AI providers failed. Please try again later."
        if len(results) == 1:
            return results[0]
        # Synthesize/merge answers using your best LLM (e.g., OpenAI or Gemini)
        merged = await ask_openai(
            "You are an expert research assistant. Given the following answers from different AI models, synthesize the best, most accurate, and complete response:\n\n" +
            "\n\n---\n\n".join(results)
        )
        return merged[:2000]

@commands.command()
async def ask(self, ctx, *, query):
    """Multi-LLM research Q&A: answers complex questions, connects dots, cross-checks facts."""
    web_results = await duckduckgo_search(query)
    web_context = "\n".join(web_results)
    prompt = f"Answer the following question using the latest information:\nQuestion: {query}\n\nWeb results:\n{web_context}\n\nAnswer:"
    providers = [ask_gemini, ask_openai, ask_huggingface, ask_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def summarize(self, ctx, *, text):
    """Summarize documents, articles, or web pages."""
    web_results = await duckduckgo_search(text)
    web_context = "\n".join(web_results)
    prompt = f"Summarize the following content using the latest information:\nContent: {text}\n\nWeb results:\n{web_context}\n\nSummary:"
    providers = [summarize_gemini, summarize_openai, summarize_huggingface, summarize_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def compare(self, ctx, *, items):
    """Compare two concepts, products, or entities across sources."""
    web_results = await duckduckgo_search(items)
    web_context = "\n".join(web_results)
    prompt = f"Compare the following using the latest information:\nItems: {items}\n\nWeb results:\n{web_context}\n\nComparison:"
    providers = [compare_gemini, compare_openai, compare_huggingface, compare_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def extract(self, ctx, *, args):
    """Extract key facts, data points, or statistics from text or web sources."""
    web_results = await duckduckgo_search(args)
    web_context = "\n".join(web_results)
    prompt = f"Extract key facts and data from the following using the latest information:\nInput: {args}\n\nWeb results:\n{web_context}\n\nFacts:"
    providers = [extract_gemini, extract_openai, extract_huggingface, extract_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def cite(self, ctx, *, query):
    """Provide sources and citations for answers or summaries."""
    web_results = await duckduckgo_search(query)
    web_context = "\n".join(web_results)
    prompt = f"Provide sources and citations for the following using the latest information:\nQuery: {query}\n\nWeb results:\n{web_context}\n\nCitations:"
    providers = [cite_gemini, cite_openai, cite_huggingface, cite_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def recommend(self, ctx, *, topic):
    """Suggest relevant papers, articles, or resources (arXiv, PubMed, etc.)."""
    web_results = await duckduckgo_search(topic)
    web_context = "\n".join(web_results)
    prompt = f"Recommend relevant resources for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nRecommendations:"
    providers = [recommend_gemini, recommend_openai, recommend_huggingface, recommend_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def timeline(self, ctx, *, topic):
    """Generate a timeline of events or developments for a topic."""
    web_results = await duckduckgo_search(topic)
    web_context = "\n".join(web_results)
    prompt = f"Generate a timeline for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nTimeline:"
    providers = [timeline_gemini, timeline_openai, timeline_huggingface, timeline_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

@commands.command()
async def trend(self, ctx, *, topic):
    """Analyze trends or patterns over time from multiple sources."""
    web_results = await duckduckgo_search(topic)
    web_context = "\n".join(web_results)
    prompt = f"Analyze trends for the following topic using the latest information:\nTopic: {topic}\n\nWeb results:\n{web_context}\n\nTrend analysis:"
    providers = [trend_gemini, trend_openai, trend_huggingface, trend_cohere]
    response = await self.try_providers_ensemble(providers, prompt)
    await ctx.send(response)

async def setup(bot):
    await bot.add_cog(Research(bot))
