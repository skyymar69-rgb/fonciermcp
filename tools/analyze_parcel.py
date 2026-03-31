import asyncio, httpx, statistics, logging
from helpers.geocoder import geocode_address
logger = logging.getLogger(__name__)
T = 15

DEPS = {
    "69381":"69","69382":"69","69383":"69","69384":"69","69385":"69",
    "69386":"69","69387":"69","69388":"69","69389":"69",
}

async def _cad(c, lat, lon, insee):
    try:
        r = await c.get("https://apicarto.ign.fr/api/cadastre/parcelle",
            params={"lon":lon,"lat":lat,"code_insee":insee,"_limit":5})
        if r.status_code != 200: return {"erreur":"IGN "+str(r.status_code)}
        feats = r.json().get("features",[])
        if not feats: return {"erreur":"Aucune parcelle"}
        p = feats[0]["properties"]
        return {
            "reference":(p.get("codecom","")+p.get("section","").strip()+p.get("numero","")).upper(),
            "section":p.get("section","").strip(), "numero":p.get("numero",""),
            "surface_m2":p.get("contenance",0),
            "surface_ha":round(p.get("contenance",0)/10000,4) if p.get("contenance") else 0,
            "commune":p.get("nomcom",""), "code_dep":p.get("coddep",""),
            "code_insee":insee,
            "toutes_parcelles":[{"ref":f["properties"].get("section","").strip()+f["properties"].get("numero",""),
                "surf":f["properties"].get("contenance",0)} for f in feats],
            "source":"IGN — API Carto / Cadastre","licence":"Licence Ouverte Etalab v2.0"
        }
    except Exception as e: return {"erreur":str(e)}

async def _bat(c, lat, lon):
    try:
        bbox = f"{lat-0.002},{lon-0.003},{lat+0.002},{lon+0.003}"
        r = await c.get("https://data.geopf.fr/wfs/ows", params={
            "SERVICE":"WFS","VERSION":"2.0.0","REQUEST":"GetFeature",
            "TYPENAMES":"BDTOPO_V3:batiment","CRS":"EPSG:4326","BBOX":bbox,
            "outputformat":"application/json","count":10,
            "PROPERTYNAME":"usage_1,usage_2,hauteur,nombre_de_logements,nombre_d_etages,materiaux_de_la_toiture,etat_de_l_objet"
        })
        if r.status_code != 200: return {"erreur":"BDTOPO "+str(r.status_code)}
        feats = r.json().get("features",[])
        bats = []
        for f in feats:
            p = f.get("properties",{})
            bats.append({"usage":p.get("usage_1",""),"usage2":p.get("usage_2",""),
                "nb_logements":p.get("nombre_de_logements",0),
                "nb_etages":p.get("nombre_d_etages",0),
                "hauteur_m":p.get("hauteur",0),
                "toiture":p.get("materiaux_de_la_toiture",""),
                "etat":p.get("etat_de_l_objet","")})
        return {"batiments":bats,"nb_batiments":len(feats),
            "nb_avec_logements":len([b for b in bats if b["nb_logements"]]),
            "source":"IGN — BDTOPO v3","licence":"Licence Ouverte Etalab v2.0"}
    except Exception as e: return {"erreur":str(e)}

async def _dvf(c, lat, lon, radius=500):
    try:
        for dist in [radius, min(radius*2,2000)][:2]:
            try:
                r = await c.get(
                    f"https://api.dvf.etalab.gouv.fr/geoapi/mutations?lat={lat}&lon={lon}&dist={dist}",
                    timeout=5.0)
                if r.status_code == 200:
                    ventes = r.json().get("features",[])
                    if ventes: return _parse_dvf(ventes, dist)
            except Exception: break
        return {"disponible":False,"ventes":[],"stats":{},
            "lien_direct":f"https://dvf.etalab.gouv.fr/?lat={lat}&lon={lon}&zoom=17",
            "message":"DVF disponible sur dvf.etalab.gouv.fr",
            "source":"DGFiP — DVF","licence":"Licence Ouverte Etalab v2.0"}
    except Exception as e: return {"erreur":str(e),"ventes":[],"stats":{}}

