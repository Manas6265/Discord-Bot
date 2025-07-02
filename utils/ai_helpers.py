import openai
import os
import logging
import asyncio
import aiohttp
from config import OPENAI_API_KEY, GEMINI_API_KEY, HUGGINGFACE_API_KEY, COHERE_API_KEY
from openai import AsyncOpenAI

openai.api_key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY
# Create an async OpenAI client
openai_client = AsyncOpenAI(api_key=openai.api_key)
# Placeholder functions for other AI services
async def ask_gemini(prompt: str) -> str:
    return "Gemini answer (placeholder)"

async def ask_huggingface(prompt: str) -> str:
    return "HuggingFace answer (placeholder)"

async def ask_cohere(prompt: str) -> str:
    return "Cohere answer (placeholder)"

# === ASK ===
async def ask_openai(prompt: str) -> str:
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=256
        )
        content = response.choices[0].message.content
        return content.strip() if content else "No answer returned."
    except Exception as e:
        logging.error(f"OpenAI ask failed: {str(e)}")
        return "Error during OpenAI completion."

# === SUMMARIZE ===
async def summarize_openai(claim, context):
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
        logging.error(f"Summarization failed: {str(e)}")
        return "Error during summarization."

# === EXTRACT ===
async def extract_openai(claim, context):
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
        logging.error(f"Extraction failed: {str(e)}")
        return "Error during fact extraction."

# === PLACEHOLDERS FOR OTHERS ===
async def summarize_gemini(text): return "Gemini summary (placeholder)"
async def summarize_huggingface(text): return "HuggingFace summary (placeholder)"
async def summarize_cohere(text): return "Cohere summary (placeholder)"

async def compare_gemini(items): return "Gemini comparison (placeholder)"
async def compare_openai(items): return "OpenAI comparison (placeholder)"
async def compare_huggingface(items): return "HuggingFace comparison (placeholder)"
async def compare_cohere(items): return "Cohere comparison (placeholder)"

async def extract_gemini(args): return "Gemini extraction (placeholder)"
async def extract_huggingface(args): return "HuggingFace extraction (placeholder)"
async def extract_cohere(args): return "Cohere extraction (placeholder)"

async def cite_gemini(query): return "Gemini citations (placeholder)"
async def cite_openai(query): return "OpenAI citations (placeholder)"
async def cite_huggingface(query): return "HuggingFace citations (placeholder)"
async def cite_cohere(query): return "Cohere citations (placeholder)"

async def recommend_gemini(topic): return "Gemini recommendations (placeholder)"
async def recommend_openai(topic): return "OpenAI recommendations (placeholder)"
async def recommend_huggingface(topic): return "HuggingFace recommendations (placeholder)"
async def recommend_cohere(topic): return "Cohere recommendations (placeholder)"

async def timeline_gemini(topic): return "Gemini timeline (placeholder)"
async def timeline_openai(topic): return "OpenAI timeline (placeholder)"
async def timeline_huggingface(topic): return "HuggingFace timeline (placeholder)"
async def timeline_cohere(topic): return "Cohere timeline (placeholder)"

async def trend_gemini(topic): return "Gemini trend analysis (placeholder)"
async def trend_openai(topic): return "OpenAI trend analysis (placeholder)"
async def trend_huggingface(topic): return "HuggingFace trend analysis (placeholder)"
async def trend_cohere(topic): return "Cohere trend analysis (placeholder)"