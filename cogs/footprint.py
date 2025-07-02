import re
import aiohttp
import asyncio
from discord.ext import commands
from discord import Embed, Color
from discord.ext.commands import cooldown, BucketType
from utils.osint_helpers import (
    check_github, check_reddit, check_pastebin,
    check_google_search, check_theharvester, check_whatsmyname,
    # If you have check_emailrep, import it here
    confidence_score
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class FootprintCog(commands.Cog):
    @commands.command()
    @cooldown(2, 60, BucketType.user)
    async def footprint(self, ctx, query: str):
        is_email = EMAIL_REGEX.match(query)
        embed = Embed(title=f"OSINT Footprint: {query}", color=Color.blue())
        async with ctx.typing(), aiohttp.ClientSession() as session:
            tasks = [
                check_github(query, session),
                check_reddit(query, session),
                check_pastebin(query, session),
                check_whatsmyname(query),
            ]
            platforms = ["GitHub", "Reddit", "Pastebin", "WhatsMyName"]

            if is_email:
                tasks.append(check_google_search(query, "github", session))
                tasks.append(check_theharvester(query))
                # Uncomment if you have check_emailrep
                # tasks.append(check_emailrep(query, session))
                platforms += ["Google(GitHub)", "theHarvester"] #, "EmailRep"]

            results = await asyncio.gather(*tasks)

        for name, res in zip(platforms, results):
            if isinstance(res, dict) and res.get("found", False):
                val = "\n".join(f"• {k}: {v}" for k, v in res.items() if k != "found" and v)
                if not val:
                    val = "✅ Found"
            elif isinstance(res, dict) and "error" in res:
                val = f"⚠️ Error: {res['error']}"
            else:
                val = "❌ Not found"
            embed.add_field(name=name, value=val[:1000], inline=False)

        embed.add_field(
            name="Confidence",
            value=f"{confidence_score(dict(zip(platforms, results)))}%",
            inline=False
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FootprintCog(bot))