def _parse_dvf(ventes, radius):
    parsed = []
    for v in ventes:
        p = v["properties"]
        surf = p.get("sbati") or p.get("sterr") or 1
        val = p.get("valeurfonc",0) or 0
        parsed.append({"date":p.get("datemut",""),"valeur_euros":int(val),
            "surface_bati_m2":p.get("sbati",0) or 0,"surface_terrain_m2":p.get("sterr",0) or 0,
            "prix_m2":round(val/surf) if val and surf>0 else 0,
            "type_bien":p.get("libtypbien",""),"nature_mutation":p.get("libnatmut",""),
            "nb_lots":p.get("nblocmut",0),"commune":p.get("nomcom",""),
            "adresse":p.get("l_adrs_norm",[""])[0] if isinstance(p.get("l_adrs_norm"),list) else p.get("l_adrs_norm","")})
    parsed.sort(key=lambda x:x["date"],reverse=True)
    pm2=[v["prix_m2"] for v in parsed if v["prix_m2"]>100]
    vals=[v["valeur_euros"] for v in parsed if v["valeur_euros"]>0]
    stats={}
    if pm2:
        stats={"prix_m2_median":int(statistics.median(pm2)),
            "prix_m2_moyen":int(statistics.mean(pm2)),
            "prix_m2_min":min(pm2),"prix_m2_max":max(pm2),
            "valeur_mediane":int(statistics.median(vals)) if vals else 0,
            "nb_transactions":len(pm2),
            "periode":(min(v["date"] for v in parsed if v["date"])[:7]+" à "+max(v["date"] for v in parsed if v["date"])[:7])}
    return {"disponible":True,"ventes":parsed[:20],
        "ventes_logements":[v for v in parsed if v["surface_bati_m2"]>0][:12],
        "stats":stats,"count_total":len(ventes),"rayon_m":radius,
        "source":"DGFiP — DVF","licence":"Licence Ouverte Etalab v2.0"}

async def _plu(c, lat, lon):
    try:
        r = await c.get("https://apicarto.ign.fr/api/gpu/zone-urba",params={"lon":lon,"lat":lat,"_limit":5})
        if r.status_code != 200: return {"erreur":"GPU "+str(r.status_code)}
        feats = r.json().get("features",[])
        if not feats: return {"erreur":"Aucune zone PLU"}
        r2 = await c.get("https://apicarto.ign.fr/api/gpu/document",params={"lon":lon,"lat":lat})
        doc = r2.json().get("features",[{}])[0].get("properties",{}) if r2.status_code==200 else {}
        z = feats[0]["properties"]
        tz = z.get("typezone","")
        if tz.startswith("U"): ct,dt = "Constructible","Zone urbaine "+tz+" — Construction autorisée"
        elif tz.startswith("AU"): ct,dt = "À urbaniser","Zone AU — Ouverture à l'urbanisation possible"
        elif tz.startswith("A"): ct,dt = "Zone agricole","Zone A — Construction très limitée"
        elif tz.startswith("N"): ct,dt = "Zone naturelle","Zone N — Construction interdite sauf exceptions"
        else: ct,dt = "À vérifier","Zone "+tz+" — Consulter le règlement"
        return {"zone_principale":z.get("libelle",tz),"libelle_long":z.get("libelong",""),
            "type_zone":tz,"constructibilite":ct,"constructibilite_detail":dt,
            "toutes_zones":[{"libelle":f["properties"].get("libelle",""),"type":f["properties"].get("typezone",""),
                "lien":f["properties"].get("urlfic","")} for f in feats],
            "document_urbanisme":{"type":doc.get("typedoc",""),"etat":doc.get("etat",""),
                "date_approbation":doc.get("datappro",""),"commune":doc.get("nomcom",""),
                "lien_reglement":z.get("urlfic",""),"id_urbanisme":z.get("idurba","")},
            "source":"Géoportail de l'Urbanisme — IGN","licence":"Licence Ouverte Etalab v2.0"}
    except Exception as e: return {"erreur":str(e)}

