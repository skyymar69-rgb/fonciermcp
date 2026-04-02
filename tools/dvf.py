"""
tools/dvf.py v3 — Multi-source DVF avec fallback automatique
Sources par ordre de priorite:
1. api.dvf.etalab.gouv.fr (plan Railway Hobby)
2. api.cquest.org/dvf (proxy public, accessible plan gratuit)
"""
import logging, math, httpx
from helpers.geocoder import geocode_address

logger = logging.getLogger(__name__)

DVF_ETALAB = "https://api.dvf.etalab.gouv.fr/geoapi/mutations"
DVF_CQUEST  = "https://api.cquest.org/dvf"

async def get_dvf_history(address: str, radius: int = 500, years: int = 5) -> dict:
    """Historique DVF certifie DGFiP autour d'une adresse.
    Args: address, radius (metres, max 2000m), years."""
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable: {address}", "disponible": False, "success": False}
    return await _dvf_multi(geo["lat"], geo["lon"], min(radius, 2000), geo)

async def _dvf_multi(lat: float, lon: float, radius: int, geo: dict) -> dict:
    """Essaie chaque source DVF dans l'ordre."""
    # Source 1 : etalab (Railway Hobby uniquement)
    result = await _dvf_etalab(lat, lon, radius)
    if result.get("success"):
        return result
    # Source 2 : cquest.org (accessible plan gratuit)
    result = await _dvf_cquest(lat, lon, radius, geo)
    if result.get("success"):
        return result
    # Fallback : lien direct
    return {
        "success": False,
        "disponible": False,
        "message": "DVF temporairement indisponible — upgrade Railway Hobby pour acces complet.",
        "lien_direct": f"https://explore.data.gouv.fr/fr/immobilier?lat={lat}&lng={lon}&zoom=16",
        "source": "DVF — DGFiP / data.gouv.fr",
    }

async def _dvf_etalab(lat: float, lon: float, radius: int) -> dict:
    """API officielle etalab (necessite acces DNS Railway Hobby)."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(DVF_ETALAB, params={
                "lat": lat, "lon": lon, "dist": radius,
                "fields": "date_mutation,valeur_fonciere,surface_reelle_bati,type_local,nombre_pieces_principales,code_postal,nature_mutation",
            })
            if r.status_code != 200:
                return {"success": False}
            data = r.json()
            if not data.get("features"):
                return {"success": True, "ventes_logements": [], "stats": {}, "count": 0,
                        "radius_m": radius, "source": "DVF etalab — DGFiP"}
            return _parse_etalab(data["features"], radius)
    except Exception as e:
        logger.debug(f"DVF etalab indisponible: {e}")
        return {"success": False}

async def _dvf_cquest(lat: float, lon: float, radius: int, geo: dict) -> dict:
    """Proxy cquest.org — accessible sans restriction DNS."""
    try:
        code_commune = geo.get("code_insee", "69123")
        params = {"code_commune": code_commune, "per_page": 200}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(DVF_CQUEST, params=params)
            if r.status_code != 200:
                return {"success": False}
            data = r.json()
            items = data.get("resultats", data.get("features", []))
            if not items:
                return {"success": True, "ventes_logements": [], "stats": {}, "count": 0,
                        "radius_m": radius, "source": "DVF cquest — DGFiP"}
            return _parse_cquest(items, lat, lon, radius)
    except Exception as e:
        logger.debug(f"DVF cquest indisponible: {e}")
        return {"success": False}

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    dlat = math.radians(float(lat2)-float(lat1))
    dlon = math.radians(float(lon2)-float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1)))*math.cos(math.radians(float(lat2)))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _parse_etalab(features: list, radius: int) -> dict:
    ventes = []
    for f in features:
        p = f.get("properties", {})
        prix = p.get("valeur_fonciere")
        surf = p.get("surface_reelle_bati")
        if not prix:
            continue
        nature = p.get("nature_mutation","Vente")
        if nature not in ("Vente","Adjudication","Expropriation"):
            continue
        try:
            prix_f = float(prix)
            surf_f = float(surf) if surf else None
        except:
            continue
        ventes.append({
            "date": p.get("date_mutation",""),
            "type_bien": p.get("type_local","Bien immobilier"),
            "nature": nature,
            "valeur_euros": int(prix_f),
            "surface_bati_m2": int(surf_f) if surf_f else None,
            "prix_m2": round(prix_f/surf_f) if surf_f and surf_f > 5 else None,
            "pieces": p.get("nombre_pieces_principales"),
            "code_postal": p.get("code_postal",""),
        })
    ventes.sort(key=lambda x: x.get("date",""), reverse=True)
    return _build_result(ventes, radius, "DVF — API etalab DGFiP (officiel)")

def _parse_cquest(items: list, lat: float, lon: float, radius: int) -> dict:
    ventes = []
    for item in items:
        lat2 = item.get("latitude") or item.get("lat")
        lon2 = item.get("longitude") or item.get("lon")
        try:
            if lat2 and lon2 and _haversine(lat, lon, lat2, lon2) > radius:
                continue
        except:
            pass
        prix = item.get("valeur_fonciere") or item.get("prix")
        surf = item.get("surface_reelle_bati") or item.get("surface")
        if not prix:
            continue
        try:
            prix_f = float(str(prix).replace(",",".").replace(" ",""))
            surf_f = float(str(surf).replace(",",".")) if surf else None
        except:
            continue
        ventes.append({
            "date": item.get("date_mutation",""),
            "type_bien": item.get("type_local","Bien immobilier"),
            "nature": item.get("nature_mutation","Vente"),
            "valeur_euros": int(prix_f),
            "surface_bati_m2": int(surf_f) if surf_f else None,
            "prix_m2": round(prix_f/surf_f) if surf_f and surf_f > 5 else None,
            "pieces": item.get("nombre_pieces_principales"),
            "code_postal": item.get("code_postal",""),
        })
    ventes.sort(key=lambda x: x.get("date",""), reverse=True)
    return _build_result(ventes, radius, "DVF — proxy cquest.org (DGFiP)")

def _build_result(ventes: list, radius: int, source: str) -> dict:
    pm2 = sorted([v["prix_m2"] for v in ventes if v.get("prix_m2") and v["prix_m2"] > 100])
    stats = {}
    if pm2:
        mid = len(pm2) // 2
        dates = [v.get("date","") for v in ventes if v.get("date")]
        stats = {
            "prix_m2_median": pm2[mid],
            "prix_m2_moyen": round(sum(pm2)/len(pm2)),
            "prix_m2_min": pm2[0],
            "prix_m2_max": pm2[-1],
            "nb_transactions": len(pm2),
            "periode": f"{min(dates)[:7]} - {max(dates)[:7]}" if dates else "",
        }
    return {
        "success": True,
        "disponible": True,
        "ventes_logements": ventes[:20],
        "stats": stats,
        "count": len(ventes),
        "radius_m": radius,
        "source": source,
    }
