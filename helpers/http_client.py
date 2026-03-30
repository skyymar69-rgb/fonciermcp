import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_client: Optional[httpx.AsyncClient] = None

async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": "FoncierMCP/1.0"},
            follow_redirects=True,
        )
    return _client

async def fetch_json(url: str, params: dict = None) -> Optional[dict]:
    client = await get_client()
    try:
        r = await client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} — {url}")
        return None
    except Exception as e:
        logger.error(f"Erreur réseau — {url}: {e}")
        return None