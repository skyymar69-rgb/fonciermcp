import asyncio, logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
GPU_API = "https://apicarto.ign.fr/api/gpu"

async def check_plu_rules(address: str) -> dict:
    """Regles d urbanisme PLU pour une adresse.
    Args:
        address: Adresse complete
    Returns: Zone PLU, constructibilite, lien reglement PDF.
    """
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _plu(geo["lat"], geo["lon"])

async def _plu(lat: float, lon: float) -> dict:
    zonage, commune = await asyncio.gather(
        fetch_json(f"{GPU_API}/zone-urba", {"lon": lon, "lat": lat, "_limit": 5}),
        fetch_json(f"{GPU_API}/municipality", {"lon": lon, "lat": lat}),
        return_exceptions=True,
    )
    zones = []
    if isinstance(zonage, dict) and zonage.get("features"):
        for f in zonage["features"]:
            p = f["properties"]
            zones.append({"libelle": p.get("libelle"), "description": p.get("libelong"), "type_zone": p.get("typezone"), "url_reglement": p.get("urlfic")})
    doc = None
    if isinstance(commune, dict) and commune.get("features"):
        p = commune["features"][0]["properties"]
        doc = {"commune": p.get("nom"), "type_doc": p.get("typedoc"), "etat": p.get("etat"), "date_appro": p.get("datappro")}
    mapping = {"U": {"statut": "Constructible", "detail": "Zone urbaine."}, "AU": {"statut": "Constructible sous conditions", "detail": "Zone a urbaniser."}, "A": {"statut": "Tres limite", "detail": "Zone agricole."}, "N": {"statut": "Non constructible", "detail": "Zone naturelle."}}
    tz = zones[0].get("type_zone") if zones else None
    return {"zones": zones, "document_urbanisme": doc, "constructibilite": mapping.get(tz, {"statut": "Inconnu", "detail": f"Zone : {tz or 'non trouvee'}"}), "source": "Geoportail de l Urbanisme - IGN / DGALN"}