import logging, os, time
import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from auth import verify, create as create_key, list_keys
from webhook import handle_webhook, create_checkout_session
from tools.analyze_parcel import analyze_parcel
from tools.dvf import get_dvf_history
from tools.plu import check_plu_rules
from tools.risks import get_erp_risks
from tools.dpe import get_dpe
from rapport import generate_rapport

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
logger = logging.getLogger(__name__)

mcp = FastMCP(name="LexFoncier", instructions="Tu es Lex Foncier, assistant analyse fonciere France.")
mcp.tool()(analyze_parcel)
mcp.tool()(get_dvf_history)
mcp.tool()(check_plu_rules)
mcp.tool()(get_erp_risks)
mcp.tool()(get_dpe)

app = FastAPI(title="Lex Foncier", docs_url=None, redoc_url=None)
app.mount("/mcp", mcp.streamable_http_app())

_ip_usage: dict = {}
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "2"))
APP_URL = os.getenv("APP_URL", "https://app-production-71c1.up.railway.app")

def _get_ip(request: Request) -> str:
    return request.headers.get("X-Forwarded-For","").split(",")[0].strip() or request.client.host or "unknown"

def _check_free_quota(ip: str) -> tuple[bool, int]:
    now = time.time()
    day_key = int(now // 86400)
    entry = _ip_usage.get(ip, {"day": 0, "count": 0})
    if entry["day"] != day_key:
        entry = {"day": day_key, "count": 0}
    count = entry["count"]
    entry["count"] += 1
    _ip_usage[ip] = entry
    if len(_ip_usage) > 5000:
        oldest = sorted(_ip_usage.items(), key=lambda x: x[1]["day"])[:1000]
        for k, _ in oldest: del _ip_usage[k]
    return count < FREE_LIMIT, count

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    public = ["/health","/webhook/stripe","/api/demo","/api/key/create",
              "/api/checkout","/merci","/","/rapport","/diagnostic",
              "/rapport-demo","/tarifs.html","/fonctionnalites.html",
              "/api.html","/notaires.html","/agents.html","/promoteurs.html",
              "/mentions-legales.html","/cgu.html"]
    if not path.startswith("/mcp") or any(path.startswith(e) for e in public):
        return await call_next(request)
    key = request.headers.get("X-API-Key","")
    if not key:
        return JSONResponse({"error":"X-API-Key manquant"}, status_code=401)
    client = await verify(key)
    if not client:
        return JSONResponse({"error":"Cle invalide"}, status_code=403)
    request.state.client = client
    return await call_next(request)

@app.get("/health")
async def health():
    return {"status":"ok","service":"LexFoncier","version":"3.0"}

@app.get("/rapport-demo")
async def rapport_demo():
    f = "static/rapport-demo.html"
    if os.path.exists(f): return HTMLResponse(open(f).read())
    return HTMLResponse("<h1>Demo non disponible</h1>", status_code=404)

@app.get("/diagnostic")
async def diagnostic():
    import httpx, time as t
    urls = [
        ("BAN", "https://api-adresse.data.gouv.fr/search/?q=Lyon&limit=1"),
        ("IGN_carto", "https://apicarto.ign.fr/api/cadastre/commune?code_insee=69123&_limit=1"),
        ("DVF_etalab", "https://api.dvf.etalab.gouv.fr/geoapi/mutations?lat=45.76&lon=4.83&dist=100"),
        ("GPU_IGN", "https://apicarto.ign.fr/api/gpu/zone-urba?lon=4.83&lat=45.76"),
        ("Georisques", "https://georisques.gouv.fr/api/v1/gaspar/risques?latlon=4.83,45.76&rayon=500"),
        ("ADEME_dep69", "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-69/lines?size=1"),
        ("INSEE_geo", "https://geo.api.gouv.fr/communes?code=69123"),
        ("BDTOPO", "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities"),
    ]
    results = {}
    async with httpx.AsyncClient(timeout=8) as client:
        for name, url in urls:
            t0 = t.time()
            try:
                r = await client.get(url)
                results[name] = {"status":r.status_code,"ms":round((t.time()-t0)*1000),"ok":r.status_code<400}
            except Exception as e:
                results[name] = {"status":0,"error":str(e)[:60],"ok":False}
    return results

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_webhook(request)

@app.get("/api/checkout/{plan}")
async def checkout_get(plan: str, request: Request):
    if plan not in ["starter","pro","cabinet"]:
        raise HTTPException(400, "Plan invalide")
    email = request.query_params.get("email","")
    session = await create_checkout_session(plan, email)
    if "error" in session:
        return RedirectResponse(url="/tarifs.html?msg=stripe_bientot", status_code=302)
    return RedirectResponse(url=session["url"], status_code=302)

@app.get("/merci")
async def merci():
    html = open("static/merci.html").read() if os.path.exists("static/merci.html") else """
    <!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Merci — Lex Foncier</title><link rel="stylesheet" href="assets/style.css"></head><body>
    <nav class="site-nav"><div class="container"><div class="nav-inner">
    <a href="/" class="nav-logo">Lex <span>Foncier</span></a></div></div></nav>
    <section style="min-height:70vh;display:flex;align-items:center;justify-content:center;text-align:center">
    <div style="max-width:500px;padding:2rem">
    <div style="font-size:3rem;margin-bottom:1.5rem">&#x2705;</div>
    <h1 style="margin-bottom:1rem">Abonnement active !</h1>
    <p style="color:var(--c-muted);margin-bottom:2rem;line-height:1.7">
    Votre cle API Lex Foncier vous a ete envoyee par email.<br>
    Vous pouvez des maintenant l'utiliser dans Claude Desktop.</p>
    <a href="/api.html" style="background:var(--c-gold);color:white;padding:.85rem 2rem;border-radius:var(--radius-lg);font-weight:600;text-decoration:none;margin-right:1rem">Documentation</a>
    <a href="/" style="color:var(--c-muted);font-size:.88rem">Accueil</a>
    </div></section>
    <script src="assets/app.js"></script></body></html>"""
    return HTMLResponse(html)

@app.post("/api/demo")
async def demo_api(request: Request):
    body = await request.json()
    address = body.get("address","").strip()
    dvf_radius = int(body.get("dvf_radius", 500))
    api_key = request.headers.get("X-API-Key","") or body.get("api_key","")
    if len(address) < 5:
        raise HTTPException(400, "Adresse trop courte")
    if api_key:
        client_info = await verify(api_key)
        if not client_info:
            return JSONResponse({"success":False,"error":"Cle API invalide","code":"INVALID_KEY"}, status_code=401)
    else:
        ip = _get_ip(request)
        allowed, used = _check_free_quota(ip)
        if not allowed:
            return JSONResponse({
                "success":False,"code":"QUOTA_EXCEEDED",
                "error":"Limite gratuite atteinte",
                "message":f"Vous avez utilise vos {FREE_LIMIT} analyses gratuites.",
                "used":used,"limit":FREE_LIMIT,
                "cta_url":"/tarifs.html","demo_url":"/rapport-demo",
            }, status_code=429)
    try:
        result = await analyze_parcel(address, dvf_radius)
        if not api_key:
            ip = _get_ip(request)
            used_now = _ip_usage.get(ip,{}).get("count",0)
            result["_quota"] = {"used":used_now,"limit":FREE_LIMIT,"remaining":max(0,FREE_LIMIT-used_now),"mode":"free"}
        else:
            result["_quota"] = {"mode":"api_key"}
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Demo error: {e}")
        return JSONResponse({"success":False,"erreur":str(e),"address":address}, status_code=500)

@app.post("/api/rapport")
@app.get("/rapport")
async def rapport_endpoint(request: Request):
    if request.method == "GET":
        address = request.query_params.get("address","")
        dvf_radius = int(request.query_params.get("radius",500))
    else:
        body = await request.json()
        address = body.get("address","").strip()
        dvf_radius = int(body.get("dvf_radius",500))
    if len(address) < 5:
        raise HTTPException(400, "Parametre address manquant")
    try:
        data = await analyze_parcel(address, dvf_radius)
        return HTMLResponse(generate_rapport(data))
    except Exception as e:
        return HTMLResponse(f"<h1>Erreur</h1><p>{str(e)}</p>", status_code=500)

@app.post("/api/key/create")
async def api_create_key(request: Request, x_admin_secret: str = Header(default="")):
    if x_admin_secret != os.getenv("ADMIN_SECRET","changeme"):
        raise HTTPException(403, "Non autorise")
    body = await request.json()
    key = await create_key(name=body.get("name",""), email=body.get("email",""), plan=body.get("plan","starter"))
    return {"api_key": key}

@app.get("/admin/keys")
async def admin_list_keys(x_admin_secret: str = Header(default="")):
    if x_admin_secret != os.getenv("ADMIN_SECRET","changeme"):
        raise HTTPException(403, "Non autorise")
    keys = await list_keys()
    return {"keys": keys, "total": len(keys)}

def _serve(name):
    f = "static/" + name
    return HTMLResponse(open(f).read() if os.path.exists(f) else f"<h1>{name} introuvable</h1>")

@app.get("/", response_class=HTMLResponse)
async def index(): return _serve("index.html")
@app.get("/tarifs.html", response_class=HTMLResponse)
async def tarifs(): return _serve("tarifs.html")
@app.get("/fonctionnalites.html", response_class=HTMLResponse)
async def fonctionnalites(): return _serve("fonctionnalites.html")
@app.get("/api.html", response_class=HTMLResponse)
async def api_page(): return _serve("api.html")
@app.get("/notaires.html", response_class=HTMLResponse)
async def notaires(): return _serve("notaires.html")
@app.get("/agents.html", response_class=HTMLResponse)
async def agents(): return _serve("agents.html")
@app.get("/promoteurs.html", response_class=HTMLResponse)
async def promoteurs(): return _serve("promoteurs.html")
@app.get("/mentions-legales.html", response_class=HTMLResponse)
async def mentions_legales(): return _serve("mentions-legales.html")
@app.get("/cgu.html", response_class=HTMLResponse)
async def cgu(): return _serve("cgu.html")

if os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("MCP_PORT","8000")))
    uvicorn.run(app, host=os.getenv("MCP_HOST","0.0.0.0"), port=port)
