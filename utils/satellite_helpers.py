import aiohttp
import datetime
import math
import os
import time
import json
import numpy as np
import rasterio
import rioxarray
from skimage import filters, feature, exposure
from skimage.feature import canny, graycomatrix, graycoprops
from sentinelsat import SentinelAPI, geojson_to_wkt
from datetime import date, timedelta
import tempfile
# --The Sentinal's Token Generation code
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "sentinel_token.json")

def load_sentinel_token():
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return None

def save_sentinel_token(token, expires_in):
    expires_at = int(time.time()) + int(expires_in)
    data = {
        "access_token": token,
        "expires_at": expires_at,
        "status": "live"
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def is_token_expired(token_data):
    if not token_data:
        return True
    expires_at = token_data.get("expires_at", 0)
    # Consider expired if less than 2 minutes left
    if expires_at - time.time() < 120:
        return True
    return False

async def get_sentinel_token():
    token_data = load_sentinel_token()
    if token_data and not is_token_expired(token_data):
        return token_data["access_token"]
    url = "https://services.sentinel-hub.com/oauth/token"
    payload = {
        "client_id": os.getenv("SENTINEL_HUB_CLIENT_ID"),
        "client_secret": os.getenv("SENTINEL_HUB_CLIENT_SECRET"),
        "grant_type": "client_credentials"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            token = data.get("access_token")
            if not token:
                raise Exception(f"Token request failed: {data}")
            expires_in = data.get("expires_in", 3599)
            save_sentinel_token(token, expires_in)
            return token

# --- Helper: JSON Caching ---
def get_cache_paths(lat, lon, days_back):
    base = f"cache_{lat}_{lon}_{days_back}"
    return f"{base}.img", f"{base}.json"

def check_existing_download(lat, lon, days_back=7):
    img_path, meta_path = get_cache_paths(lat, lon, days_back)
    if os.path.exists(img_path) and os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return img_path, meta
    return None, None

def save_download_cache(lat, lon, days_back, img_path, meta):
    _, meta_path = get_cache_paths(lat, lon, days_back)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    # img_path is already the file path to the image

def save_results(report_dict, output_path="latest_report.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, default=str)

# --- Download Sentinel Image (caches as .img and .json) ---
async def download_sentinel_image(lat, lon, days_back=7, cloud_pct=20):
    user = os.getenv("DHUS_USER", "")
    password = os.getenv("DHUS_PASSWORD", "")
    
    if not user or not password:
        raise EnvironmentError("🚨 Sentinel API credentials (DHUS_USER / DHUS_PASSWORD) are missing.")
    
    api = SentinelAPI(user, password, "https://apihub.copernicus.eu/apihub")
    bbox = {
        "type": "Polygon",
        "coordinates": [[
            [lon-0.01, lat-0.01],
            [lon+0.01, lat-0.01],
            [lon+0.01, lat+0.01],
            [lon-0.01, lat+0.01],
            [lon-0.01, lat-0.01]
        ]]
    }
    footprint = geojson_to_wkt(bbox)

    products = api.query(
        footprint,
        date=(date.today() - timedelta(days=days_back), date.today()),
        platformname='Sentinel-2',
        cloudcoverpercentage=(0, cloud_pct),
        limit=1
    )
    if not products:
        return None, None

    product_id = next(iter(products))
    meta = api.get_product_odata(product_id)
    temp_dir = tempfile.mkdtemp()
    api.download(product_id, directory_path=temp_dir)

    # 📸 B04 Band Lookup
    jp2_path = None
    for root, _, files in os.walk(temp_dir):
        for f in files:
            if "B04" in f and f.endswith(".jp2"):
                jp2_path = os.path.join(root, f)
                break

    if not jp2_path:
        raise FileNotFoundError("Band B04 image not found in Sentinel download.")

    img_cache_path, _ = get_cache_paths(lat, lon, days_back)
    import shutil
    shutil.copy2(jp2_path, img_cache_path)
    save_download_cache(lat, lon, days_back, img_cache_path, meta)
    return img_cache_path, meta

# --- NASA FIRMS ---
async def query_nasa_firms(lat, lon, radius_km=50, hours=24):
    now = datetime.datetime.utcnow()
    start_time = now - datetime.timedelta(hours=hours)
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * abs(math.cos(math.radians(lat))) or 1)
    bbox = f"{lon - lon_delta},{lat - lat_delta},{lon + lon_delta},{lat + lat_delta}"
    url = (
        "https://firms.modaps.eosdis.nasa.gov/mapserver/wfs"
        f"?service=WFS&version=1.1.0&request=GetFeature"
        f"&typeName=fires_viirs&bbox={bbox}&outputFormat=application/json"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            ct = resp.headers.get("Content-Type", "")
            if resp.status != 200:
                return [{"source": "NASA FIRMS", "error": f"HTTP {resp.status}"}]
            if "application/json" not in ct:
                sample = (await resp.text())[:300]
                return [{
                    "source": "NASA FIRMS",
                    "error": "Unexpected content type",
                    "content_type": ct,
                    "sample": sample
                }]

            data = await resp.json()
            events = []
            for f in data.get("features", []):
                p = f.get("properties", {})
                tm = f"{p.get('acq_date')} {p.get('acq_time')}"
                try:
                    dt = datetime.datetime.strptime(tm, "%Y-%m-%d %H%M")
                except:
                    continue
                if not (start_time <= dt <= now):
                    continue
                events.append({
                    "source": "NASA FIRMS",
                    "latitude": p.get("latitude"),
                    "longitude": p.get("longitude"),
                    "confidence": p.get("confidence"),
                    "brightness": p.get("bright_ti4"),
                    "acq_time": tm,
                    "type": p.get("type"),
                })
            return events

# --- Sentinel Hub ---
async def query_sentinel_hub(lat, lon, radius_km=5, date="2024-07-01"):
    token = await get_sentinel_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    url = "https://services.sentinel-hub.com/api/v1/process"

    payload = {
        "input": {
            "bounds": {
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                }
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{date}T00:00:00Z",
                            "to": f"{date}T23:59:59Z"
                        }
                    }
                }
            ]
        },
        "output": {
            "width": 512,
            "height": 512,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/png"
                    }
                }
            ]
        },
        "evalscript": """
//VERSION=3
function setup() {
    return {
        input: ["B04", "B03", "B02"],
        output: { bands: 3 }
    };
}
function evaluatePixel(sample) {
    return [sample.B04, sample.B03, sample.B02];
}
"""
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                image_bytes = await resp.read()
                return {
                    "source": "Sentinel Hub",
                    "date": date,
                    "type": "Sentinel-2 True Color",
                    "image_bytes": image_bytes,
                    "note": "Successfully retrieved image."
                }
            else:
                return {
                    "source": "Sentinel Hub",
                    "error": f"Failed with status {resp.status}",
                    "note": await resp.text()
                }