async def _risks(c, lat, lon, code_insee=""):
    try:
        res = {"risques_gaspar":[],"nb_risques":0}
        r = await c.get("https://georisques.gouv.fr/api/v1/gaspar/risques",
            params={"latlon":f"{lon},{lat}","rayon":1000})
        if r.status_code==200:
            risques=[{"code_risque":z.get("codeRisque",""),"libelle":z.get("libelleRisque",""),
                "commune":z.get("libelle","")} for z in r.json().get("data",[])]
            res["risques_gaspar"]=risques; res["nb_risques"]=len(risques)
        r2 = await c.get("https://georisques.gouv.fr/api/v1/zonages_inondations",
            params={"latlon":f"{lon},{lat}","rayon":500})
        if r2.status_code==200:
            zones=r2.json().get("data",[])
            res["inondation"]={"present":len(zones)>0,"nb_zones":len(zones),
                "zones":[{"libelle":z.get("libelle",""),"type":z.get("typeAlea","")} for z in zones[:3]]}
        r3 = await c.get("https://georisques.gouv.fr/api/v1/retrait_gonflement_argiles",
            params={"latlon":f"{lon},{lat}","rayon":200})
        if r3.status_code==200:
            za=r3.json().get("data",[])
            if za: res["argiles"]={"exposition":za[0].get("libelleExposition","Non renseigné"),"code":za[0].get("codeExposition","")}
        if code_insee:
            r4 = await c.get("https://georisques.gouv.fr/api/v1/radon",params={"code_insee":code_insee})
            if r4.status_code==200:
                rad=r4.json().get("data",[])
                if rad: res["radon"]={"classe":rad[0].get("classeRadon",""),"libelle":rad[0].get("libelleClasse","")}
        res["source"]="Géorisques — BRGM"; res["licence"]="Licence Ouverte Etalab v2.0"
        return res
    except Exception as e: return {"erreur":str(e),"risques_gaspar":[],"nb_risques":0}

async def _dpe(c, lat, lon, code_dep):
    try:
        dep = str(code_dep).zfill(2) if code_dep else "69"
        r = await c.get(
            f"https://data.ademe.fr/data-fair/api/v1/datasets/dpe-{dep}/lines",
            params={"geo_distance":f"{lon},{lat},300","size":15,
                "select":"numero_dpe,date_etablissement_dpe,classe_consommation_energie,classe_estimation_ges,consommation_energie,estimation_ges,surface_habitable,annee_construction,commune,code_postal,numero_rue,nom_rue,tr002_type_batiment_id",
                "sort":"-date_etablissement_dpe"})
        if r.status_code==200:
            d=r.json(); dpes=d.get("results",[])
            TYPES={1:"Maison",2:"Appartement",3:"Immeuble",4:"Local commercial"}
            return {"dpe_adresse":[{"numero":dp.get("numero_dpe",""),"date":dp.get("date_etablissement_dpe",""),
                "etiquette_dpe":dp.get("classe_consommation_energie",""),
                "etiquette_ges":dp.get("classe_estimation_ges",""),
                "conso_energie_kwh":dp.get("consommation_energie",0),
                "emission_ges":dp.get("estimation_ges",0),
                "type_batiment":TYPES.get(dp.get("tr002_type_batiment_id"),str(dp.get("tr002_type_batiment_id",""))),
                "annee_construction":dp.get("annee_construction",0),
                "surface_m2":dp.get("surface_habitable",0),
                "adresse":str(dp.get("numero_rue",""))+" "+str(dp.get("nom_rue","")),
                "commune":dp.get("commune",""),"code_postal":dp.get("code_postal",""),
                "distance_m":round(dp.get("_geo_distance",0))} for dp in dpes],
                "nb_dpe_proches":len(dpes),"total_commune":d.get("total",0),
                "source":"ADEME — DPE dep "+dep,"licence":"Licence Ouverte Etalab v2.0"}
        return {"erreur":"DPE HTTP "+str(r.status_code),"dpe_adresse":[]}
    except Exception as e: return {"erreur":str(e),"dpe_adresse":[]}

