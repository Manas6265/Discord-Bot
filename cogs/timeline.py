import discord
from discord.ext import commands
from discord import app_commands
from utils.web_search_helpers import duckduckgo_search
from utils.ai_helpers import summarize_openai
from utils.usage_monitor import track_usage
import re
import datetime

try:
    import dateparser
except ImportError:
    dateparser = None

class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Prefix command
    @commands.command(name="timeline")
    async def timeline_prefix(self, ctx, *, topic: str):
        """Build a timeline of events related to a topic or claim. (prefix version)"""
        await self._timeline_core(ctx, topic, is_slash=False)

    # Slash command
    @app_commands.command(name="timeline", description="Build a timeline of events related to a topic or claim.")
    async def timeline_slash(self, interaction: discord.Interaction, topic: str):
        await self._timeline_core(interaction, topic, is_slash=True)

    async def _timeline_core(self, ctx_or_inter, topic, is_slash):
        # Defer response for slash, typing for prefix
        if is_slash:
            await ctx_or_inter.response.defer(thinking=True)
            send = ctx_or_inter.followup.send
        else:
            async with ctx_or_inter.typing():
                pass
            send = ctx_or_inter.send

        await track_usage(ctx_or_inter, "timeline")

        results = await duckduckgo_search(topic, max_results=20)
        if not results:
            await send("No relevant events found.")
            return

        timeline_events = []
        for result in results:
            if isinstance(result, dict):
                title = result.get("title", "")
                body = result.get("body", "")
                url = result.get("url", "")
            else:
                title = ""
                body = str(result)
                url = ""

            context = f"{title}\n{body}"
            try:
                summary = await summarize_openai(topic, context)
            except Exception as e:
                summary = f"*Summary failed: {e}*"

            timestamp = self.extract_date(body or title)
            timeline_events.append({
                "date": timestamp or "Unknown",
                "summary": summary,
                "source": url
            })

        sorted_events = sorted(
            timeline_events,
            key=lambda e: e["date"] if e["date"] != "Unknown" else "9999-99-99"
        )

        embed = discord.Embed(
            title=f"🕰️ Timeline for: {topic}",
            description="Chronological breakdown of events found online.",
            color=discord.Color.blurple()
        )

        for event in sorted_events[:25]:
            label = f"🗓️ {event['date']}" if event['date'] != "Unknown" else "📌 Undated"
            value = f"{event['summary']}\n"
            if event['source']:
                value += f"[Source]({event['source']})"
            embed.add_field(name=label, value=value, inline=False)

        if len(sorted_events) > 25:
            embed.set_footer(text=f"Showing 25 of {len(sorted_events)} events.")

        await send(embed=embed)

    def extract_date(self, text):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)
        match2 = re.search(r"(\d{1,2} \w+ \d{4})", text)
        if match2:
            try:
                return datetime.datetime.strptime(match2.group(1), "%d %B %Y").date().isoformat()
            except ValueError:
                pass
        if dateparser:
            dt = dateparser.parse(text)
            if dt:
                return dt.date().isoformat()
        return "Unknown"

async def setup(bot):
    cog = Timeline(bot)
    await bot.add_cog(cog)
    # Register slash commands for this cog
    if hasattr(bot, "tree"):
        bot.tree.add_command(cog.timeline_slash)