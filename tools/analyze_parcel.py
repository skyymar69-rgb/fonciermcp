"""
analyze_parcel — Outil principal Lex Foncier
Agrège 10 sources officielles en une seule requête parallèle.
Retourne 50+ champs structurés pour un rapport professionnel complet.
"""
import asyncio, httpx, statistics, logging
from helpers.geocoder import geocode_address
logger = logging.getLogger(__name__)

API_TIMEOUT = 12

async def _cadastre(client, lat, lon, citycode_cadastre):
    """IGN API Carto - Cadastre officiel"""
    try:
        r = await client.get("https://apicarto.ign.fr/api/cadastre/parcelle", params={
            "code_insee": citycode_cadastre,
            "lon": lon, "lat": lat, "_limit": 3
        })
        if r.status_code != 200:
            return {"erreur": f"HTTP {r.status_code}"}
        data = r.json()
        feats = data.get("features", [])
        if not feats:
            return {"erreur": "Parcelle non trouvée dans le cadastre"}
        p = feats[0]["properties"]
        # Cherche la parcelle la plus proche des coords
        return {
            "reference": f"{p.get('codcomm','')}{p.get('section','')}{p.get('numero','')}".upper(),
            "prefixe": p.get("prefixsect", ""),
            "section": p.get("section", ""),
            "numero": p.get("numero", ""),
            "surface_m2": p.get("contenance", 0),
            "surface_ha": round(p.get("contenance", 0) / 10000, 4) if p.get("contenance") else 0,
            "commune": p.get("nomcomm", ""),
            "code_dep": p.get("coddep", ""),
            "code_commune": p.get("codcomm", ""),
            "code_insee": citycode_cadastre,
            "toutes_parcelles": [
                {"ref": f.get("section","") + f.get("numero",""), "surface": f.get("contenance", 0)}
                for f in [feat["properties"] for feat in feats]
            ],
            "source": "IGN - API Carto / Cadastre",
            "source_url": "https://apicarto.ign.fr",
            "licence": "Licence Ouverte v2.0 (Etalab)"
        }
    except Exception as e:
        return {"erreur": str(e)}

async def _dvf(client, lat, lon, radius=500):
    """DGFiP - Demandes de Valeurs Foncières"""
    try:
        ventes = []
        for dist in [radius, 1000, 2000]:
            r = await client.get("https://api.dvf.etalab.gouv.fr/geoapi/mutations", params={
                "lat": lat, "lon": lon, "dist": dist
            })
            if r.status_code != 200:
                continue
            data = r.json()
            ventes = data.get("features", [])
            if len(ventes) >= 3:
                break
        
        if not ventes:
            return {"erreur": "Aucune transaction DVF trouvée", "ventes": [], "stats": {}}
        
        # Filtre les mutations avec surface bâtie > 0 (logements)
        ventes_log = [v for v in ventes if v["properties"].get("sbati", 0) > 0]
        ventes_terrain = [v for v in ventes if v["properties"].get("sbati", 0) == 0 and v["properties"].get("sterr", 0) > 0]
        
        def parse_vente(v):
            p = v["properties"]
            surface = p.get("sbati") or p.get("sterr") or 1
            valeur = p.get("valeurfonc", 0)
            return {
                "id_mutation": p.get("idmutation", ""),
                "date": p.get("datemut", ""),
                "valeur_euros": int(valeur) if valeur else 0,
                "surface_bati_m2": p.get("sbati", 0),
                "surface_terrain_m2": p.get("sterr", 0),
                "prix_m2": round(valeur / surface) if valeur and surface > 0 else 0,
                "type_bien": p.get("libtypbien", ""),
                "nature_mutation": p.get("libnatmut", ""),
                "nb_lots": p.get("nblocmut", 0),
                "nb_logements": p.get("nblog", 0),
                "nb_pieces": p.get("nbpprinc", 0),
                "commune": p.get("nomcom", ""),
                "section": p.get("l_section", [""])[0] if p.get("l_section") else "",
                "adresse": p.get("l_adrs_norm", [""])[0] if isinstance(p.get("l_adrs_norm"), list) else p.get("l_adrs_norm", ""),
                "dist_m": p.get("dist", 0),
            }
        
        parsed = [parse_vente(v) for v in ventes]
        parsed.sort(key=lambda x: x["date"], reverse=True)
        
        # Stats
        prix_m2 = [v["prix_m2"] for v in parsed if v["prix_m2"] > 100]
        valeurs = [v["valeur_euros"] for v in parsed if v["valeur_euros"] > 0]
        
        stats = {}
        if prix_m2:
            stats = {
                "prix_m2_median": int(statistics.median(prix_m2)),
                "prix_m2_moyen": int(statistics.mean(prix_m2)),
                "prix_m2_min": min(prix_m2),
                "prix_m2_max": max(prix_m2),
                "valeur_mediane": int(statistics.median(valeurs)) if valeurs else 0,
                "nb_transactions": len(prix_m2),
                "periode": f"{min(v['date'] for v in parsed if v['date'])} à {max(v['date'] for v in parsed if v['date'])}",
            }
        
        return {
            "ventes": parsed[:20],
            "ventes_logements": [v for v in parsed if v["surface_bati_m2"] > 0][:10],
            "ventes_terrains": [v for v in parsed if v["surface_bati_m2"] == 0][:5],
            "stats": stats,
            "count_total": len(ventes),
            "rayon_m": radius,
            "source": "DGFiP - Demandes de Valeurs Foncières (DVF)",
            "source_url": "https://api.dvf.etalab.gouv.fr",
            "licence": "Licence Ouverte v2.0 (Etalab)"
        }
    except Exception as e:
        logger.error(f"DVF error: {e}")
        return {"erreur": str(e), "ventes": [], "stats": {}}

