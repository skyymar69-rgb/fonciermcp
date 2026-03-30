import logging
from typing import Optional
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
API_ADRESSE = "https://api-adresse.data.gouv.fr"
API_CADASTRE = "https://apicarto.ign.fr/api/cadastre"

async def geocode_address(address: str) -> Optional[dict]:
    data = await fetch_json(f"{API_ADRESSE}/search/", {"q": address, "limit": 1})
    if not data or not data.get("features"):
        return None
    f = data["features"][0]
    p = f["properties"]
    c = f["geometry"]["coordinates"]
    return {
        "address_normalized": p.get("label"),
        "street": p.get("name"),
        "postcode": p.get("postcode"),
        "city": p.get("city"),
        "citycode": p.get("citycode"),
        "lon": c[0], "lat": c[1],
        "score": round(p.get("score", 0), 2),
    }

async def get_parcel(lat: float, lon: float) -> Optional[dict]:
    data = await fetch_json(f"{API_CADASTRE}/parcelle", {"lon": lon, "lat": lat, "_limit": 1})
    if not data or not data.get("features"):
        return None
    p = data["features"][0]["properties"]
    return {
        "parcel_id": p.get("id"),
        "section": p.get("section"),
        "numero": p.get("numero"),
        "surface_m2": p.get("contenance"),
        "commune": p.get("nom_com"),
        "code_dep": p.get("code_dep"),
        "code_com": p.get("code_com"),
    }

async def resolve(address: str) -> Optional[dict]:
    geo = await geocode_address(address)
    if not geo:
        return None
    parcel = await get_parcel(geo["lat"], geo["lon"])
    return {**geo, "parcel": parcel}