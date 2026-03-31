"""Geocodeur robuste pour adresses francaises - BAN + fallbacks."""
import httpx, logging, re
logger = logging.getLogger(__name__)

# Codes INSEE arrondissements → code INSEE Cadastre
ARROND_TO_CADASTRE = {
    **{f"693{i+1:02d}":"69123" for i in range(9)},   # Lyon
    **{f"751{i+1:02d}":"75056" for i in range(20)},  # Paris
    **{f"132{i+1:02d}":"13055" for i in range(16)},  # Marseille
}

# CP → code INSEE pour grandes villes (fallback)
CP_TO_INSEE = {
    "69001":"69123","69002":"69123","69003":"69123","69004":"69123","69005":"69123",
    "69006":"69123","69007":"69123","69008":"69123","69009":"69123",
    "13001":"13055","13002":"13055","13003":"13055","13004":"13055","13005":"13055",
    "13006":"13055","13007":"13055","13008":"13055","13009":"13055","13010":"13055",
    "13011":"13055","13012":"13055","13013":"13055","13014":"13055","13015":"13055",
    "13016":"13055",
    "75001":"75056","75002":"75056","75003":"75056","75004":"75056","75005":"75056",
    "75006":"75056","75007":"75056","75008":"75056","75009":"75056","75010":"75056",
    "75011":"75056","75012":"75056","75013":"75056","75014":"75056","75015":"75056",
    "75016":"75056","75017":"75056","75018":"75056","75019":"75056","75020":"75056",
}

UA = "LexFoncier/2.0 geocoder (contact@lexfoncier.fr)"

async def geocode_address(address: str) -> dict:
    """Geocode adresse FR via BAN (User-Agent robuste) puis Komoot."""
    hdrs = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"}
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=hdrs) as c:
        # -- BAN tentative 1 : housenumber --
        for t_type in [None, "housenumber"]:
            params = {"q": address, "limit": 5}
            if t_type: params["type"] = t_type
            try:
                r = await c.get("https://api-adresse.data.gouv.fr/search/", params=params)
                if r.status_code == 200 and r.content:
                    d = r.json()
                    feats = d.get("features", [])
                    if feats:
                        return _from_ban(feats, address)
            except Exception as e:
                logger.warning(f"BAN ({t_type}): {e}")

        # -- Fallback Komoot Photon --
        try:
            r2 = await c.get("https://photon.komoot.io/api/",
                             params={"q": address+" France", "limit": 5, "lang": "fr"})
            if r2.status_code == 200 and r2.content:
                feats2 = r2.json().get("features", [])
                if feats2:
                    return _from_komoot(feats2, address, c)
        except Exception as e:
            logger.warning(f"Komoot: {e}")

        raise ValueError("Adresse introuvable: " + address)

def _cadastre_code(citycode: str, postcode: str) -> str:
    """Résout le code INSEE cadastral depuis citycode ou postcode."""
    if citycode:
        c = ARROND_TO_CADASTRE.get(citycode, citycode)
        if c != citycode: return c
        return citycode
    if postcode and postcode in CP_TO_INSEE:
        return CP_TO_INSEE[postcode]
    return ""

def _ctx_parts(ctx: str):
    parts = [x.strip() for x in ctx.split(",")]
    return (parts[0] if parts else ""), (parts[-1] if len(parts)>1 else "")

def _from_ban(feats: list, address: str) -> dict:
    best = max(feats, key=lambda f: f["properties"].get("score", 0))
    p = best["properties"]
    lon, lat = best["geometry"]["coordinates"]
    citycode = p.get("citycode", "")
    postcode  = p.get("postcode", "")
    cadastre  = _cadastre_code(citycode, postcode)
    dep, reg  = _ctx_parts(p.get("context",""))
    return {
        "lat":lat, "lon":lon, "label":p.get("label",address),
        "score":round(p.get("score",0),4),
        "citycode":citycode, "citycode_cadastre":cadastre,
        "city":p.get("city",""), "postcode":postcode,
        "street":p.get("street",p.get("name","")),
        "housenumber":p.get("housenumber",""),
        "context":p.get("context",""), "type":p.get("type",""),
        "department":dep, "region":reg,
    }

async def _from_komoot(feats: list, address: str, client) -> dict:
    """Parse Komoot + enrichit via INSEE géo API."""
    f = feats[0]; p = f.get("properties",{})
    lon, lat = f["geometry"]["coordinates"]
    postcode = str(p.get("postcode",""))
    city     = p.get("city", p.get("locality",""))
    
    # Essaie de récupérer le citycode via API geo INSEE
    citycode = ""
    try:
        rg = await client.get("https://geo.api.gouv.fr/communes",
                              params={"nom":city,"codePostal":postcode,"fields":"code","limit":1})
        if rg.status_code == 200 and rg.content:
            communes = rg.json()
            if communes:
                citycode = communes[0].get("code","")
    except Exception:
        pass

    if not citycode and postcode in CP_TO_INSEE:
        citycode = CP_TO_INSEE[postcode]

    cadastre = _cadastre_code(citycode, postcode)
    dep = postcode[:2] if postcode else ""
    return {
        "lat":lat, "lon":lon,
        "label": str(p.get("housenumber",""))+" "+str(p.get("street",p.get("name","")))+" "+postcode+" "+city,
        "score":0.6, "citycode":citycode, "citycode_cadastre":cadastre,
        "city":city, "postcode":postcode,
        "street":p.get("street",p.get("name","")),
        "housenumber":str(p.get("housenumber","")),
        "context":"", "type":"housenumber",
        "department":dep, "region":p.get("state",""),
    }
