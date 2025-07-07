import os
from dotenv import load_dotenv
import discord

load_dotenv("token.env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
NASA_API_KEY=os.getenv("NASA_API_KEY")

# GEE Service Account Info
GEE_SERVICE_ACCOUNT_EMAIL = "your-service-account@your-project.iam.gserviceaccount.com"
GEE_KEY_PATH = os.path.join(os.path.dirname(__file__), "credentials", "gee_service_account.json")


# Satellite/Remote Sensing API Keys
NASA_FIRMS_API_KEY = os.getenv("NASA_FIRMS_API_KEY")
SENTINEL_HUB_CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID")
SENTINEL_HUB_CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
PLANET_API_KEY = os.getenv("PLANET_API_KEY")
USGS_API_KEY = os.getenv("USGS_API_KEY")
JAXA_API_KEY = os.getenv("JAXA_API_KEY")
ABUSEIPDB_KEY=os.getenv("ABUSEIPDB_KEY")
SKYWATCH_API_KEY = os.getenv("SKYWATCH_API_KEY")
GEE_API_KEY = os.getenv("GEE_API_KEY")
NOAA_GOES_API_KEY = os.getenv("NOAA_GOES_API_KEY")
AFRL_SPOT_API_KEY = os.getenv("AFRL_SPOT_API_KEY")
VIIRS_NIGHTFIRE_API_KEY = os.getenv("VIIRS_NIGHTFIRE_API_KEY")
APILAYER_WHOIS_KEY = os.getenv("APILAYER_WHOIS_KEY")
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
GREYNOISE_API_KEY = os.getenv("GREYNOISE_API_KEY")
'''
DNSLYTICS_API_KEY = os.getenv("DNSLYTICS_API_KEY")
'''
EMAILABLE_API_KEY = os.getenv("EMAILABLE_API_KEY")
ZEROBOUNCE_API_KEY = os.getenv("ZEROBOUNCE_API_KEY")
KICKBOX_API_KEY= os.getenv("KICKBOX_API_KEY")
MAILBOXLAYER_KEY = os.getenv("MAILBOXLAYER_KEY")
ABSTRACT_EMAIL_KEY = os.getenv("ABSTRACT_EMAIL_KEY")

BOT_PREFIX = "!"
INTENTS = discord.Intents.default()
INTENTS.message_content = True
