# ai.py
# Cog for all AI/LLM chat and question-answering commands.
# Integrates with Ollama, Hugging Face, Cohere, GPT4All, etc.
# Commands: !ask, !summarize, !translate, etc.

from discord.ext import commands
from utils.ai_helpers import ask_gemini, ask_openai, ask_huggingface, ask_cohere

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ask(self, ctx, *, question):
        """Ask a question to Gemini, fallback to OpenAI, Hugging Face, Cohere."""
        # Try providers in order, fallback if one fails
        for provider in (ask_gemini, ask_openai, ask_huggingface, ask_cohere):
            try:
                response = await provider(question)
                if response and "error" not in response.lower():
                    await ctx.send(response[:2000])
                    return
            except Exception as e:
                continue
        await ctx.send("All AI providers failed. Please try again later.")

async def setup(bot):
    await bot.add_cog(AI(bot))

