# utils/usage_monitor.py
import discord
import logging
import datetime

LOG_FILE = "usage_log.txt"

async def track_usage(ctx, feature_name: str):
    """Tracks usage of a feature (e.g., /verify) with user and guild info."""
    timestamp = datetime.datetime.utcnow().isoformat()
    user = getattr(ctx.author, "name", "Unknown")
    guild = getattr(ctx.guild, "name", "DM")
    log_entry = f"[{timestamp}] Used: {feature_name} | User: {user} | Guild: {guild}\n"

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logging.error(f"Failed to log usage: {e}")

LIMIT_GIF_URL = "https://imgs.search.brave.com/rhC1bl-6X778veEamF4t-IKUknZgon34f2uLUYddl-k/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9naWZk/Yi5jb20vaW1hZ2Vz/L2hpZ2gvYW5pbWUt/ZmlnaHQtc3RvbWFj/aC1wdW5jaC1xMDFm/c2J1MWJocWg3b3Ri/LmdpZg.gif"

async def send_limit_warning(ctx, provider_name, percent_used):
    embed = discord.Embed(
        title=f"👑 {provider_name} API Limit Approaching!",
        description=(
            f"**Heads up!**\n"
            f"You've used **{percent_used}%** of your **{provider_name}** quota.\n"
            "To keep your research and automation running smoothly, consider switching providers, reducing usage, or upgrading your plan."
        ),
        color=discord.Color.from_rgb(102, 51, 153)
    )
    embed.set_image(url=LIMIT_GIF_URL)
    embed.set_author(
        name="Resource Guardian",
        icon_url="https://cdn-icons-png.flaticon.com/512/1828/1828884.png"
    )
    embed.set_footer(
        text="AI Security & Productivity Assistant",
        icon_url="https://cdn-icons-png.flaticon.com/512/3062/3062634.png"
    )
    embed.add_field(
        name="What can you do?",
        value="• Wait until quota resets\n• Use another provider\n• Contact admin for upgrade",
        inline=False
    )
    await ctx.send(embed=embed)

async def usage_monitor(ctx, provider_name, percent_used):
    try:
        if percent_used >= 80:
            await send_limit_warning(ctx, provider_name, percent_used)
    except Exception as e:
        print(f"Error sending limit warning: {e}")
