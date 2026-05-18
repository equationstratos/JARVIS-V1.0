"""
Web utils — version optimisée

Optimisations :
- Session aiohttp partagée (TCP keep-alive)
- Timeouts agressifs (10s plutôt que 60s)
- Parser lxml plus rapide que html.parser quand dispo
- Limite de résultats pour éviter le scraping inutile
"""
import aiohttp
from typing import Optional


_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    """Session HTTP partagée, créée à la demande."""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=20, limit_per_host=10,
            keepalive_timeout=60, enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        _session = aiohttp.ClientSession(
            connector=connector, timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36"
            },
        )
    return _session


async def search_duckduckgo(query: str, max_results: int = 5) -> str:
    """Recherche web via DuckDuckGo HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: beautifulsoup4 not installed."

    # Choisir lxml si dispo (10x plus rapide que html.parser)
    parser = "html.parser"
    try:
        import lxml  # noqa
        parser = "lxml"
    except ImportError:
        pass

    url = f"https://html.duckduckgo.com/html/?q={query}"
    try:
        session = await _get_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return f"Search failed (HTTP {resp.status})"
            html = await resp.text()
    except Exception as e:
        return f"Search error: {e}"

    soup = BeautifulSoup(html, parser)
    results = []
    for i, item in enumerate(soup.find_all("div", class_="result__body"), 1):
        if i > max_results:
            break
        title_el = item.find("a", class_="result__a")
        snippet_el = item.find("a", class_="result__snippet")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        results.append(f"{i}. {title}\n   {snippet}")

    return "\n\n".join(results) if results else "No results found."


async def cleanup():
    """À appeler au shutdown du serveur."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
