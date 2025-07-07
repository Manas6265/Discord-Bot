import json
import os
from typing import List, Dict, Any, Optional

PREPROCESS_LOG_PATH = "tracker_state.json"
OUTPUT_PATH = "fine_tune_dataset.jsonl"

def _load_tracker_state() -> Dict[str, Any]:
    if os.path.exists(PREPROCESS_LOG_PATH):
        with open(PREPROCESS_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _sanitize(text: Optional[str]) -> str:
    return text.replace("\n", " ").strip() if text else ""

def generate_finetune_dataset(
    output_path: str = OUTPUT_PATH,
    min_samples: int = 10
) -> List[Dict[str, Any]]:
    state = _load_tracker_state()
    trails = state.get("preprocessing_trails", [])
    dataset = []
    for trail in trails:
        # Only include corrected, non-gibberish samples
        if (
            trail.get("correction")
            and trail.get("original_query")
            and len(trail["original_query"]) > 3
            and trail.get("inferred_intent", "").lower() != trail["correction"].lower()
            and not trail.get("flags", {}).get("is_gibberish", False)
        ):
            dataset.append({
                "prompt": _sanitize(trail["original_query"]),
                "completion": _sanitize(trail["correction"]),
                "raw": _sanitize(trail.get("original_query_raw", "")),
                "cleaned": _sanitize(trail.get("cleaned_query", "")),
                "intent_guess": trail.get("inferred_intent"),
                "intent_correction": trail.get("correction"),
                "token_count": trail.get("token_count", {}),
                "latency_ms": trail.get("latency_ms"),
                "language": trail.get("language"),
                "confidence": trail.get("confidence", None),
                "ambiguity_score": trail.get("ambiguity_score", None),
                "alternate_intents": trail.get("alternate_intents", []),
                "flags": trail.get("flags", {}),
                "session_id": trail.get("session_id"),
                "timestamp": trail.get("timestamp")
            })
    if len(dataset) >= min_samples:
        with open(output_path, "w", encoding="utf-8") as f:
            for pair in dataset:
                f.write(json.dumps(pair) + "\n")
        print(f"✅ Generated dataset with {len(dataset)} examples → {output_path}")
    else:
        print(f"⚠️ Not enough valid examples ({len(dataset)} found, {min_samples} required).")
    return dataset

if __name__ == "__main__":
    generate_finetune_dataset()
