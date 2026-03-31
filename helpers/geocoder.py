"""
Géocodeur robuste pour adresses françaises.
Gère correctement les arrondissements Lyon (69381-69389),
Paris (75101-75120), Marseille (13201-13216).
"""
import httpx, re, logging
logger = logging.getLogger(__name__)

# Mapping communes avec arrondissements vers code INSEE officiel (Cadastre)
# Lyon : arrondissements → code cadastre est toujours 69123
# Paris : arrondissements → code cadastre est toujours 75056
# Marseille : arrondissements → code cadastre est toujours 13055

ARRONDISSEMENT_TO_CADASTRE = {
    # Lyon
    "69381": "69123", "69382": "69123", "69383": "69123",
    "69384": "69123", "69385": "69123", "69386": "69123",
    "69387": "69123", "69388": "69123", "69389": "69123",
    # Paris
    "75101": "75056", "75102": "75056", "75103": "75056",
    "75104": "75056", "75105": "75056", "75106": "75056",
    "75107": "75056", "75108": "75056", "75109": "75056",
    "75110": "75056", "75111": "75056", "75112": "75056",
    "75113": "75056", "75114": "75056", "75115": "75056",
    "75116": "75056", "75117": "75056", "75118": "75056",
    "75119": "75056", "75120": "75056",
    # Marseille
    "13201": "13055", "13202": "13055", "13203": "13055",
    "13204": "13055", "13205": "13055", "13206": "13055",
    "13207": "13055", "13208": "13055", "13209": "13055",
    "13210": "13055", "13211": "13055", "13212": "13055",
    "13213": "13055", "13214": "13055", "13215": "13055",
    "13216": "13055",
}

async def geocode_address(address: str) -> dict:
    """
    Géocode une adresse française.
    Retourne: {lat, lon, label, score, citycode, citycode_cadastre, city, postcode, 
               street, housenumber, context, x, y, type}
    """
    async with httpx.AsyncClient(timeout=10) as client:
        # Essai 1 : housenumber exact
        r = await client.get("https://api-adresse.data.gouv.fr/search/", params={
            "q": address, "limit": 5, "type": "housenumber"
        })
        data = r.json()
        
        # Essai 2 : sans contrainte de type si pas de résultat housenumber
        if not data.get("features"):
            r = await client.get("https://api-adresse.data.gouv.fr/search/", params={
                "q": address, "limit": 5
            })
            data = r.json()
        
        if not data.get("features"):
            raise ValueError(f"Adresse introuvable : {address}")
        
        # Prend le meilleur résultat (score le plus élevé)
        best = max(data["features"], key=lambda f: f["properties"].get("score", 0))
        p = best["properties"]
        lon, lat = best["geometry"]["coordinates"]
        citycode = p.get("citycode", "")
        
        # Résout le code INSEE pour le Cadastre
        citycode_cadastre = ARRONDISSEMENT_TO_CADASTRE.get(citycode, citycode)
        
        return {
            "lat": lat,
            "lon": lon,
            "label": p.get("label", address),
            "score": round(p.get("score", 0), 4),
            "citycode": citycode,
            "citycode_cadastre": citycode_cadastre,
            "city": p.get("city", ""),
            "postcode": p.get("postcode", ""),
            "street": p.get("street", p.get("name", "")),
            "housenumber": p.get("housenumber", ""),
            "context": p.get("context", ""),
            "type": p.get("type", ""),
            "department": p.get("context", "").split(",")[0].strip() if p.get("context") else "",
            "region": p.get("context", "").split(",")[-1].strip() if p.get("context") else "",
        }
