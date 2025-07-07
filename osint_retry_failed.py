import json
import os
import re
from time import sleep
from config import COHERE_API_KEY
import cohere

OUTPUT_FILE = "osint_sources_global.json"
FAILED_FILE = "osint_failed_report.json"
API_SLEEP_SEC = 3

if COHERE_API_KEY is None:
    raise ValueError("COHERE_API_KEY is not set.")

client = cohere.Client(COHERE_API_KEY)

def remove_emojis(text):
    if not isinstance(text, str):
        return text
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002B00-\U00002BFF"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    text = ''.join(c for c in text if ord(c) < 128)
    return text

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        msg = " ".join(str(a) for a in args)
        safe = msg.encode("utf-8", errors="replace").decode("utf-8")
        print("[Unicode-safe]", safe)

def extract_json_array(text):
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    match = re.search(r'\[\s*[\s\S]*?\]', text)
    if match:
        json_array = match.group(0)
        json_array = re.sub(r',\s*]', ']', json_array)
        return json_array.strip()
    return None

def osint_source_prompt(country):
    return f"""
Generate a list of at least 100 OSINT sources for {country} using 10 buckets (e.g., Government, National Media, Regional Media, NGO, Tech, Cyber, Community, Data Portals, Intelligence, Trackers).

Each entry must be a JSON object with:
- country
- source_name
- bucket
- trust_tier (1–3)
- access (RSS/API/Scrape)
- language
- notes

Return a pure JSON array only, with no explanation or extra text.
"""

def ask_cohere(prompt):
    try:
        safe_print(f"[AI] Asking: {prompt[:40]}...")
        response = client.chat(
            message=prompt,
            model="command-r",
            max_tokens=2048,
            temperature=0.7,
        )
        content = response.text
        return content.strip() if content is not None else None
    except Exception as e:
        safe_print(f"[ERROR] Cohere error: {e}")
        return None

def append_osint_data(continent, country, sources):
    with open(OUTPUT_FILE, "r+", encoding='utf-8') as f:
        data = json.load(f)
        if continent not in data:
            data[continent] = {}
        if country in data[continent]:
            safe_print(f"[INFO] {country} already collected, skipping save.")
            return
        data[continent][country] = sources
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
    safe_print(f"[INFO] Saved {country} under {continent}")

def retry_failed_countries():
    if not os.path.exists(FAILED_FILE):
        safe_print(f"[ERROR] Failed report {FAILED_FILE} not found.")
        return

    # Always read the failed report as a JSON array
    with open(FAILED_FILE, "r", encoding="utf-8") as f:
        try:
            failed_countries = json.load(f)
        except Exception:
            # fallback: line-delimited JSON
            f.seek(0)
            failed_countries = [json.loads(line) for line in f if line.strip()]

    if not failed_countries:
        safe_print("[INFO] No failed countries to retry.")
        return

    new_failed = []
    for entry in failed_countries:
        continent = entry["continent"]
        country = entry["country"]
        safe_print(f"\n[RETRY] {country} in {continent}")

        # Pre-check: skip if already present
        with open(OUTPUT_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        if continent in data and country in data[continent]:
            safe_print(f"[INFO] {country} already exists, skipping API call.")
            continue

        sources_raw = ask_cohere(osint_source_prompt(country))
        safe_print(f"Raw sources response for {country}:", repr(sources_raw))
        if not sources_raw:
            safe_print(f"[ERROR] Failed to get sources for {country}.")
            new_failed.append({"continent": continent, "country": country, "reason": "No response"})
            continue
        try:
            sources_json = extract_json_array(sources_raw)
            if sources_json is not None:
                cleaned_json = remove_emojis(sources_json)
                sources = json.loads(cleaned_json)
                append_osint_data(continent, country, sources)
            else:
                safe_print(f"[ERROR] No JSON array found in Cohere response for {country}. Skipping.")
                new_failed.append({"continent": continent, "country": country, "reason": "No JSON array"})
        except Exception as e:
            safe_print(f"[ERROR] Error generating sources for {country}: {e}")
            new_failed.append({"continent": continent, "country": country, "reason": str(e)})
        sleep(API_SLEEP_SEC)

    # Save new failures as a JSON array (atomic, no duplicates)
    if new_failed:
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(new_failed, f, indent=2)
        safe_print(f"[REPORT] Wrote {len(new_failed)} failures to {FAILED_FILE}")
    else:
        # Remove the failed file if all succeeded
        os.remove(FAILED_FILE)
        safe_print("[REPORT] All retries succeeded! Removed the failed report.")

if __name__ == "__main__":
    retry_failed_countries()