async def _ban_rev(c, lat, lon):
    try:
        r = await c.get("https://api-adresse.data.gouv.fr/reverse/",params={"lon":lon,"lat":lat})
        if r.status_code!=200 or not r.text.strip(): return {}
        feats=r.json().get("features",[])
        if not feats: return {}
        p=feats[0]["properties"]; ctx=p.get("context","")
        parts=[x.strip() for x in ctx.split(",")]
        return {"adresse_complete":p.get("label",""),"numero":p.get("housenumber",""),
            "rue":p.get("street",p.get("name","")),"code_postal":p.get("postcode",""),
            "commune":p.get("city",""),"code_insee":p.get("citycode",""),
            "departement":parts[0] if parts else "","region":parts[-1] if len(parts)>1 else ""}
    except Exception as e: return {"erreur":str(e)}

async def _commune(c, insee):
    try:
        r = await c.get(f"https://geo.api.gouv.fr/communes/{insee}",
            params={"fields":"nom,codeDepartement,codeRegion,population,surface,codesPostaux"})
        if r.status_code!=200: return {}
        d=r.json()
        return {"nom":d.get("nom",""),"departement":d.get("codeDepartement",""),
            "region":d.get("codeRegion",""),"population":d.get("population",0),
            "surface_km2":round(d.get("surface",0)/100,1) if d.get("surface") else 0,
            "codes_postaux":d.get("codesPostaux",[])}
    except Exception: return {}

async def analyze_parcel(address: str, dvf_radius: int = 500) -> dict:
    """Analyse foncière complète — 8 sources officielles."""
    import time; t0=time.time()
    try: geo = await geocode_address(address)
    except Exception as e: return {"success":False,"erreur":"Géocodage impossible: "+str(e),"address":address}
    lat,lon=geo["lat"],geo["lon"]
    citycode=geo["citycode"]; cc=geo["citycode_cadastre"]
    ctx=geo.get("department",""); dep=ctx.split(",")[0].strip()[:2] if ctx else cc[:2]
    async with httpx.AsyncClient(timeout=T,follow_redirects=True,
        headers={"User-Agent":"LexFoncier/2.0"}) as client:
        cad,bat,dvf,plu,risks,dpe,ban,com = await asyncio.gather(
            _cad(client,lat,lon,cc), _bat(client,lat,lon),
            _dvf(client,lat,lon,dvf_radius), _plu(client,lat,lon),
            _risks(client,lat,lon,cc), _dpe(client,lat,lon,dep),
            _ban_rev(client,lat,lon), _commune(client,cc))
    return {"success":True,
        "meta":{"address_input":address,"address_normalized":geo["label"],
            "geocoding_score":geo["score"],"coordinates":{"lat":lat,"lon":lon},
            "commune":geo["city"],"code_postal":geo["postcode"],
            "code_insee":citycode,"code_insee_cadastre":cc,
            "departement":geo.get("department",""),"region":geo.get("region",""),
            "temps_secondes":round(time.time()-t0,2),
            "sources":["BAN","IGN Cadastre","IGN Bâtiments","DVF DGFiP","GPU PLU","Géorisques","DPE ADEME","INSEE Géo"]},
        "adresse":ban,"cadastre":cad,"batiments":bat,
        "dvf":dvf,"plu":plu,"risks":risks,"dpe":dpe,"commune":com}
