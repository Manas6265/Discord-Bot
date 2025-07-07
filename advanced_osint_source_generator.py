import json
import os
import re
import sys
import time
import threading
import cohere
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import COHERE_API_KEY

# --- CONFIG ---
OUTPUT_FILE = "osint_sources_global.json"
BATCH_SIZE = 20    # How many sources per API call
MAX_BATCHES = 5    # Up to 100 sources per country (20*5)
MAX_WORKERS = 3    # Number of threads, tuned to rate limit (10 calls/min max)
COHERE_CALL_LIMIT = 10  # 10 calls per minute total allowed

if COHERE_API_KEY is None:
    raise ValueError("COHERE_API_KEY is not set.")

# --- Global rate limiter state ---
rate_limit_lock = threading.Lock()
call_timestamps = []

def wait_for_rate_limit():
    global call_timestamps
    with rate_limit_lock:
        now = time.time()
        # Remove timestamps older than 60 seconds
        call_timestamps = [t for t in call_timestamps if now - t < 60]

        if len(call_timestamps) >= COHERE_CALL_LIMIT:
            # Need to wait until earliest call is older than 60s
            wait_time = 60 - (now - call_timestamps[0]) + 0.1
            print(f"[RateLimit] Waiting {wait_time:.1f}s to respect 10 calls/min limit...")
            time.sleep(wait_time)
            # Clean again after wait
            now = time.time()
            call_timestamps = [t for t in call_timestamps if now - t < 60]

        # Record current call
        call_timestamps.append(time.time())

# --- LLM CLIENT (thread-safe, global rate limit) ---
class LLMClient:
    def __init__(self, cohere_client=None):
        self.cohere_client = cohere_client

    def ask(self, prompt):
        return self._ask_cohere(prompt)

    def _ask_cohere(self, prompt):
        backoff = 10  # initial backoff seconds on 429
        max_backoff = 80
        while True:
            wait_for_rate_limit()
            try:
                if self.cohere_client is None:
                    raise RuntimeError("Cohere client is not initialized.")
                response = self.cohere_client.chat(
                    message=prompt,
                    model="command-r",
                    max_tokens=2048,
                    temperature=0.3,
                )
                return response.text.strip() if response.text else None
            except Exception as e:
                status_code = getattr(e, 'status_code', None)
                if status_code == 429:
                    print(f"[Cohere] 429 Too Many Requests. Backing off for {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
                    continue
                print(f"[Cohere] Error: {e}")
                return None

# --- INIT LLM CLIENT ---
cohere_client = cohere.Client(COHERE_API_KEY)
llm_client = LLMClient(cohere_client=cohere_client)

def ask_llm(prompt):
    return llm_client.ask(prompt)

# --- UTILS ---
def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9_\-]', '_', name)

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
        message = " ".join(str(arg) for arg in args)
        safe_message = message.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
        print(safe_message, **kwargs)
    except Exception as e:
        print("[safe_print error]", str(e))

def extract_json_array(text):
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    match = re.search(r'\[\s*[\s\S]*?\]', text)
    if match:
        json_array = match.group(0)
        json_array = re.sub(r',\s*]', ']', json_array)
        return json_array.strip()
    return None

def normalize_source_name(name):
    return re.sub(r'\W+', '', name or '').lower()


# --- PROMPTS ---
CONTINENTS_PROMPT = (
    "List all current major continents on Earth as a JSON array. "
    "Return only the JSON array, with no explanation or extra text."
)

COUNTRIES_PROMPT_TEMPLATE = (
    "List all sovereign countries in the continent: {}. "
    "Return only a JSON array, with no explanation or extra text."
)

def osint_source_prompt(country, batch_num=1):
    return f"""
You are an expert OSINT cataloguer.
Generate a list of {BATCH_SIZE} OSINT sources for {country} using 10 buckets (e.g., Government, National Media, Regional Media, NGO, Tech, Cyber, Community, Data Portals, Intelligence, Trackers).
Each entry must be a JSON object with:
- country
- source_name
- bucket
- trust_tier (1–3)
- access (RSS/API/Scrape)
- language
- notes
Respond strictly in valid JSON. Do not include markdown, explanation, or comments.
If you cannot find {BATCH_SIZE} sources, return as many as possible, but always return a valid JSON array.
Batch: {batch_num}
"""

# --- FILE HANDLING ---
def init_json_file():
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump({}, f, indent=2)
        safe_print(f"[INFO] Initialized new file: {OUTPUT_FILE}")

def append_osint_data(continent, country, sources):
    with threading.Lock():
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