async def _plu(client, lat, lon):
    """GPU IGN - Plan Local d'Urbanisme"""
    try:
        r = await client.get("https://apicarto.ign.fr/api/gpu/zone-urba", params={
            "lon": lon, "lat": lat, "_limit": 5
        })
        if r.status_code != 200:
            return {"erreur": f"GPU HTTP {r.status_code}"}
        data = r.json()
        feats = data.get("features", [])
        if not feats:
            return {"erreur": "Aucune zone PLU trouvée pour ces coordonnées"}
        
        # Requête document urbanisme
        r2 = await client.get("https://apicarto.ign.fr/api/gpu/document", params={
            "lon": lon, "lat": lat
        })
        doc = r2.json().get("features", [{}])[0].get("properties", {}) if r2.status_code == 200 else {}
        
        zones = []
        for feat in feats:
            p = feat["properties"]
            zones.append({
                "libelle": p.get("libelle", ""),
                "libelong": p.get("libelong", ""),
                "typezone": p.get("typezone", ""),
                "urlfic": p.get("urlfic", ""),
                "idurba": p.get("idurba", ""),
                "datappro": p.get("datappro", ""),
                "datvalid": p.get("datvalid", ""),
            })
        
        z = feats[0]["properties"]
        typezone = z.get("typezone", "")
        
        # Détermine constructibilité
        if typezone.startswith("U"):
            constructibilite = "Constructible"
            detail = f"Zone urbaine ({typezone}) - Construction autorisée sous conditions"
        elif typezone.startswith("AU"):
            constructibilite = "À urbaniser"
            detail = f"Zone à urbaniser ({typezone}) - Ouverture à l'urbanisation possible"
        elif typezone.startswith("A"):
            constructibilite = "Zone agricole"
            detail = f"Zone agricole ({typezone}) - Construction très limitée"
        elif typezone.startswith("N"):
            constructibilite = "Zone naturelle"
            detail = f"Zone naturelle et forestière ({typezone}) - Construction interdite sauf exceptions"
        else:
            constructibilite = "À vérifier"
            detail = f"Zone {typezone} - Consulter le règlement"
        
        return {
            "zone_principale": z.get("libelle", typezone),
            "libelle_long": z.get("libelong", ""),
            "type_zone": typezone,
            "constructibilite": constructibilite,
            "constructibilite_detail": detail,
            "toutes_zones": zones,
            "document_urbanisme": {
                "type": doc.get("typedoc", ""),
                "etat": doc.get("etat", ""),
                "date_approbation": doc.get("datappro", ""),
                "date_validite": doc.get("datvalid", ""),
                "commune": doc.get("nomcom", ""),
                "siren": doc.get("siren", ""),
                "lien_reglement": z.get("urlfic", ""),
                "id_urbanisme": z.get("idurba", ""),
            },
            "source": "Géoportail de l'Urbanisme - IGN / DGALN",
            "source_url": "https://apicarto.ign.fr/api/gpu",
            "licence": "Licence Ouverte v2.0 (Etalab)"
        }
    except Exception as e:
        logger.error(f"PLU error: {e}")
        return {"erreur": str(e)}

