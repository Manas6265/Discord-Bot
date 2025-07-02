import logging
import asyncio
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, BOT_PREFIX, INTENTS
from discord.ext.commands import CommandNotFound
#from database import setup_database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("discord_bot")

# Initialize bot
bot = commands.Bot(command_prefix=commands.when_mentioned_or(BOT_PREFIX), intents=INTENTS)

# List of cogs (modules) to load
INITIAL_COGS = [
    "cogs.footprint",
    #"cogs.breach_check",
    #"cogs.social_media",
    #"cogs.image_analysis",
    #"cogs.reports",
    "cogs.verify",
    "cogs.timeline" 
]
@bot.command()
async def ping(ctx):
    """Simple command to check if the bot is online and show latency."""
    latency = ctx.bot.latency * 1000  # Convert to ms
    await ctx.send(f"Pong! 🏓 Latency: {latency:.2f} ms")
    logger.info(
        f"Ping command used by {ctx.author} in guild: {getattr(ctx.guild, 'name', 'DM')} (channel: {ctx.channel})"
    )

@bot.event
async def on_ready():
    if bot.user is not None:
        logger.info(f"Bot online as {bot.user} (ID: {bot.user.id})")
    else:
        logger.info("Bot online, but bot.user is None (unexpected).")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")

async def main():
    # Load all cogs asynchronously
    for cog in INITIAL_COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")

    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set in environment/config.")
        return

    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        # Optionally, send a message to the user:
        # await ctx.send("Unknown command. Did you make a typo?")
        return  # Silently ignore
    raise error  # Let other errors propagate
LIMIT_GIF_URL = "https://imgs.search.brave.com/rhC1bl-6X778veEamF4t-IKUknZgon34f2uLUYddl-k/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9naWZk/Yi5jb20vaW1hZ2Vz/L2hpZ2gvYW5pbWUt/ZmlnaHQtc3RvbWFj/aC1wdW5jaC1xMDFm/c2J1MWJocWg3b3Ri/LmdpZg.gif"
ROYAL_PURPLE = discord.Color.from_rgb(102, 51, 153)  # Deep purple for a royal look

async def send_limit_warning(ctx, provider_name, percent_used):
    embed = discord.Embed(
        title=f"👑 {provider_name} API Limit Approaching!",
        description=(
            f"**Heads up!**\n"
            f"You've used **{percent_used}%** of your **{provider_name}** quota.\n"
            "To keep your research and automation running smoothly, consider switching providers, reducing usage, or upgrading your plan."
        ),
        color=ROYAL_PURPLE
    )
    embed.set_image(url=LIMIT_GIF_URL)
    embed.set_author(
        name="Resource Guardian",
        icon_url="https://cdn-icons-png.flaticon.com/512/1828/1828884.png"  # Crown icon
    )
    embed.set_footer(
        text="AI Security & Productivity Assistant",
        icon_url="https://cdn-icons-png.flaticon.com/512/3062/3062634.png"  # Shield icon
    )
    embed.add_field(
        name="What can you do?",
        value="• Wait until quota resets\n• Use another provider\n• Contact admin for upgrade",
        inline=False
    )
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)

from discord import app_commands

@bot.tree.command(name="ping", description="Check if the bot is online and show latency.")
async def ping_slash(interaction: discord.Interaction):
    latency = bot.latency * 1000
    await interaction.response.send_message(f"Pong! 🏓 Latency: {latency:.2f} ms")
    logger.info(
        f"Ping (slash) used by {interaction.user} in guild: {getattr(interaction.guild, 'name', 'DM')}"
    )

if __name__ == "__main__":
#    setup_database()
    asyncio.run(main())
