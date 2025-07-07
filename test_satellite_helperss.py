'''# pyright: reportPrivateImportUsage=false

import asyncio
import datetime
import math
import aiohttp
import json
import sys
import os

import discord

# Reconfigure stdout encoding for Windows (safe fallback)
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleOutputCP(65001)

from config import GEMINI_API_KEY, DISCORD_TOKEN, NASA_FIRMS_API_KEY

FIRMS_MAP_KEY = "NASA_FIRMS_API_KEY"  # Replace with your actual MAP_KEY

import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def reformat_output_with_gemini(raw_response: str):
    try:
        response = await model.generate_content_async(
            [
                {
                    "role": "user",
                    "parts": [
                        "You are a JSON fixer and formatter. Take any input (even if not valid JSON), and return it as readable, structured output. If it's not JSON, make it readable.",
                        f"Input:\n{raw_response}"
                    ]
                }
            ]
        )
        return response.text
    except Exception as e:
        return f"Gemini failed to reformat: {e}\n{raw_response}"

async def query_nasa_firms_fixed(lat, lon, radius_km, days_back=1):
    try:
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * math.cos(math.radians(lat)))
        west = lon - lon_offset
        south = lat - lat_offset
        east = lon + lon_offset
        north = lat + lat_offset
        area_coords = f"{west},{south},{east},{north}"
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{area_coords}/{days_back}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    lines = content.strip().split('\n')
                    if len(lines) > 1:
                        fire_data = []
                        header = lines[0].split(',')
                        for line in lines[1:]:
                            values = line.split(',')
                            if len(values) == len(header):
                                fire_point = dict(zip(header, values))
                                fire_data.append(fire_point)
                        return {
                            "source": "NASA FIRMS",
                            "status": "success",
                            "fire_count": len(fire_data),
                            "data": fire_data[:5],
                            "query_area": area_coords,
                            "note": f"Found {len(fire_data)} fire detections"
                        }
                    else:
                        return {
                            "source": "NASA FIRMS",
                            "status": "no_data",
                            "message": "No fire detections found in the specified area and time range"
                        }
                else:
                    error_content = await response.text()
                    return {
                        "source": "NASA FIRMS",
                        "error": f"Failed with status {response.status}",
                        "content": error_content[:200]
                    }
    except Exception as e:
        return {
            "source": "NASA FIRMS",
            "error": str(e)
        }

async def query_sentinel_hub_fixed(lat, lon, radius_km, date):
    try:
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * math.cos(math.radians(lat)))
        min_lon = lon - lon_offset
        max_lon = lon + lon_offset
        min_lat = lat - lat_offset
        max_lat = lat + lat_offset
        polygon_coords = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]
        payload = {
            "input": {
                "bounds": {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon_coords]
                    },
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                    }
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{date}T00:00:00Z",
                            "to": f"{date}T23:59:59Z"
                        }
                    }
                }]
            },
            "output": {
                "width": 512,
                "height": 512,
                "responses": [{
                    "identifier": "default",
                    "format": {
                        "type": "image/jpeg"
                    }
                }]
            },
            "evalscript": """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B03", "B02"],
                        output: { bands: 3 }
                    }
                }
                function evaluatePixel(sample) {
                    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
                }
            """
        }
        from utils.satellite_helpers import get_sentinel_token
        SENTINEL_TOKEN = await get_sentinel_token()
        headers = {
            "Authorization": f"Bearer {SENTINEL_TOKEN}",
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://services.sentinel-hub.com/api/v1/process",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    return {
                        "source": "Sentinel Hub",
                        "status": "success",
                        "geometry": "polygon",
                        "coordinates": polygon_coords,
                        "note": "Successfully created polygon geometry for Sentinel Hub query"
                    }
                else:
                    error_content = await response.text()
                    return {
                        "source": "Sentinel Hub",
                        "error": f"Failed with status {response.status}",
                        "details": error_content
                    }
    except Exception as e:
        return {
            "source": "Sentinel Hub",
            "error": str(e)
        }

async def query_all_satellite_sources_fixed(lat, lon, radius_km, date):
    results = []
    firms_result = await query_nasa_firms_fixed(lat, lon, radius_km)
    results.append(firms_result)
    sentinel_result = await query_sentinel_hub_fixed(lat, lon, radius_km, date)
    results.append(sentinel_result)
    stubs = [
        {
            "source": "Planet Labs",
            "date": date,
            "type": "PlanetScope",
            "preview_url": "https://api.planet.com/...",
            "note": "Stub - implement real API call."
        },
        {
            "source": "Landsat",
            "date": date,
            "type": "Landsat 8",
            "preview_url": "https://earthexplorer.usgs.gov/...",
            "note": "Stub - implement real API call."
        },
        {
            "source": "JAXA ALOS",
            "date": date,
            "type": "ALOS DSM",
            "note": "Stub: jaxa.earth API currently does not expose iterable results. Will return after API update."
        }
    ]
    results.extend(stubs)
    return results

async def get_satellite_output():
    lat, lon = 28.6139, 77.2090  # New Delhi
    date = "2024-07-01"
    output = []
    if FIRMS_MAP_KEY == NASA_FIRMS_API_KEY:
        output.append("WARNING: Please set your FIRMS_MAP_KEY!")
        output.append("   Get a free MAP_KEY at: https://firms.modaps.eosdis.nasa.gov/api/map_key/")
        output.append("   Replace 'YOUR_MAP_KEY_HERE' in the code with your actual key.\n")
    try:
        output.append("Testing fixed satellite sources...")
        results = await query_all_satellite_sources_fixed(lat, lon, 10, date)
        output.append(f"Total results: {len(results)}\n")
        for r in results:
            try:
                output.append(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
            except Exception as json_error:
                output.append(f"JSON serialization error: {json_error}")
                formatted = await reformat_output_with_gemini(str(r))
                output.append(formatted + "\n")
    except Exception as e:
        output.append("Error in query_all_satellite_sources_fixed: " + str(e))
        fixed = await reformat_output_with_gemini(str(e))
        output.append("Reformatted output:\n" + fixed)
    output.append("All satellite helper tests complete.")
    return "\n".join(output)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.strip().lower() == "!test map":
        await message.channel.send("Running satellite helper test, please wait...")
        output = await get_satellite_output()
        # Discord messages have a 2000 character limit, so split if needed
        for chunk in [output[i:i+1990] for i in range(0, len(output), 1990)]:
            await message.channel.send(f"```json\n{chunk}\n```")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN is not set in your config file.")
    client.run(DISCORD_TOKEN)
'''