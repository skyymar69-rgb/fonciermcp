"""Geocodeur robuste BAN pour adresses françaises."""
import httpx, logging
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "LexFoncier/2.0 (contact@lexfoncier.fr)",
    "Accept": "application/json",
}

ARRONDISSEMENT_TO_CADASTRE = {
    "69381":"69123","69382":"69123","69383":"69123","69384":"69123","69385":"69123",
    "69386":"69123","69387":"69123","69388":"69123","69389":"69123",
    "75101":"75056","75102":"75056","75103":"75056","75104":"75056","75105":"75056",
    "75106":"75056","75107":"75056","75108":"75056","75109":"75056","75110":"75056",
    "75111":"75056","75112":"75056","75113":"75056","75114":"75056","75115":"75056",
    "75116":"75056","75117":"75056","75118":"75056","75119":"75056","75120":"75056",
    "13201":"13055","13202":"13055","13203":"13055","13204":"13055","13205":"13055",
    "13206":"13055","13207":"13055","13208":"13055","13209":"13055","13210":"13055",
    "13211":"13055","13212":"13055","13213":"13055","13214":"13055","13215":"13055",
    "13216":"13055",
}

async def geocode_address(address: str) -> dict:
    """Geocode une adresse française via BAN avec fallback robuste."""
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers=HEADERS
    ) as client:

        # Essai 1 : housenumber strict
        for attempt_params in [
            {"q": address, "limit": 5, "type": "housenumber"},
            {"q": address, "limit": 5},
            {"q": address, "limit": 5, "autocomplete": 0},
        ]:
            try:
                r = await client.get(
                    "https://api-adresse.data.gouv.fr/search/",
                    params=attempt_params
                )
                if r.status_code != 200:
                    logger.warning(f"BAN HTTP {r.status_code} for {address}")
                    continue
                body = r.text.strip()
                if not body:
                    logger.warning(f"BAN empty body for {address}")
                    continue
                data = r.json()
                feats = data.get("features", [])
                if feats:
                    return _parse_ban(feats, address)
            except Exception as e:
                logger.warning(f"BAN attempt failed: {e}")
                continue

        raise ValueError(f"Adresse introuvable: {address}")

def _parse_ban(features: list, address: str) -> dict:
    best = max(features, key=lambda f: f["properties"].get("score", 0))
    p = best["properties"]
    lon, lat = best["geometry"]["coordinates"]
    citycode = p.get("citycode", "")
    citycode_cadastre = ARRONDISSEMENT_TO_CADASTRE.get(citycode, citycode)
    ctx = p.get("context", "")
    parts = [x.strip() for x in ctx.split(",")]
    return {
        "lat": lat, "lon": lon,
        "label": p.get("label", address),
        "score": round(p.get("score", 0), 4),
        "citycode": citycode,
        "citycode_cadastre": citycode_cadastre,
        "city": p.get("city", ""),
        "postcode": p.get("postcode", ""),
        "street": p.get("street", p.get("name", "")),
        "housenumber": p.get("housenumber", ""),
        "context": ctx,
        "type": p.get("type", ""),
        "department": parts[0] if parts else "",
        "region": parts[-1] if len(parts) > 1 else "",
    }
