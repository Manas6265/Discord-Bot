import requests
import time

HF_API_KEY = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # your real key
HF_MODEL = "HuggingFaceH4/zephyr-7b-beta"  # try this open chat model
HF_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

QUERIES = [
    "What is AI?",
    "Explain quantum computing.",
    "Summarize the history of the internet.",
    "What is the capital of France?",
    "List three uses of machine learning.",
]

def query_hf(prompt):
    payload = {"inputs": prompt}
    response = requests.post(HF_URL, headers=HEADERS, json=payload)
    try:
        return response.json()
    except Exception as e:
        return {"error": str(e), "response_text": response.text, "status_code": response.status_code}

if __name__ == "__main__":
    for i, prompt in enumerate(QUERIES):
        print(f"\nQuery {i+1}: {prompt}")
        result = query_hf(prompt)
        print("Raw HuggingFace response:", result)
        time.sleep(2)
