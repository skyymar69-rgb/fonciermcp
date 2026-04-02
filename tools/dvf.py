"""
tools/dvf.py v3 — Multi-source DVF avec fallback automatique
Sources par ordre de priorite:
1. api.dvf.etalab.gouv.fr (plan Railway Hobby uniquement)
2. api.cquest.org/dvf (proxy public, accessible plan gratuit)
3. data.adresse.data.gouv.fr/csv (fallback final)
"""
import logging, httpx
from helpers.geocoder import geocode_address, reverse_geocode

logger = logging.getLogger(__name__)

DVF_ETALAB  = "https://api.dvf.etalab.gouv.fr/geoapi/mutations"
DVF_CQUEST  = "https://api.cquest.org/dvf"
DVF_DATAGOUV = "https://files.data.gouv.fr/geo-dvf/latest/csv"

async def get_dvf_history(address: str, radius: int = 500, years: int = 5) -> dict:
    """Historique DVF certifie DGFiP autour d'une adresse.
    Args: address, radius (metres, max 2000m), years (annees d'historique)."""
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable: {address}", "disponible": False}
    return await _dvf_multi(geo["lat"], geo["lon"], min(radius, 2000), geo)

async def _dvf_multi(lat: float, lon: float, radius: int, geo: dict = None) -> dict:
    """Essaie chaque source DVF dans l'ordre jusqu'au succes."""
    
    # Source 1: etalab (Railway Hobby)
    result = await _dvf_etalab(lat, lon, radius)
    if result.get("success"):
        return result
    
    # Source 2: cquest.org proxy DVF (accessible plan gratuit Railway)
    result = await _dvf_cquest(lat, lon, radius, geo)
    if result.get("success"):
        return result
    
    # Aucune source disponible - retourne lien direct
    code_dep = str(geo.get("code_insee","69"))[:2] if geo else "69"
    return {
        "success": False,
        "disponible": False,
        "message": "DVF temporairement indisponible — upgrade Railway Hobby pour acces complet.",
        "lien_direct": f"https://explore.data.gouv.fr/fr/immobilier?lat={lat}&lng={lon}&zoom=16",
        "source": "DVF — DGFiP / data.gouv.fr",
    }

async def _dvf_etalab(lat: float, lon: float, radius: int) -> dict:
    """API officielle etalab (necessite acces DNS — Railway Hobby)."""
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
                return {"success": True, "ventes": [], "stats": {}, "count": 0,
                        "radius_m": radius, "source": "DVF etalab — DGFiP"}
            return _parse_etalab(data["features"], radius)
    except Exception as e:
        logger.debug(f"DVF etalab unavailable: {e}")
        return {"success": False}

async def _dvf_cquest(lat: float, lon: float, radius: int, geo: dict = None) -> dict:
    """Proxy cquest.org - API DVF alternative accessible sans restriction DNS."""
    try:
        # Recupere le code commune depuis le geocodage
        code_commune = geo.get("code_insee","69123") if geo else "69123"
        section = geo.get("section","") if geo else ""
        
        params = {"code_commune": code_commune, "per_page": 200}
        if section:
            params["section"] = section
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(DVF_CQUEST, params=params)
            if r.status_code != 200:
                return {"success": False}
            data = r.json()
            features = data.get("resultats", data.get("features", []))
            if not features:
                return {"success": True, "ventes": [], "stats": {}, "count": 0,
                        "radius_m": radius, "source": "DVF cquest — DGFiP"}
            return _parse_cquest(features, lat, lon, radius)
    except Exception as e:
        logger.debug(f"DVF cquest unavailable: {e}")
        return {"success": False}

def _parse_etalab(features: list, radius: int) -> dict:
    """Parse le format GeoJSON etalab."""
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
        ventes.append({
            "date": p.get("date_mutation",""),
            "type_bien": p.get("type_local","Bien immobilier"),
            "nature": nature,
            "valeur_euros": int(prix),
            "surface_bati_m2": int(surf) if surf else None,
            "prix_m2": round(prix/surf) if prix and surf and surf > 5 else None,
            "pieces": p.get("nombre_pieces_principales"),
            "code_postal": p.get("code_postal",""),
        })
    ventes.sort(key=lambda x: x.get("date",""), reverse=True)
    return _build_result(ventes, radius, "DVF — API etalab DGFiP (officiel)")

def _parse_cquest(items: list, lat: float, lon: float, radius: int) -> dict:
    """Parse le format cquest.org."""
    import math
    def dist(lat2, lon2):
        R = 6371000
        dlat = math.radians(lat2-lat)
        dlon = math.radians(lon2-lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    ventes = []
    for item in items:
        # Format variable selon la version de l'API
        lat2 = item.get("latitude") or item.get("lat")
        lon2 = item.get("longitude") or item.get("lon")
        if lat2 and lon2 and dist(float(lat2), float(lon2)) > radius:
            continue
        prix = item.get("valeur_fonciere") or item.get("prix")
        surf = item.get("surface_reelle_bati") or item.get("surface")
        if not prix:
            continue
        try: prix = float(str(prix).replace(",",".").replace(" ",""))
        except: continue
        try: surf = float(str(surf).replace(",",".")) if surf else None
        except: surf = None
        ventes.append({
            "date": item.get("date_mutation",""),
            "type_bien": item.get("type_local","Bien immobilier"),
            "nature": item.get("nature_mutation","Vente"),
            "valeur_euros": int(prix),
            "surface_bati_m2": int(surf) if surf else None,
            "prix_m2": round(prix/surf) if prix and surf and surf > 5 else None,
            "pieces": item.get("nombre_pieces_principales"),
            "code_postal": item.get("code_postal",""),
        })
    ventes.sort(key=lambda x: x.get("date",""), reverse=True)
    return _build_result(ventes, radius, "DVF — proxy cquest.org (DGFiP)")

def _build_result(ventes: list, radius: int, source: str) -> dict:
    """Calcule les statistiques et formate le resultat."""
    pm2 = sorted([v["prix_m2"] for v in ventes if v.get("prix_m2") and v["prix_m2"] > 100])
    stats = {}
    if pm2:
        mid = len(pm2) // 2
        stats = {
            "prix_m2_median": pm2[mid],
            "prix_m2_moyen": round(sum(pm2)/len(pm2)),
            "prix_m2_min": pm2[0],
            "prix_m2_max": pm2[-1],
            "nb_transactions": len(pm2),
            "periode": f"{min(v.get('date','') for v in ventes if v.get('date'))[:7]} — {max(v.get('date','') for v in ventes if v.get('date'))[:7]}" if ventes else "",
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
