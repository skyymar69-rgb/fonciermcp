import logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"

async def get_dpe(address: str, limit: int = 10) -> dict:
    """DPE ADEME pour une adresse. Args: address, limit. Returns: etiquettes energie."""
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _dpe(geo.get("citycode"), limit)

async def _dpe(citycode: str, limit: int = 10) -> dict:
    if not citycode:
        return {"dpe": [], "error": "Code commune manquant"}
    data = await fetch_json(DPE_API, {
        "code_insee_commune_actualise": citycode,
        "size": limit,
        "select": "numero_dpe,classe_consommation_energie,classe_estimation_ges,date_etablissement_dpe,surface_thermique_lot,annee_construction",
    })
    if not data or not data.get("results"):
        return {"dpe": [], "citycode": citycode, "nb": 0}
    items = [{"numero": r.get("numero_dpe"), "etiquette": r.get("classe_consommation_energie"), "ges": r.get("classe_estimation_ges"), "date": r.get("date_etablissement_dpe"), "surface_m2": r.get("surface_thermique_lot"), "annee": r.get("annee_construction")} for r in data["results"]]
    etiq = [i["etiquette"] for i in items if i["etiquette"]]
    return {"dpe": items, "stats_etiquettes": {e: etiq.count(e) for e in sorted(set(etiq))}, "nb": len(items), "source": "ADEME — Base nationale des DPE"}