# --- Unified Multi-Source Query ---
async def query_all_satellite_sources(lat, lon, radius_km=5, date=None):
    if date is None:
        date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    results = []
    try:
        results += await query_nasa_firms(lat, lon, radius_km, 24)
    except Exception as e:
        results.append({"source": "NASA FIRMS", "error": str(e)})
    try:
        results += [await query_sentinel_hub(lat, lon, radius_km, date)]
    except Exception as e:
        results.append({"source": "Sentinel Hub", "error": str(e)})
    # Add more sources as implemented
    return results

# --- Advanced Analytics ---
def mask_clouds(image_path, threshold=0.2):
    with rasterio.open(image_path) as src:
        img = src.read(1).astype(np.float32)
        img = exposure.rescale_intensity(img, out_range='float')
        mask = img > threshold
        cloud_coverage = np.mean(mask)
    return mask, cloud_coverage

def calculate_ndvi(red_path, nir_path):
    with rasterio.open(red_path) as red, rasterio.open(nir_path) as nir:
        red_band = red.read(1).astype(np.float32)
        nir_band = nir.read(1).astype(np.float32)
        ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-6)
    return ndvi

def simple_change_detection(path1, path2):
    with rasterio.open(path1) as src1, rasterio.open(path2) as src2:
        img1 = src1.read(1).astype(np.float32)
        img2 = src2.read(1).astype(np.float32)
        diff = np.abs(img2 - img1)
        change_score = np.mean(diff)
    return diff, change_score

def detect_anomalies(image_path):
    with rasterio.open(image_path) as src:
        img = src.read(1).astype(np.float32)
        img = exposure.rescale_intensity(img, out_range='float')
        edges = feature.canny(img, sigma=3)
        entropy_img = filters.rank.entropy((img*255).astype(np.uint8), np.ones((5,5)))
        anomaly_score = np.std(entropy_img)
    return {
        "edges": edges,
        "anomaly_score": anomaly_score
    }

def texture_features(image_array, distances=[1], angles=[0]):
    glcm = graycomatrix(image_array.astype(np.uint8), distances=distances, angles=angles, levels=256, symmetric=True, normed=True)
    contrast = graycoprops(glcm, 'contrast')[0, 0]
    homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
    energy = graycoprops(glcm, 'energy')[0, 0]
    return {
        "contrast": contrast,
        "homogeneity": homogeneity,
        "energy": energy
    }

