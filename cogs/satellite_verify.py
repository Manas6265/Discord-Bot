from utils.satellite_helpers import query_all_satellite_sources
import discord
from discord.ext import commands
from discord import app_commands
import re
import datetime

class SatelliteVerify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="satellite_verify")
    async def satellite_verify_prefix(self, ctx, *, query: str = ""):
        await self._satellite_verify_core(ctx, query, is_slash=False)

    @app_commands.command(name="satellite_verify", description="Verify satellite activity via coordinates.")
    @app_commands.describe(query="Coordinates in 'lat, lon' format (e.g., '28.7041, 77.1025')")
    async def satellite_verify_slash(self, interaction: discord.Interaction, query: str = ""):
        await self._satellite_verify_core(interaction, query, is_slash=True)

    async def _satellite_verify_core(self, ctx_or_inter, query, is_slash):
        coords = None
        match = re.search(r"(-?\d{1,3}\.\d+)[,\s]+(-?\d{1,3}\.\d+)", query)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                coords = (lat, lon)
            except Exception:
                coords = None

        if not coords:
            await self._send(ctx_or_inter, is_slash, content="❌ Please provide coordinates in the format: `latitude, longitude` (e.g. `28.7041, 77.1025`).")
            return

        radius_km = 50
        today = datetime.datetime.utcnow().date().isoformat()
        await self._defer(ctx_or_inter, is_slash)
        await self._send(
            ctx_or_inter, is_slash,
            content=(
                f"🛰️ Scanning satellite sources near "
                f"[{coords[0]}, {coords[1]}](https://maps.google.com/?q={coords[0]},{coords[1]}) "
                f"within `{radius_km} km`, date `{today}`..."
            )
        )

        try:
            events = await query_all_satellite_sources(coords[0], coords[1], radius_km, date=today)
            if not events:
                await self._send(ctx_or_inter, is_slash, content="No satellite data found near these coordinates.")
                return

            # Pagination: 10 events per embed
            chunks = [events[i:i+10] for i in range(0, len(events), 10)]
            for idx, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title="📡 Satellite Event Results",
                    description=f"Page {idx+1} of {len(chunks)}",
                    color=discord.Color.teal()
                )
                for e in chunk:
                    title = f"{e.get('source', 'Unknown')} - {e.get('date', e.get('acq_time', 'N/A'))} | {e.get('type', 'Unknown')}"
                    info = f"{e.get('note', '')}\n"
                    if 'confidence' in e or 'brightness' in e:
                        info += f"Confidence: {e.get('confidence', 'N/A')}, Brightness: {e.get('brightness', 'N/A')}\n"
                    if e.get("preview_url"):
                        info += f"[Preview]({e['preview_url']})"
                    embed.add_field(name=title, value=info.strip(), inline=False)
                await self._send(ctx_or_inter, is_slash, embed=embed)

        except Exception as e:
            await self._send(ctx_or_inter, is_slash, content=f"❌ Error: {e}")

    async def _send(self, ctx_or_inter, is_slash, content=None, embed=None):
        if is_slash:
            # For slash, always use followup.send for consistency
            await ctx_or_inter.followup.send(content=content, embed=embed)
        else:
            await ctx_or_inter.send(content=content, embed=embed)

    async def _defer(self, ctx_or_inter, is_slash):
        if is_slash:
            await ctx_or_inter.response.defer(thinking=True)
        else:
            async with ctx_or_inter.typing():
                pass

async def setup(bot):
    await bot.add_cog(SatelliteVerify(bot))
