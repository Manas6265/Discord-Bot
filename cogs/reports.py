from typing import List, Dict, Any
from utils.tracker import log_analytics
from datetime import datetime

async def create_report(
    results: List[Dict[str, Any]],
    aggregated: Dict[str, list],
    session_id: str = "",
    user_id: str = ""
) -> str:
    """
    Aggregate and summarize results from multiple modules into a unified report string.

    Args:
        results: List of module result dicts (from analyze/handle_query).
        aggregated: Dict with all data types merged (links, images, texts, etc).
        session_id: Optional session identifier for analytics.
        user_id: Optional user identifier for analytics.

    Returns:
        A formatted report string for user display.
    """
    report = {
        "links": [],
        "images": [],
        "texts": [],
        "locations": [],
        "audio": []
    }

    # Add all aggregated items (unique only)
    for dtype in report:
        if dtype in aggregated:
            report[dtype].extend(aggregated[dtype])

    # Remove duplicates while preserving order
    for dtype in report:
        seen = set()
        unique_items = []
        for item in report[dtype]:
            if item not in seen:
                unique_items.append(item)
                seen.add(item)
        report[dtype] = unique_items

    # Build report string
    lines = []
    if report["texts"]:
        lines.append("**📝 Texts:**")
        lines.extend([f"- {t}" for t in report["texts"]])
    if report["links"]:
        lines.append("\n**🔗 Links:**")
        lines.extend([f"- {l}" for l in report["links"]])
    if report["images"]:
        lines.append("\n**🖼️ Images:**")
        lines.extend([f"- {img}" for img in report["images"]])
    if report["locations"]:
        lines.append("\n**📍 Locations:**")
        lines.extend([f"- {loc}" for loc in report["locations"]])
    if report["audio"]:
        lines.append("\n**🔊 Audio:**")
        lines.extend([f"- {a}" for a in report["audio"]])

    # Optionally, add a summary line
    total_items = sum(len(report[d]) for d in report)
    lines.append(
        f"\n_Report generated: {total_items} items from {len(results)} modules._"
    )

    report_str = "\n".join(lines)

    # Simple analytics logging (type-safe)
    log_analytics("report_generated", 1)

    return report_str
