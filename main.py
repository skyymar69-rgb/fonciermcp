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

mcp = FastMCP(name="LexFoncier", instructions="Tu es Lex Foncier, assistant analyse fonciere France. Tu interroges les données officielles françaises (IGN, DGFiP, GPU, Géorisques, ADEME) pour produire des analyses foncières complètes.")
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
    public = ["/health", "/webhook/stripe", "/api/demo", "/api/key/create", "/",
              "/rapport", "/tarifs.html", "/fonctionnalites.html", "/api.html",
              "/notaires.html", "/agents.html", "/promoteurs.html",
              "/mentions-legales.html", "/cgu.html"]
    if not path.startswith("/mcp") or any(path.startswith(e) for e in public):
        return await call_next(request)
    key = request.headers.get("X-API-Key","")
    if not key:
        return JSONResponse({"error": "X-API-Key manquant"}, status_code=401)
    client = await verify(key)
    if not client:
        return JSONResponse({"error": "Cle invalide"}, status_code=403)
    request.state.client = client
    return await call_next(request)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "LexFoncier", "version": "2.0"}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_webhook(request)

@app.post("/api/demo")
async def demo_api(request: Request):
    """Demo API - retourne les données JSON complètes"""
    body = await request.json()
    address = body.get("address","").strip()
    dvf_radius = int(body.get("dvf_radius", 500))
    if len(address) < 5:
        raise HTTPException(400, "Adresse trop courte (min 5 caractères)")
    try:
        result = await analyze_parcel(address, dvf_radius)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Demo error for '{address}': {e}")
        return JSONResponse({"success": False, "erreur": str(e), "address": address}, status_code=500)

@app.post("/api/rapport")
@app.get("/rapport")
async def rapport_endpoint(request: Request):
    """Génère un rapport HTML imprimable"""
    if request.method == "GET":
        address = request.query_params.get("address","")
        dvf_radius = int(request.query_params.get("radius", 500))
    else:
        body = await request.json()
        address = body.get("address","").strip()
        dvf_radius = int(body.get("dvf_radius", 500))
    
    if len(address) < 5:
        raise HTTPException(400, "Paramètre address manquant ou trop court")
    
    try:
        data = await analyze_parcel(address, dvf_radius)
        html = generate_rapport(data)
        return HTMLResponse(html)
    except Exception as e:
        logger.error(f"Rapport error for '{address}': {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{str(e)}</p>", status_code=500)

@app.post("/api/key/create")
async def api_create_key(request: Request, x_admin_secret: str = Header(default="")):
    if x_admin_secret != os.getenv("ADMIN_SECRET","changeme"):
        raise HTTPException(403, "Non autorise")
    body = await request.json()
    key = await create_key(name=body.get("name",""), email=body.get("email",""), plan=body.get("plan","starter"))
    return {"api_key": key}

def _serve_html(name: str) -> HTMLResponse:
    f = f"static/{name}"
    return HTMLResponse(open(f).read() if os.path.exists(f) else f"<h1>{name} introuvable</h1>", 200,
                        headers={"Cache-Control": "public, max-age=3600"})

@app.get("/", response_class=HTMLResponse)
async def index(): return _serve_html("index.html")

@app.get("/tarifs.html", response_class=HTMLResponse)
async def tarifs(): return _serve_html("tarifs.html")

@app.get("/fonctionnalites.html", response_class=HTMLResponse)
async def fonctionnalites(): return _serve_html("fonctionnalites.html")

@app.get("/api.html", response_class=HTMLResponse)
async def api_page(): return _serve_html("api.html")

@app.get("/notaires.html", response_class=HTMLResponse)
async def notaires(): return _serve_html("notaires.html")

@app.get("/agents.html", response_class=HTMLResponse)
async def agents(): return _serve_html("agents.html")

@app.get("/promoteurs.html", response_class=HTMLResponse)
async def promoteurs(): return _serve_html("promoteurs.html")

@app.get("/mentions-legales.html", response_class=HTMLResponse)
async def mentions_legales(): return _serve_html("mentions-legales.html")

@app.get("/cgu.html", response_class=HTMLResponse)
async def cgu(): return _serve_html("cgu.html")

if os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info(f"Lex Foncier v2.0 sur {host}:{port}")
    uvicorn.run(app, host=host, port=port)
