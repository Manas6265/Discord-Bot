import openai
import os
import logging
import asyncio
import aiohttp
from config import OPENAI_API_KEY, GEMINI_API_KEY, HUGGINGFACE_API_KEY, COHERE_API_KEY
from openai import AsyncOpenAI

# --- Setup logging ---
logger = logging.getLogger("ai_helpers")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s][%(asctime)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- API Keys ---
openai.api_key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY
openai_client = AsyncOpenAI(api_key=openai.api_key)

# === AI PROVIDER HELPERS ===

async def ask_openai(prompt: str) -> str:
    """Ask OpenAI's GPT model with a prompt and return the response."""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  # Forcing the free model for now
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=256
        )
        content = response.choices[0].message.content
        return content.strip() if content else "No answer returned."
    except Exception as e:
        logger.error(f"OpenAI ask failed: {str(e)}")
        return "Error during OpenAI completion."

async def ask_gemini(prompt: str) -> str:
    """Ask Gemini model (placeholder)."""
    # TODO: Replace with real Gemini API call
    return "Gemini answer (placeholder)"

async def ask_huggingface(prompt: str) -> str:
    """Ask HuggingFace model (placeholder)."""
    # TODO: Replace with real HuggingFace API call
    return "HuggingFace answer (placeholder)"

async def ask_cohere(prompt: str) -> str:
    """Ask Cohere model (placeholder)."""
    # TODO: Replace with real Cohere API call
    return "Cohere answer (placeholder)"

# === SUMMARIZE ===

async def summarize_openai(claim, context):
    """Summarize findings from context related to a claim using OpenAI."""
    try:
        prompt = (
            f"Claim: {claim}\n"
            f"Context: {context}\n\n"
            "Summarize the findings from the context that relate directly to the claim. Be concise, factual, and highlight any contradictions or confirmations."
        )
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert OSINT analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300
        )
        content = response.choices[0].message.content
        return content.strip() if content else "No summary returned."
    except Exception as e:
        logger.error(f"Summarization failed: {str(e)}")
        return "Error during summarization."

async def summarize_osint_footprint(results: list) -> str:
    """
    Summarize OSINT footprint results using cloud AI, prioritizing
    Gemini > HuggingFace > Cohere > OpenAI.
    Returns a short ASCII summary string.
    """
    context_lines = []
    for r in results:
        status = r.get("status")
        if status is True:
            status_str = "[+] Positive"
        elif status is False:
            status_str = "[-] Negative"
        elif status is None:
            status_str = "[!] Error"
        else:
            status_str = str(status)
        context_lines.append(f"{r.get('source', 'Unknown')}: {status_str} | {r.get('details', '')}")
    context = "\n".join(context_lines)

    prompt = (
        "You are an OSINT analyst. Given these source check results, "
        "write a short, clear risk summary and suggest next steps. "
        "Use only ASCII, no emoji.\n\n"
        f"Results:\n{context}\n\n"
        "Summary:"
    )

    # Try Gemini first
    try:
        summary = await ask_gemini(prompt)
        if summary and "placeholder" not in summary.lower():
            return summary.strip()
    except Exception as e:
        logger.warning(f"Gemini summarization failed: {e}")

    # Try HuggingFace and Cohere in parallel
    try:
        hf_task = asyncio.create_task(ask_huggingface(prompt))
        cohere_task = asyncio.create_task(ask_cohere(prompt))
        hf_result, cohere_result = await asyncio.gather(hf_task, cohere_task)
        for summary in [hf_result, cohere_result]:
            if summary and "placeholder" not in summary.lower():
                return summary.strip()
    except Exception as e:
        logger.warning(f"HuggingFace/Cohere summarization failed: {e}")

    # Fallback: OpenAI
    try:
        summary = await ask_openai(prompt)
        return summary.strip() if summary else "No summary generated."
    except Exception as e:
        logger.error(f"OpenAI summarization failed: {e}")
        return "No summary generated (all AI providers failed)."

# === EXTRACT ===

async def extract_openai(claim, context):
    """Extract factual data points from context related to a claim using OpenAI."""
    try:
        prompt = (
            f"Claim: {claim}\n"
            f"Context: {context}\n\n"
            "Extract all factual data points (names, dates, numbers, locations, etc.) related to the claim. Format them as bullet points."
        )
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI specialized in information extraction."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=300
        )
        content = response.choices[0].message.content
        return content.strip() if content else "No facts extracted."
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        return "Error during fact extraction."

# === PLACEHOLDER PROVIDER FUNCTIONS ===

# Summarize
async def summarize_gemini(text): return "Gemini summary (placeholder)"
async def summarize_huggingface(text): return "HuggingFace summary (placeholder)"
async def summarize_cohere(text): return "Cohere summary (placeholder)"

# Compare
async def compare_gemini(items): return "Gemini comparison (placeholder)"
async def compare_openai(items): return "OpenAI comparison (placeholder)"
async def compare_huggingface(items): return "HuggingFace comparison (placeholder)"
async def compare_cohere(items): return "Cohere comparison (placeholder)"

# Extract
async def extract_gemini(args): return "Gemini extraction (placeholder)"
async def extract_huggingface(args): return "HuggingFace extraction (placeholder)"
async def extract_cohere(args): return "Cohere extraction (placeholder)"

# Cite
async def cite_gemini(query): return "Gemini citations (placeholder)"
async def cite_openai(query): return "OpenAI citations (placeholder)"
async def cite_huggingface(query): return "HuggingFace citations (placeholder)"
async def cite_cohere(query): return "Cohere citations (placeholder)"

# Recommend
async def recommend_gemini(topic): return "Gemini recommendations (placeholder)"
async def recommend_openai(topic): return "OpenAI recommendations (placeholder)"
async def recommend_huggingface(topic): return "HuggingFace recommendations (placeholder)"
async def recommend_cohere(topic): return "Cohere recommendations (placeholder)"

# Timeline
async def timeline_gemini(topic): return "Gemini timeline (placeholder)"
async def timeline_openai(topic): return "OpenAI timeline (placeholder)"
async def timeline_huggingface(topic): return "HuggingFace timeline (placeholder)"
async def timeline_cohere(topic): return "Cohere timeline (placeholder)"

# Trend
async def trend_gemini(topic): return "Gemini trend analysis (placeholder)"
async def trend_openai(topic): return "OpenAI trend analysis (placeholder)"
async def trend_huggingface(topic): return "HuggingFace trend analysis (placeholder)"
async def trend_cohere(topic): return "Cohere trend analysis (placeholder)"
