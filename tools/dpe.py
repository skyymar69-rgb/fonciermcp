import logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"

async def get_dpe(address: str, limit: int = 10) -> dict:
    """Diagnostics de performance energetique (DPE) ADEME pour une adresse.
    Args:
        address: Adresse complete
        limit: Nombre de resultats (defaut 10)
    Returns: Liste DPE avec etiquette energie, GES, surface, annee construction.
    """
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _dpe(geo.get("citycode"), limit)

async def _dpe(citycode: str, limit: int = 10) -> dict:
    if not citycode:
        return {"dpe": [], "error": "Code commune manquant"}
    data = await fetch_json(DPE_API, {"Code_INSEE_commune_actualise": citycode, "size": limit, "select": "N°DPE,Etiquette_DPE,Etiquette_GES,Date_réception_DPE,Adresse_(BAN),Surface_habitable_logement,Année_construction"})
    if not data or not data.get("results"):
        return {"dpe": [], "citycode": citycode, "nb": 0}
    items = [{"numero": r.get("N°DPE"), "etiquette": r.get("Etiquette_DPE"), "ges": r.get("Etiquette_GES"), "date": r.get("Date_réception_DPE"), "adresse": r.get("Adresse_(BAN)"), "surface_m2": r.get("Surface_habitable_logement"), "annee_construction": r.get("Année_construction")} for r in data["results"]]
    etiq = [i["etiquette"] for i in items if i["etiquette"]]
    return {"dpe": items, "stats_etiquettes": {e: etiq.count(e) for e in set(etiq)}, "nb": len(items), "source": "ADEME - Base nationale des DPE"}