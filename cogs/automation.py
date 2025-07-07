from datetime import datetime
import asyncio
from utils.error_logging_helper import log_error
from utils.tracker import log_conversation, log_provider_decision, log_analytics

# Import analyze functions from each orchestrator-ready module
from utils.location_extractor import extract_and_geocode_locations
from cogs.ai import analyze as ai_analyze
from cogs.osint import analyze as osint_analyze
from cogs.footprint import analyze as footprint_analyze
from cogs.research import analyze as research_analyze
from cogs.timeline import analyze as timeline_analyze
from cogs.verify import analyze as verify_analyze
from cogs.reports import create_report
from cogs.satellite_verify import analyze as satellite_verify_analyze

# --- LLM wrapper: tries Gemini, Huggingface, Cohere (never OpenAI) ---
async def ask_any_llm(prompt):
    from utils.ai_helpers import ask_gemini, ask_huggingface, ask_cohere
    for fn in [ask_gemini, ask_huggingface, ask_cohere]:
        try:
            result = await fn(prompt)
            if result and isinstance(result, str):
                return result
        except Exception:
            continue
    return ""

MODULES = [
    ("AI Analysis", ai_analyze),
    ("OSINT", osint_analyze),
    ("Footprint", footprint_analyze),
    ("Research", research_analyze),
    ("Timeline", timeline_analyze),
    ("Verify", verify_analyze),
]

AGG_KEYS = ["links", "images", "texts", "locations", "audio", "text", "error"]

async def handle_query_with_status(
    query: str,
    ctx,
    status_callback,
    options: dict | None = None,
    parallel: bool = False
) -> dict:
    """
    Orchestrates analysis across all modules, gives live status via callback, and aggregates results.
    Ultra-defensive: aggregates all standard fields, including 'text' and 'error'.
    """
    # Extract session/user info for logging, always string
    session_id = str(options.get("session_id") or "") if options else ""
    user_id = str(options.get("user_id") or "") if options else ""

    # Step 1: Animated dots
    for i in range(1, 6):
        await status_callback(f"``````")
        await asyncio.sleep(0.5)
    await asyncio.sleep(0.3)

    # Step 2: Show assumptions
    assumptions = [
        "• A person",
        "• Social media account",
        "• Organization or project",
        "• Email, username, or domain"
    ]
    await status_callback(
        f"``````\n"
        f"Analyzing query: {query}\n"
        f"Assumptions:\n" +
        "\n".join(assumptions) +
        f"\n\nInitializing modules...\n"
    )
    await asyncio.sleep(0.8)

    results = []
    provider_results = []
    total = len(MODULES)

    # --- Step 3: Location extraction and satellite imagery ---
    await status_callback(f"``````")
    locations = await extract_and_geocode_locations(
        query,
        ask_llm_fn=ask_any_llm,
        max_locations=3
    )
    if locations:
        loc_report = "\n".join(
            f"{loc['name']} ({loc['latitude']:.4f}, {loc['longitude']:.4f})"
            for loc in locations
        )
        await status_callback(
            f"``````\n"
            f"Found locations:\n" +
            loc_report +
            f"\n\nFetching satellite imagery for these locations...\n"
        )
        satellite_results = []
        for loc in locations:
            coords = f"{loc['latitude']},{loc['longitude']}"
            try:
                sat_res = await satellite_verify_analyze(coords, options)
                satellite_results.append(sat_res)
            except Exception as e:
                log_error("automation.satellite_verify", e)
        results.extend(satellite_results)
    else:
        await status_callback(
            f"``````\n"
            f"No locations found in query: {query}\n"
        )

    # Step 4: Module-by-module progress (sequential for best updates)
    for idx, (name, analyze_func) in enumerate(MODULES, 1):
        await status_callback(
            f"``````\n"
            f"Analyzing query: {query}\n"
            f"Assumptions:\n" +
            "\n".join(assumptions) +
            f"\n\nInitializing modules...\n"
            f"{name} ({idx}/{total}) running...\n"
        )
        start_time = datetime.utcnow()
        try:
            res = await analyze_func(query, options)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            results.append(res)
            provider_results.append({
                "module": name,
                "result": res,
                "latency": elapsed,
                "status": "success"
            })
            log_provider_decision(
                session_id=session_id,
                query=query,
                providers_tried=[name],
                provider_results=[{
                    "module": name,
                    "latency": elapsed,
                    "status": "success"
                }],
                final_provider=name,
                final_result="success"
            )
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            log_error(f"automation.handle_query_with_status.{name}", e)
            error_result = {
                "result": {k: [] for k in AGG_KEYS},
                "confidence": 0.0,
                "details": {"error": str(e)},
                "source": name,
                "timestamp": datetime.utcnow().isoformat()
            }
            results.append(error_result)
            provider_results.append({
                "module": name,
                "error": str(e),
                "latency": elapsed,
                "status": "error"
            })
            log_provider_decision(
                session_id=session_id,
                query=query,
                providers_tried=[name],
                provider_results=[{
                    "module": name,
                    "latency": elapsed,
                    "status": "error",
                    "error": str(e)
                }],
                final_provider=name,
                final_result="error"
            )
        await asyncio.sleep(0.8)

    # Step 5: Aggregate all data types (ultra-defensive: all keys present)
    aggregated = {k: [] for k in AGG_KEYS}
    for res in results:
        result_dict = res.get("result", {})
        for dtype in AGG_KEYS:
            val = result_dict.get(dtype)
            # For 'error' and 'text', allow both string and list
            if dtype in ["error", "text"]:
                if isinstance(val, list):
                    aggregated[dtype].extend(val)
                elif isinstance(val, str) and val:
                    aggregated[dtype].append(val)
            else:
                if isinstance(val, list):
                    aggregated[dtype].extend(val)
                elif val:
                    aggregated[dtype].append(val)

    # Step 6: Generate the final report
    await status_callback(
        f"``````\n"
        f"Generating final report for query: {query}\n"
    )
    report_str = await create_report(results, aggregated, session_id=session_id, user_id=user_id)

    await status_callback(
        f"``````\n"
        f"Analysis complete for {query}!\n\n{report_str}\n"
    )

    # Step 7: Log conversation (for analytics/fine-tuning)
    log_conversation(
        session_id=session_id,
        user_query=query,
        processed_query=query,
        bot_response=report_str,
        provider="orchestrator",
        provider_version="v1",
        context={
            "channel_id": getattr(ctx, "channel", None) and ctx.channel.id or "",
            "guild_id": getattr(ctx, "guild", None) and ctx.guild.id or ""
        },
        user_info={"user_id": user_id or ""}
    )

    # Step 8: Log analytics (overall orchestration stats)
    log_analytics("orchestration_complete", 1)

    return {
        "aggregated": aggregated,
        "raw_results": results,
        "report": report_str
    }