# --- Orchestrator ---
async def orchestrate_satellite_analysis(
    lat: float,
    lon: float,
    *,
    days_back: int = 7,
    cloud_pct: int = 20,
    cache: bool = True,
    export_json: bool = True,
) -> dict:
    img_path, meta = (None, None)
    if cache:
        img_path, meta = check_existing_download(lat, lon, days_back)
    if not img_path:
        img_path, meta = await download_sentinel_image(lat, lon, days_back, cloud_pct)
    if not img_path:
        return {"summary": "No Sentinel-2 image found for this location.", "success": False}

    mask, cloud_coverage = mask_clouds(img_path)
    cloud_percent = cloud_coverage * 100 if cloud_coverage is not None else None

    nir_path = img_path.replace("B04", "B08")
    ndvi = None
    ndvi_val = None
    if os.path.exists(nir_path):
        ndvi = calculate_ndvi(img_path, nir_path)
        ndvi_val = float(np.mean(ndvi))

    ndvi_change_val = None
    img_path_old, _ = await download_sentinel_image(lat, lon, days_back=30)
    if img_path_old and os.path.exists(nir_path.replace("days_back=7", "days_back=30")):
        ndvi_old = calculate_ndvi(img_path_old, nir_path.replace("B04", "B08"))
        ndvi_change_val = np.mean(np.abs(ndvi_old - ndvi)) if ndvi is not None else None

    change_score = None
    if img_path_old:
        _, change_score = simple_change_detection(img_path_old, img_path)

    anomaly = detect_anomalies(img_path)
    texture = texture_features((anomaly['edges']*255).astype(np.uint8))

    meta_summary = ""
    if meta:
        meta_summary = (
            f"🛰 Date: {meta.get('beginposition','')[:10]}, "
            f"Orbit: {meta.get('orbitnumber','')}, "
            f"Tile: {meta.get('title','')}"
        )

    summary_lines = [
        f"**Satellite Analytics Report** for ({lat:.4f}, {lon:.4f}):",
        f"• Cloud coverage: {cloud_percent:.1f}%" if cloud_percent is not None else "",
        f"• NDVI: {ndvi_val:.3f}" if ndvi_val is not None else "",
        f"• NDVI change (30d): {ndvi_change_val:.3f}" if ndvi_change_val is not None else "",
        f"• Change score (30d): {change_score:.3f}" if change_score is not None else "",
        f"• Anomaly score: {anomaly['anomaly_score']:.3f}",
        f"• Texture: Contrast={texture['contrast']:.2f}, Homogeneity={texture['homogeneity']:.2f}, Energy={texture['energy']:.2f}",
        meta_summary
    ]
    summary = "\n".join([line for line in summary_lines if line])

    report = {
        "lat": lat,
        "lon": lon,
        "cloud_percent": cloud_percent,
        "ndvi": ndvi_val,
        "ndvi_change": ndvi_change_val,
        "change_score": change_score,
        "anomaly_score": anomaly["anomaly_score"],
        "texture": texture,
        "meta": meta,
        "summary": summary,
        "image_path": img_path,
        "success": True
    }

    if export_json:
        save_results(report)

    return report

# --- Satellite Verification Functions (for satellite_verify.py) ---

async def satellite_image_verify(query: str) -> dict:
    import re
    match = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", query)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        return await orchestrate_satellite_analysis(lat, lon)
    return {"summary": "Unable to parse coordinates.", "cloud_coverage": None, "success": False}

async def satellite_metadata_lookup(query: str) -> dict:
    import re
    match = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", query)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        img_path, meta = await download_sentinel_image(lat, lon)
        return {"metadata": str(meta), "confidence": 1.0 if meta else 0.0}
    return {"metadata": "Unable to parse coordinates.", "confidence": 0.0}

async def satellite_reverse_search(query: str) -> dict:
    import re
    match = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", query)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        results = await query_all_satellite_sources(lat, lon)
        links = []
        for r in results:
            if isinstance(r, dict) and r.get("preview_url"):
                links.append(r["preview_url"])
        summary = f"Found {len(links)} possible matches for ({lat},{lon})."
        return {"links": links, "summary": summary, "confidence": 1.0 if links else 0.0}
    return {"links": [], "summary": "Unable to parse coordinates.", "confidence": 0.0}

__all__ = [
    "satellite_image_verify",
    "satellite_metadata_lookup",
    "satellite_reverse_search",
]
