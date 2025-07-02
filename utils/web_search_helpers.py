import aiohttp

async def duckduckgo_search(query, max_results=3):
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_redirect": 1,
        "no_html": 1,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            results = []
            for topic in data.get("RelatedTopics", []):
                if "Text" in topic and "FirstURL" in topic:
                    results.append(f"{topic['Text']} ({topic['FirstURL']})")
                if len(results) >= max_results:
                    break
            return results