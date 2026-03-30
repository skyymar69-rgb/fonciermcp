import asyncio, logging
from helpers.geocoder import resolve
from tools.dvf import _dvf
from tools.risks import _risks
from tools.plu import _plu
from tools.dpe import _dpe

logger = logging.getLogger(__name__)

async def analyze_parcel(address: str, radius_dvf: int = 500) -> dict:
    """Analyse complete d une adresse fonciere.
    Consolide en une requete : cadastre, prix DVF, regles PLU, risques et DPE.
    Args:
        address: Adresse complete (ex: 12 place Bellecour, 69002 Lyon)
        radius_dvf: Rayon de recherche des ventes en metres (defaut 500)
    Returns: Rapport foncier complet structure.
    """
    loc = await resolve(address)
    if not loc:
        return {"success": False, "error": f"Adresse introuvable : {address}", "address": address}
    lat, lon = loc["lat"], loc["lon"]
    dvf, risks, plu, dpe = await asyncio.gather(_dvf(lat, lon, radius_dvf), _risks(lat, lon), _plu(lat, lon), _dpe(loc.get("citycode")), return_exceptions=True)
    safe = lambda r, fb=None: fb if isinstance(r, Exception) else r
    return {"success": True, "address": loc["address_normalized"], "city": loc.get("city"), "coordinates": {"lat": lat, "lon": lon}, "geocoding_score": loc.get("score"), "cadastre": loc.get("parcel"), "plu": safe(plu), "dvf": safe(dvf, {"error": "DVF indisponible"}), "risks": safe(risks, {"error": "Georisques indisponible"}), "dpe": safe(dpe), "meta": {"dvf_radius_m": radius_dvf, "source": "FoncierMCP - donnees publiques officielles francaises"}}