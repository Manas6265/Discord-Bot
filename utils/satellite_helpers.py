import aiohttp
import datetime
import math
from config import (
    NASA_FIRMS_API_KEY,
    SENTINEL_HUB_CLIENT_ID,
    SENTINEL_HUB_CLIENT_SECRET,
    PLANET_API_KEY,
    USGS_API_KEY,
    JAXA_API_KEY,
    SKYWATCH_API_KEY,
    GEE_API_KEY,
)

# --- NASA FIRMS (already integrated) ---
async def query_nasa_firms(lat, lon, radius_km=50, hours=24):
    """
    Query NASA FIRMS for fire/thermal anomalies near (lat, lon) within radius_km and hours.
    Returns a list of dicts with event details.
    """
    # Calculate time window
    now = datetime.datetime.utcnow()
    start_time = now - datetime.timedelta(hours=hours)
    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build WFS query for bounding box around point
    # (FIRMS does not support direct radius, so we use a bounding box)
    # 1 deg latitude ≈ 111 km, longitude varies by latitude
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * abs(math.cos(math.radians(lat))) or 1)
    min_lat = lat - lat_delta
    max_lat = lat + lat_delta
    min_lon = lon - lon_delta
    max_lon = lon + lon_delta

    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    url = (
        f"https://firms.modaps.eosdis.nasa.gov/mapserver/wfs?"
        f"service=WFS&version=1.1.0&request=GetFeature&typeName=fires_viirs"
        f"&bbox={bbox}&outputFormat=application/json"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            events = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                event_time = props.get("acq_date", "") + " " + props.get("acq_time", "")
                try:
                    event_dt = datetime.datetime.strptime(
                        props.get("acq_date", "") + " " + props.get("acq_time", ""), "%Y-%m-%d %H%M"
                    )
                except Exception:
                    event_dt = None
                # Filter by time window
                if event_dt and not (start_time <= event_dt <= now):
                    continue
                events.append({
                    "latitude": props.get("latitude"),
                    "longitude": props.get("longitude"),
                    "confidence": props.get("confidence"),
                    "brightness": props.get("bright_ti4"),
                    "satellite": props.get("satellite"),
                    "acq_time": event_time,
                    "type": props.get("type"),
                    "link": f"https://firms.modaps.eosdis.nasa.gov/active_fire/#lat={props.get('latitude')}&lon={props.get('longitude')}&zoom=8"
                })
            return events

# --- Sentinel Hub (ESA Copernicus) ---
async def query_sentinel_hub(lat, lon, radius_km=5, date="2024-07-01"):
    # Use SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET
    return [{
        "source": "Sentinel Hub",
        "date": date,
        "type": "Sentinel-2 True Color",
        "preview_url": "https://services.sentinel-hub.com/...",
        "note": "Stub - implement real API call.",
    }]

# --- Planet Labs ---
async def query_planet_labs(lat, lon, radius_km=5, date="2024-07-01"):
    # Use PLANET_API_KEY
    return [{
        "source": "Planet Labs",
        "date": date,
        "type": "PlanetScope",
        "preview_url": "https://api.planet.com/...",
        "note": "Stub - implement real API call.",
    }]

# --- Landsat (USGS) ---
async def query_landsat(lat, lon, radius_km=5, date="2024-07-01"):
    # Use USGS_API_KEY
    return [{
        "source": "Landsat",
        "date": date,
        "type": "Landsat 8",
        "preview_url": "https://earthexplorer.usgs.gov/...",
        "note": "Stub - implement real API call.",
    }]

# --- JAXA ALOS ---
async def query_jaxa_alos(lat, lon, radius_km=5, date="2024-07-01"):
    # Use JAXA_API_KEY
    return [{
        "source": "JAXA ALOS",
        "date": date,
        "type": "ALOS-2 SAR",
        "preview_url": "https://www.eorc.jaxa.jp/...",
        "note": "Stub - implement real API call.",
    }]

# --- SkyWatch EarthCache ---
async def query_skywatch(lat, lon, radius_km=5, date="2024-07-01"):
    # Use SKYWATCH_API_KEY
    return [{
        "source": "SkyWatch",
        "date": date,
        "type": "SkyWatch Aggregated",
        "preview_url": "https://platform.skywatch.com/...",
        "note": "Stub - implement real API call.",
    }]

# --- Google Earth Engine (GEE) ---
async def query_google_earth_engine(lat, lon, radius_km=5, date="2024-07-01"):
    # Use GEE_API_KEY
    return [{
        "source": "Google Earth Engine",
        "date": date,
        "type": "GEE Composite",
        "preview_url": "https://earthengine.google.com/...",
        "note": "Stub - implement real API call.",
    }]

# --- VIIRS Nightfire ---
async def query_viirs_nightfire(lat, lon, radius_km=5, date="2024-07-01"):
    return [{
        "source": "VIIRS Nightfire",
        "date": date,
        "type": "Nightfire",
        "preview_url": "https://viirsfire.geog.umd.edu/...",
        "note": "Stub - implement real API call.",
    }]

# --- NOAA GOES / Himawari ---
async def query_noaa_goes(lat, lon, radius_km=5, date="2024-07-01"):
    return [{
        "source": "NOAA GOES",
        "date": date,
        "type": "GOES",
        "preview_url": "https://www.goes.noaa.gov/...",
        "note": "Stub - implement real API call.",
    }]

# --- AFRL SPOT Reports ---
async def query_afrl_spot(lat, lon, radius_km=5, date="2024-07-01"):
    return [{
        "source": "AFRL SPOT",
        "date": date,
        "type": "SPOT Report",
        "preview_url": "https://spot.afrl.af.mil/...",
        "note": "No public API. Manual integration required.",
    }]

# --- Unified Multi-Source Query ---
async def query_all_satellite_sources(lat, lon, radius_km=5, date="2024-07-01"):
    results = []
    results += await query_nasa_firms(lat, lon, radius_km, 24)
    results += await query_sentinel_hub(lat, lon, radius_km, date)
    results += await query_planet_labs(lat, lon, radius_km, date)
    results += await query_landsat(lat, lon, radius_km, date)
    results += await query_jaxa_alos(lat, lon, radius_km, date)
    results += await query_skywatch(lat, lon, radius_km, date)
    results += await query_google_earth_engine(lat, lon, radius_km, date)
    results += await query_viirs_nightfire(lat, lon, radius_km, date)
    results += await query_noaa_goes(lat, lon, radius_km, date)
    results += await query_afrl_spot(lat, lon, radius_km, date)
    return results