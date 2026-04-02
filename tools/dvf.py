"""
tools/dvf.py v4 — DVF multi-source avec CSV data.gouv.fr comme fallback
Sources par ordre de priorite:
1. api.dvf.etalab.gouv.fr — officiel (Railway Hobby, DNS debloque)
2. files.data.gouv.fr CSV par commune — accessible plan gratuit Railway
"""
import logging, math, io, csv, gzip, httpx
from helpers.geocoder import geocode_address

logger = logging.getLogger(__name__)

DVF_ETALAB   = "https://api.dvf.etalab.gouv.fr/geoapi/mutations"
DVF_CSV_BASE = "https://files.data.gouv.fr/geo-dvf/latest/csv"

async def get_dvf_history(address: str, radius: int = 500, years: int = 5) -> dict:
    """Historique DVF certifie DGFiP autour d'une adresse.
    Args: address, radius (metres, max 2000m), years."""
    geo = await geocode_address(address)
    if not geo:
        return {"error": f"Adresse introuvable: {address}", "disponible": False, "success": False}
    return await _dvf_multi(geo["lat"], geo["lon"], min(radius, 2000), geo)

async def _dvf_multi(lat: float, lon: float, radius: int, geo: dict) -> dict:
    """Essaie chaque source DVF dans l'ordre."""
    # Source 1: API etalab (Railway Hobby uniquement)
    result = await _dvf_etalab(lat, lon, radius)
    if result.get("success"):
        return result
    # Source 2: CSV data.gouv.fr par commune (fonctionne plan gratuit)
    result = await _dvf_csv(lat, lon, radius, geo)
    if result.get("success"):
        return result
    # Fallback final
    return {
        "success": False,
        "disponible": False,
        "message": "DVF temporairement indisponible.",
        "lien_direct": f"https://explore.data.gouv.fr/fr/immobilier?lat={lat}&lng={lon}&zoom=16",
        "source": "DVF — DGFiP / data.gouv.fr",
    }

async def _dvf_etalab(lat: float, lon: float, radius: int) -> dict:
    """API officielle etalab."""
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
        logger.debug(f"DVF etalab indisponible: {type(e).__name__}")
        return {"success": False}

async def _dvf_csv(lat: float, lon: float, radius: int, geo: dict) -> dict:
    """Telechargement CSV DVF par commune depuis data.gouv.fr.
    Accessible depuis Railway plan gratuit via HTTPS direct."""
    code_insee = geo.get("code_insee", "")
    if not code_insee or len(code_insee) < 5:
        return {"success": False}
    code_dep = code_insee[:2]
    if code_dep == "97":
        code_dep = code_insee[:3]
    url = f"{DVF_CSV_BASE}/{code_dep}/communes/{code_insee}.csv.gz"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.debug(f"DVF CSV {url} -> {r.status_code}")
                return {"success": False}
            # Decompresse gzip
            content = gzip.decompress(r.content).decode("utf-8", errors="replace")
            rows = list(csv.DictReader(io.StringIO(content)))
            if not rows:
                return {"success": True, "ventes_logements": [], "stats": {}, "count": 0,
                        "radius_m": radius, "source": "DVF CSV — DGFiP data.gouv.fr"}
            return _parse_csv_rows(rows, lat, lon, radius)
    except Exception as e:
        logger.debug(f"DVF CSV indisponible: {type(e).__name__}: {e}")
        return {"success": False}

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    try:
        dlat = math.radians(float(lat2)-float(lat1))
        dlon = math.radians(float(lon2)-float(lon1))
        a = math.sin(dlat/2)**2+math.cos(math.radians(float(lat1)))*math.cos(math.radians(float(lat2)))*math.sin(dlon/2)**2
        return R*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
    except:
        return 9999

def _parse_csv_rows(rows: list, lat: float, lon: float, radius: int) -> dict:
    """Parse les lignes CSV DVF data.gouv.fr et filtre par rayon."""
    ventes = []
    seen = set()  # deduplique les mutations
    for row in rows:
        # Filtre par rayon si coordonnees disponibles
        lat2 = row.get("latitude","")
        lon2 = row.get("longitude","")
        if lat2 and lon2:
            try:
                if _haversine(lat, lon, lat2, lon2) > radius:
                    continue
            except:
                pass
        # Deduplique par id_mutation
        mut_id = row.get("id_mutation","")
        if mut_id and mut_id in seen:
            continue
        if mut_id:
            seen.add(mut_id)
        # Parse les valeurs
        prix_str = row.get("valeur_fonciere","").replace(",",".")
        surf_str = row.get("surface_reelle_bati","").replace(",",".")
        nature   = row.get("nature_mutation","Vente")
        type_loc = row.get("type_local","")
        if not prix_str or nature not in ("Vente","Adjudication","Expropriation"):
            continue
        # Filtre sur les biens a prix realiste (evite les terrains seuls)
        try:
            prix = float(prix_str)
            surf = float(surf_str) if surf_str else None
        except:
            continue
        if prix < 10000 or prix > 50000000:
            continue
        prix_m2 = round(prix/surf) if surf and surf > 5 else None
        if prix_m2 and (prix_m2 < 100 or prix_m2 > 50000):
            prix_m2 = None
        ventes.append({
            "date": row.get("date_mutation",""),
            "type_bien": type_loc or "Bien immobilier",
            "nature": nature,
            "valeur_euros": int(prix),
            "surface_bati_m2": int(surf) if surf else None,
            "prix_m2": prix_m2,
            "pieces": row.get("nombre_pieces_principales",""),
            "code_postal": row.get("code_postal",""),
        })
    ventes.sort(key=lambda x: x.get("date",""), reverse=True)
    return _build_result(ventes, radius, "DVF CSV — DGFiP / data.gouv.fr (certifie)")

def _parse_etalab(features: list, radius: int) -> dict:
    ventes = []
    for f in features:
        p = f.get("properties", {})
        prix  = p.get("valeur_fonciere")
        surf  = p.get("surface_reelle_bati")
        nature = p.get("nature_mutation","Vente")
        if not prix or nature not in ("Vente","Adjudication","Expropriation"):
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

def _build_result(ventes: list, radius: int, source: str) -> dict:
    pm2 = sorted([v["prix_m2"] for v in ventes if v.get("prix_m2") and v["prix_m2"] > 100])
    stats = {}
    if pm2:
        mid = len(pm2)//2
        dates = [v.get("date","") for v in ventes if v.get("date")]
        stats = {
            "prix_m2_median": pm2[mid],
            "prix_m2_moyen":  round(sum(pm2)/len(pm2)),
            "prix_m2_min":    pm2[0],
            "prix_m2_max":    pm2[-1],
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
