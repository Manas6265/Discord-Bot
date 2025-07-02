import discord
from discord.ext import commands
from utils.web_search_helpers import duckduckgo_search
from utils.ai_helpers import summarize_openai, extract_openai
from utils.usage_monitor import track_usage

class VerifyClaim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="verify")
    async def verify_claim(self, ctx, *, claim: str):
        await ctx.trigger_typing()

        # Step 1: Run web search
        search_results = await duckduckgo_search(claim, max_results=5)
        if not search_results:
            await ctx.send("No relevant sources found to verify this claim.")
            return

        # Step 2: Combine results for summarization
        combined_snippets = "\n".join([result['body'] for result in search_results if 'body' in result])

        # Step 3: Summarize findings
        try:
            summary = await summarize_openai(claim, combined_snippets)
            facts = await extract_openai(claim,await track_usage(ctx, "verify_claim"))
        except Exception as e:
            await ctx.send(f"Error during summarization: {str(e)}")
            return

        # Step 4: Output structured verification
        embed = discord.Embed(title="🕵️ Claim Verification Report", description=f"**Claim:** {claim}", color=0x3498db)
        embed.add_field(name="🔍 Summary of Findings", value=summary or "No summary available.", inline=False)
        embed.add_field(name="📌 Extracted Facts", value=facts or "No factual info extracted.", inline=False)

        for result in search_results:
            title = result.get("title", "[No Title]")
            url = result.get("url", "")
            embed.add_field(name=title, value=url, inline=False)

        await ctx.send(embed=embed)
        combined_snippets = "\n".join(search_results)

async def setup(bot):
    await bot.add_cog(VerifyClaim(bot))