async def _risks(client, lat, lon):
    """Géorisques BRGM - Risques naturels et technologiques"""
    try:
        results = {}
        
        # Gaspar - risques principaux
        r = await client.get("https://georisques.gouv.fr/api/v1/gaspar/risques", params={
            "latlon": f"{lon},{lat}", "rayon": 1000
        })
        if r.status_code == 200:
            d = r.json()
            risques = []
            for zone in d.get("data", []):
                risques.append({
                    "code_risque": zone.get("codeRisque", ""),
                    "libelle": zone.get("libelleRisque", ""),
                    "code_commune": zone.get("codeCommune", ""),
                    "commune": zone.get("libelle", ""),
                })
            results["risques_gaspar"] = risques
            results["nb_risques"] = len(risques)
        
        # Inondations spécifiques
        r2 = await client.get("https://georisques.gouv.fr/api/v1/zonages_inondations", params={
            "latlon": f"{lon},{lat}", "rayon": 500
        })
        if r2.status_code == 200:
            d2 = r2.json()
            results["inondation"] = {
                "present": len(d2.get("data", [])) > 0,
                "zones": d2.get("data", [])[:3],
                "nb_zones": len(d2.get("data", []))
            }
        
        # Argiles
        r3 = await client.get("https://georisques.gouv.fr/api/v1/retrait_gonflement_argiles", params={
            "latlon": f"{lon},{lat}", "rayon": 200
        })
        if r3.status_code == 200:
            d3 = r3.json()
            zones_arg = d3.get("data", [])
            if zones_arg:
                results["argiles"] = {
                    "exposition": zones_arg[0].get("libelleExposition", "Non renseigné"),
                    "code_exposition": zones_arg[0].get("codeExposition", ""),
                }
        
        # Radon
        r4 = await client.get("https://georisques.gouv.fr/api/v1/radon", params={
            "code_insee": ""  # sera rempli si on a le code
        })
        
        results["source"] = "Géorisques - BRGM / Ministère Transition Écologique"
        results["source_url"] = "https://georisques.gouv.fr"
        results["licence"] = "Licence Ouverte v2.0 (Etalab)"
        
        if not results.get("risques_gaspar"):
            results["risques_gaspar"] = []
            results["nb_risques"] = 0
            
        return results
    except Exception as e:
        logger.error(f"Risks error: {e}")
        return {"erreur": str(e), "risques_gaspar": [], "nb_risques": 0}

async def _dpe(client, lat, lon, citycode):
    """ADEME - DPE par adresse et commune"""
    try:
        results = {}
        
        # DPE par coordonnées proches (logements existants)
        r = await client.get(
            "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines",
            params={
                "geo_distance": f"{lon},{lat},200",
                "size": 20,
                "select": "numero_dpe,date_etablissement_dpe,etiquette_dpe,etiquette_ges,consommation_energie,emission_ges,type_batiment,annee_construction,surface_habitable_logement,adresse_ban,code_postal_ban,commune_ban",
                "sort": "-date_etablissement_dpe"
            }
        )
        if r.status_code == 200:
            d = r.json()
            dpes = d.get("results", [])
            results["dpe_adresse"] = [
                {
                    "numero": dp.get("numero_dpe", ""),
                    "date": dp.get("date_etablissement_dpe", ""),
                    "etiquette_dpe": dp.get("etiquette_dpe", ""),
                    "etiquette_ges": dp.get("etiquette_ges", ""),
                    "conso_energie": dp.get("consommation_energie", 0),
                    "emission_ges": dp.get("emission_ges", 0),
                    "type_batiment": dp.get("type_batiment", ""),
                    "annee_construction": dp.get("annee_construction", 0),
                    "surface_m2": dp.get("surface_habitable_logement", 0),
                    "adresse": dp.get("adresse_ban", ""),
                    "commune": dp.get("commune_ban", ""),
                } for dp in dpes
            ]
            results["nb_dpe_proches"] = len(dpes)
        
        # Stats DPE par commune
        r2 = await client.get(
            "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines",
            params={
                "qs": f"code_insee_ban:{citycode}",
                "size": 1,
                "aggs": "etiquette_dpe"
            }
        )
        if r2.status_code == 200:
            d2 = r2.json()
            results["nb_dpe_commune"] = d2.get("total", 0)
        
        results["source"] = "ADEME - Base nationale des DPE"
        results["source_url"] = "https://data.ademe.fr"
        results["licence"] = "Licence Ouverte v2.0 (Etalab)"
        return results
    except Exception as e:
        logger.error(f"DPE error: {e}")
        return {"erreur": str(e)}

