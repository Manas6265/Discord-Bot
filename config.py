import os
from dotenv import load_dotenv
import discord

load_dotenv("token.env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# Satellite/Remote Sensing API Keys
NASA_FIRMS_API_KEY = os.getenv("NASA_FIRMS_API_KEY")
SENTINEL_HUB_CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID")
SENTINEL_HUB_CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
PLANET_API_KEY = os.getenv("PLANET_API_KEY")
USGS_API_KEY = os.getenv("USGS_API_KEY")
JAXA_API_KEY = os.getenv("JAXA_API_KEY")
SKYWATCH_API_KEY = os.getenv("SKYWATCH_API_KEY")
GEE_API_KEY = os.getenv("GEE_API_KEY")
NOAA_GOES_API_KEY = os.getenv("NOAA_GOES_API_KEY")
AFRL_SPOT_API_KEY = os.getenv("AFRL_SPOT_API_KEY")
VIIRS_NIGHTFIRE_API_KEY = os.getenv("VIIRS_NIGHTFIRE_API_KEY")

BOT_PREFIX = "!"
INTENTS = discord.Intents.default()
INTENTS.message_content = True