# --- PER COUNTRY TASK ---
def collect_country_sources(continent, country):
    safe_print(f"\n[COLLECT] Sources for: {country} ({continent})")
    all_sources = []

    for batch_num in range(1, MAX_BATCHES + 1):
        sources_raw = ask_llm(osint_source_prompt(country, batch_num))
        safe_print(f"Raw sources response for {country} (batch {batch_num}):\n{sources_raw}\n{'='*60}")
        if not sources_raw:
            safe_print(f"[ERROR] Failed to get sources for {country}, batch {batch_num}.")
            return {"continent": continent, "country": country, "reason": f"No response (batch {batch_num})"}

        try:
            sources_json = extract_json_array(sources_raw)
            if sources_json is not None:
                cleaned_json = remove_emojis(sources_json)
                batch_sources = json.loads(cleaned_json)
                existing_names = {normalize_source_name(s['source_name']) for s in all_sources}
                batch_sources = [s for s in batch_sources if normalize_source_name(s['source_name']) not in existing_names]
                all_sources.extend(batch_sources)
                if len(batch_sources) < BATCH_SIZE:
                    break
            else:
                safe_print(f"[ERROR] No JSON array found in LLM response for {country} (batch {batch_num}). Skipping batch.")
                return {
                    "continent": continent,
                    "country": country,
                    "reason": f"No JSON array (batch {batch_num})",
                    "raw_response": sources_raw[:500]
                }
        except Exception as e:
            safe_print(f"[ERROR] Error generating sources for {country} (batch {batch_num}): {e}")
            return {
                "continent": continent,
                "country": country,
                "reason": f"{str(e)} (batch {batch_num})",
                "raw_response": sources_raw[:500]
            }

    if all_sources:
        append_osint_data(continent, country, all_sources)
        return None
    else:
        safe_print(f"[ERROR] No sources collected for {country} after all batches.")
        return {"continent": continent, "country": country, "reason": "No sources collected"}

# --- MAIN COLLECTION LOGIC ---
def run_global_collection():
    init_json_file()
    failed_countries = []

    continents_raw = ask_llm(CONTINENTS_PROMPT)
    safe_print("Raw continents response:", repr(continents_raw))
    if not continents_raw:
        safe_print("[ERROR] Failed to get continents from LLM.")
        return
    try:
        continents_json = extract_json_array(continents_raw)
        if continents_json is not None:
            continents = json.loads(continents_json)
        else:
            safe_print("[ERROR] No JSON array found for continents.")
            return
    except Exception as e:
        safe_print(f"[ERROR] Failed to parse continent list: {e}")
        return

    for continent in continents:
        safe_print(f"\n[START] Continent: {continent}")

        countries_raw = ask_llm(COUNTRIES_PROMPT_TEMPLATE.format(continent))
        safe_print(f"Raw countries response for {continent}:", repr(countries_raw))
        if not countries_raw:
            safe_print(f"[ERROR] Failed to get countries for {continent}.")
            continue
        try:
            countries_json = extract_json_array(countries_raw)
            if countries_json is not None:
                countries = json.loads(countries_json)
            else:
                safe_print(f"[ERROR] No JSON array found for countries in {continent}.")
                continue
        except Exception as e:
            safe_print(f"[ERROR] Failed to parse country list for {continent}: {e}")
            continue

        with open(OUTPUT_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)

        # Filter countries already collected
        countries_to_collect = [c for c in countries if continent not in data or c not in data[continent]]

        # Use ThreadPoolExecutor to parallelize country collection
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_country = {executor.submit(collect_country_sources, continent, country): country for country in countries_to_collect}

            for future in as_completed(future_to_country):
                country = future_to_country[future]
                result = future.result()
                if result is not None:
                    # means failure dict
                    failed_countries.append(result)

        # Save per-continent file
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        safe_continent = sanitize_filename(continent)
        with open(f"osint_sources_{safe_continent}.json", "w", encoding="utf-8") as f_cont:
            json.dump({continent: data.get(continent, {})}, f_cont, indent=2)
        safe_print(f"[INFO] Saved per-continent file: osint_sources_{safe_continent}.json")

    if failed_countries:
        with open("osint_failed_report.json", "w", encoding="utf-8") as f:
            json.dump(failed_countries, f, indent=2)
        safe_print(f"[REPORT] Wrote failures to osint_failed_report.json ({len(failed_countries)} issues)")
    else:
        safe_print("[REPORT] All countries processed successfully!")

# --- MAIN ---
if __name__ == "__main__":
    safe_print("[START] Running global OSINT source collection...")
    try:
        run_global_collection()
    except Exception as e:
        safe_print(f"[ERROR] Global collection failed: {e}")
        sys.exit(1)
    safe_print("[FINISH] Global OSINT source collection completed.")
    sys.exit(0)
# --- END OF FILE ---