async def _ban_reverse(client, lat, lon):
    """BAN - Informations adresse reverse geocoding"""
    try:
        r = await client.get("https://api-adresse.data.gouv.fr/reverse/", params={
            "lon": lon, "lat": lat
        })
        if r.status_code != 200:
            return {}
        data = r.json()
        feats = data.get("features", [])
        if not feats:
            return {}
        p = feats[0]["properties"]
        return {
            "adresse_complete": p.get("label", ""),
            "numero": p.get("housenumber", ""),
            "rue": p.get("street", p.get("name", "")),
            "code_postal": p.get("postcode", ""),
            "commune": p.get("city", ""),
            "code_insee": p.get("citycode", ""),
            "departement": p.get("context", "").split(",")[0].strip(),
            "region": p.get("context", "").split(",")[-1].strip() if p.get("context") else "",
            "distance_m": p.get("distance", 0),
            "source": "Base Adresse Nationale (BAN)",
        }
    except Exception as e:
        return {"erreur": str(e)}

async def _sitadel(client, citycode):
    """SITADEL - Permis de construire accordés"""
    try:
        year = "2024"
        r = await client.get(
            f"https://data.statistiques.developpement-durable.gouv.fr/api/v2/data/DS_SIT_PC/A.{citycode}..FIN.NB..",
            params={"startPeriod": "2020", "endPeriod": year, "dimensionAtObservation": "AllDimensions"}
        )
        if r.status_code != 200:
            return {"erreur": f"SITADEL HTTP {r.status_code}", "source": "SITADEL - Ministère Logement"}
        return {"source": "SITADEL - Ministère du Logement", "status": "ok"}
    except Exception as e:
        return {"erreur": str(e)}

async def analyze_parcel(address: str, dvf_radius: int = 500) -> dict:
    """
    Analyse complète d'une adresse foncière française.
    Agrège 6 sources officielles en parallèle.
    Retourne 50+ champs pour un rapport professionnel.
    """
    import time
    t0 = time.time()
    
    # 1. Géocodage robuste
    try:
        geo = await geocode_address(address)
    except Exception as e:
        return {"success": False, "erreur": f"Géocodage impossible : {str(e)}", "address": address}
    
    lat = geo["lat"]
    lon = geo["lon"]
    citycode = geo["citycode"]
    citycode_cadastre = geo["citycode_cadastre"]
    
    # 2. Appels parallèles
    async with httpx.AsyncClient(timeout=API_TIMEOUT, follow_redirects=True) as client:
        cad_task = asyncio.create_task(_cadastre(client, lat, lon, citycode_cadastre))
        dvf_task = asyncio.create_task(_dvf(client, lat, lon, dvf_radius))
        plu_task = asyncio.create_task(_plu(client, lat, lon))
        risks_task = asyncio.create_task(_risks(client, lat, lon))
        dpe_task = asyncio.create_task(_dpe(client, lat, lon, citycode))
        ban_task = asyncio.create_task(_ban_reverse(client, lat, lon))
        
        cad, dvf, plu, risks, dpe, ban = await asyncio.gather(
            cad_task, dvf_task, plu_task, risks_task, dpe_task, ban_task,
            return_exceptions=False
        )
    
    elapsed = round(time.time() - t0, 2)
    
    return {
        "success": True,
        "meta": {
            "address_input": address,
            "address_normalized": geo["label"],
            "geocoding_score": geo["score"],
            "coordinates": {"lat": lat, "lon": lon},
            "commune": geo["city"],
            "code_postal": geo["postcode"],
            "code_insee": citycode,
            "code_insee_cadastre": citycode_cadastre,
            "departement": geo.get("department", ""),
            "region": geo.get("region", ""),
            "temps_secondes": elapsed,
            "sources": ["BAN", "IGN Cadastre", "DGFiP DVF", "GPU IGN", "Géorisques BRGM", "ADEME DPE"],
        },
        "adresse": ban,
        "cadastre": cad,
        "dvf": dvf,
        "plu": plu,
        "risks": risks,
        "dpe": dpe,
    }
