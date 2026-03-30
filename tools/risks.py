import logging
from helpers.geocoder import geocode_address
from helpers.http_client import fetch_json

logger = logging.getLogger(__name__)
GEO_API = "https://georisques.gouv.fr/api/v1"

RISQUES_LABELS = {
    "11": "Inondation",
    "112": "Crue a debordement lent",
    "113": "Crue torrentielle",
    "116": "Remontee de nappes",
    "13": "Seisme",
    "14": "Mouvement de terrain",
    "15": "Retrait-gonflement argiles",
    "16": "Avalanche",
    "17": "Feu de foret",
    "18": "Eruption volcanique",
    "19": "Phenomene meteorologique",
    "2": "Risque technologique",
    "3": "Risque nucleaire",
}

async def get_erp_risks(address: str) -> dict:
    """Risques naturels et technologiques pour une adresse (georisques.gouv.fr).
    Args:
        address: Adresse complete
    Returns: Liste des risques identifies avec source officielle.
    """
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable : {address}"}
    return await _risks(geo["lat"], geo["lon"])

async def _risks(lat: float, lon: float) -> dict:
    data = await fetch_json(
        f"{GEO_API}/gaspar/risques",
        {"rayon": 500, "latlon": f"{lon},{lat}"}
    )
    if not data or not data.get("data"):
        return {"risques": [], "synthese": "Aucune donnee disponible", "nb_risques": 0}

    risques = []
    seen = set()
    for entry in data["data"]:
        for r in entry.get("risques_detail", []):
            label = r.get("libelle_risque_long") or RISQUES_LABELS.get(str(r.get("num_risque","")), "Risque inconnu")
            if label not in seen:
                seen.add(label)
                risques.append({
                    "type": label,
                    "code": str(r.get("num_risque", "")),
                })

    return {
        "risques": risques[:10],
        "nb_risques": len(risques),
        "synthese": "Aucun risque identifie" if not risques else f"{len(risques)} risque(s) identifies",
        "source": "Georisques — BRGM / Ministere de la Transition Ecologique",
    }
