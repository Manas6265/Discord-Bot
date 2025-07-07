import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.tracker import log_analytics
from utils.translations import tr
from typing import Optional
"""Help command cog for a Discord bot, supporting both prefix and slash commands.
Includes analytics logging and multilingual support."""
# List your commands here for translation (add more as needed)

COMMANDS = [
    ("!analyze <query>", "Unified AI/OSINT/Verification analysis on your query."),
    ("!footprint <type> <query>", "OSINT footprint (email, username, IP, domain, URL)."),
    ("!verify <claim>", "Fact-check or verify a claim or statement."),
    ("!timeline <entity>", "Show timeline or activity for an entity."),
    ("!ping", "Check bot latency and status."),
    ("!help", "Show this help message."),
]

def get_help_embed(bot: commands.Bot, locale: str = "en") -> discord.Embed:
    embed = discord.Embed(
        title=tr("HELP_TITLE", locale),
        description=tr("HELP_BANNER", locale),
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3062/3062634.png")
    embed.add_field(
        name=tr("SPECIAL_FEATURES_TITLE", locale),
        value="\n".join(tr("SPECIAL_FEATURES", locale)),
        inline=False
    )
    embed.add_field(
        name=tr("COMMANDS_TITLE", locale),
        value="\n".join([f"`{cmd}` — {desc}" for cmd, desc in COMMANDS]),
        inline=False
    )
    embed.set_footer(
        text=tr("FOOTER", locale),
        icon_url="https://cdn-icons-png.flaticon.com/512/1828/1828884.png"
    )
    return embed

class HelpCog(commands.Cog):
    """Cog for both prefix and slash help commands, with analytics logging."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, lang: Optional[str] = None):
        """
        Show the help message (prefix command).
        Usage: !help [lang]
        Example: !help es
        """
        
        # Use user-specified language, else default to 'en'
        locale = lang if (lang is not None and lang in tr.__globals__["TRANSLATIONS"]) else "en"
        embed = get_help_embed(self.bot, locale)
        await ctx.send(embed=embed)
        log_analytics("help_command_used", 1)

    @app_commands.command(name="help", description="Show help and features.")
    async def help_slash(self, interaction: discord.Interaction):
        """
        Show the help message (slash command), using Discord's locale.
        """
        # Discord passes the user's locale automatically
        locale = getattr(interaction, "locale", "en")
        embed = get_help_embed(self.bot, locale)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_analytics("help_command_used", 1)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))