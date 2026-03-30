import logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
DVF_API = "https://api.dvf.etalab.gouv.fr/geoapi/mutations"

async def get_dvf_history(address: str, radius: int = 500, years: int = 5) -> dict:
    """Historique des prix de vente immobiliers autour d'une adresse (DVF / DGFiP).
    Args:
        address: Adresse complete
        radius: Rayon en metres (max 2000, defaut 500)
    Returns: Transactions, statistiques prix au m2, mediane.
    """
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _dvf(geo["lat"], geo["lon"], min(radius, 2000))

async def _dvf(lat: float, lon: float, radius: int = 500) -> dict:
    data = await fetch_json(DVF_API, {"lat": lat, "lon": lon, "dist": radius, "fields": "date_mutation,valeur_fonciere,surface_reelle_bati,type_local,nombre_pieces_principales"})
    if not data or not data.get("features"):
        return {"ventes": [], "stats": {}, "count": 0, "radius_m": radius}
    ventes = []
    for f in data["features"]:
        p = f["properties"]
        prix = p.get("valeur_fonciere")
        surf = p.get("surface_reelle_bati")
        ventes.append({"date": p.get("date_mutation"), "type": p.get("type_local"), "prix_total": prix, "surface_m2": surf, "prix_m2": round(prix / surf) if prix and surf else None, "pieces": p.get("nombre_pieces_principales")})
    ventes.sort(key=lambda x: x["date"] or "", reverse=True)
    pm2 = sorted([v["prix_m2"] for v in ventes if v["prix_m2"]])
    stats = {"prix_m2_median": pm2[len(pm2)//2], "prix_m2_moyen": round(sum(pm2)/len(pm2)), "prix_m2_min": pm2[0], "prix_m2_max": pm2[-1], "nb_transactions": len(pm2)} if pm2 else {}
    return {"ventes": ventes[:20], "stats": stats, "count": len(ventes), "radius_m": radius, "source": "DVF - DGFiP / data.gouv.fr"}