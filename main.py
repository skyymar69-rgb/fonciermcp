import logging, os
import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from auth import verify, create as create_key
from webhook import handle_webhook
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

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    public = ["/health","/webhook/stripe","/api/demo","/api/key/create","/",
              "/rapport","/diagnostic","/tarifs.html","/fonctionnalites.html",
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
    return {"status":"ok","service":"LexFoncier","version":"2.1"}

@app.get("/diagnostic")
async def diagnostic():
    import httpx, time
    urls = [
        ("BAN", "https://api-adresse.data.gouv.fr/search/?q=Lyon&limit=1"),
        ("IGN_carto", "https://apicarto.ign.fr/api/cadastre/commune?code_insee=69123&_limit=1"),
        ("DVF_etalab", "https://api.dvf.etalab.gouv.fr/geoapi/mutations?lat=45.76&lon=4.83&dist=100"),
        ("GPU_IGN", "https://apicarto.ign.fr/api/gpu/zone-urba?lon=4.83&lat=45.76"),
        ("Georisques", "https://georisques.gouv.fr/api/v1/gaspar/risques?latlon=4.83,45.76&rayon=500"),
        ("ADEME_dpe", "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines?size=1"),
        ("INSEE_geo", "https://geo.api.gouv.fr/communes?code=69123"),
        ("Data_gouv", "https://www.data.gouv.fr/api/1/datasets/?q=dvf&page_size=1"),
        ("DVF_data", "https://files.data.gouv.fr/geo-dvf/latest/csv/69/communes/69123.csv.gz"),
    ]
    results = {}
    async with httpx.AsyncClient(timeout=8) as client:
        for name, url in urls:
            t0 = time.time()
            try:
                r = await client.get(url)
                ct = r.headers.get("content-type","")[:30]
                results[name] = {"status":r.status_code,"ms":round((time.time()-t0)*1000),"ok":r.status_code<400,"ct":ct}
            except Exception as e:
                results[name] = {"status":0,"error":str(e)[:60],"ok":False}
    return results

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_webhook(request)

@app.post("/api/demo")
async def demo_api(request: Request):
    body = await request.json()
    address = body.get("address","").strip()
    dvf_radius = int(body.get("dvf_radius",500))
    if len(address) < 5:
        raise HTTPException(400, "Adresse trop courte")
    try:
        result = await analyze_parcel(address, dvf_radius)
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
        html = generate_rapport(data)
        return HTMLResponse(html)
    except Exception as e:
        logger.error(f"Rapport error: {e}")
        return HTMLResponse("<h1>Erreur</h1><p>" + str(e) + "</p>", status_code=500)

@app.post("/api/key/create")
async def api_create_key(request: Request, x_admin_secret: str = Header(default="")):
    if x_admin_secret != os.getenv("ADMIN_SECRET","changeme"):
        raise HTTPException(403, "Non autorise")
    body = await request.json()
    key = await create_key(name=body.get("name",""),email=body.get("email",""),plan=body.get("plan","starter"))
    return {"api_key": key}

def _serve(name):
    f = "static/" + name
    return HTMLResponse(open(f).read() if os.path.exists(f) else "<h1>" + name + "</h1>")

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
    host = os.getenv("MCP_HOST","0.0.0.0")
    uvicorn.run(app, host=host, port=port)
