import logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
GEO_API = "https://georisques.gouv.fr/api/v1"

async def get_erp_risks(address: str) -> dict:
    """Risques naturels et technologiques pour une adresse (georisques.gouv.fr).
    Args:
        address: Adresse complete
    Returns: Liste des risques avec niveau et source.
    """
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _risks(geo["lat"], geo["lon"])

async def _risks(lat: float, lon: float) -> dict:
    data = await fetch_json(f"{GEO_API}/resultats_rapport_risques", {"latlon": f"{lon},{lat}"})
    if not data:
        return {"risques": [], "synthese": "Donnees indisponibles", "nb_risques": 0}
    risques = []
    for key, label in [("inondation","Inondation"),("mvt_terrain","Mouvement de terrain"),("argile","Retrait-gonflement des argiles")]:
        if data.get(key, {}).get("exposed"):
            risques.append({"type": label, "niveau": data[key].get("level","Present"), "detail": data[key].get("description","")})
    if data.get("seisme"):
        risques.append({"type": "Seisme", "niveau": f"Zone {data['seisme'].get('zone')}", "detail": "Zonage sismique reglementaire"})
    if data.get("radon"):
        risques.append({"type": "Radon", "niveau": f"Categorie {data['radon'].get('category')}", "detail": "Potentiel radon du sous-sol"})
    return {"risques": risques, "nb_risques": len(risques), "synthese": "Aucun risque majeur" if not risques else f"{len(risques)} risque(s)", "source": "Georisques - BRGM / MTE"}