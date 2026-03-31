"""Geocodeur robuste BAN pour adresses francaises."""
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

BAN_URLS = [
    "https://api-adresse.data.gouv.fr/search/",
    "https://photon.komoot.io/api/",
]

async def geocode_address(address: str) -> dict:
    """Geocode une adresse via BAN avec fallback Komoot."""
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers=HEADERS
    ) as client:
        # Essai 1 : BAN housenumber
        for attempt in range(2):
            params = {"q": address, "limit": 5}
            if attempt == 0:
                params["type"] = "housenumber"
            try:
                r = await client.get(
                    "https://api-adresse.data.gouv.fr/search/",
                    params=params
                )
                if r.status_code == 200:
                    text = r.text.strip()
                    if text and text.startswith("{"):
                        data = r.json()
                        feats = data.get("features", [])
                        if feats:
                            return _parse_ban(feats, address)
            except Exception as e:
                logger.warning(f"BAN attempt {attempt} failed: {e}")

        # Essai 2 : Komoot Photon (fallback gratuit)
        try:
            r2 = await client.get(
                "https://photon.komoot.io/api/",
                params={"q": address + " France", "limit": 3, "lang": "fr"}
            )
            if r2.status_code == 200 and r2.text.strip():
                data2 = r2.json()
                feats2 = data2.get("features", [])
                if feats2:
                    return _parse_komoot(feats2, address)
        except Exception as e:
            logger.warning(f"Komoot fallback failed: {e}")

        raise ValueError(f"Adresse introuvable: {address}")

def _parse_ban(feats: list, address: str) -> dict:
    best = max(feats, key=lambda f: f["properties"].get("score", 0))
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

def _parse_komoot(feats: list, address: str) -> dict:
    """Parse Photon Komoot response comme fallback BAN."""
    f = feats[0]
    p = f.get("properties", {})
    lon, lat = f["geometry"]["coordinates"]
    postcode = str(p.get("postcode", ""))
    citycode = ""
    return {
        "lat": lat, "lon": lon,
        "label": p.get("name","") + " " + postcode + " " + p.get("city",""),
        "score": 0.5,
        "citycode": citycode,
        "citycode_cadastre": citycode,
        "city": p.get("city", p.get("locality","")),
        "postcode": postcode,
        "street": p.get("street", p.get("name","")),
        "housenumber": str(p.get("housenumber","")),
        "context": p.get("state",""),
        "type": "housenumber",
        "department": postcode[:2] if postcode else "",
        "region": p.get("state",""),
    }
