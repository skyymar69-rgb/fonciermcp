import logging, os
import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from mcp.server.fastmcp import FastMCP
from auth import verify, create as create_key
from webhook import handle_webhook
from tools.analyze_parcel import analyze_parcel
from tools.dvf import get_dvf_history
from tools.plu import check_plu_rules
from tools.risks import get_erp_risks
from tools.dpe import get_dpe

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
logger = logging.getLogger(__name__)

mcp = FastMCP(name="FoncierMCP", instructions="Tu es FoncierMCP, assistant analyse fonciere France.")
mcp.tool()(analyze_parcel)
mcp.tool()(get_dvf_history)
mcp.tool()(check_plu_rules)
mcp.tool()(get_erp_risks)
mcp.tool()(get_dpe)

app = FastAPI(title="FoncierMCP", docs_url=None, redoc_url=None)
app.mount("/mcp", mcp.streamable_http_app())

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    exempt = ["/health", "/webhook/stripe", "/api/demo", "/api/key/create", "/"]
    if not path.startswith("/mcp") or any(path.startswith(e) for e in exempt):
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
    return {"status": "ok", "service": "FoncierMCP"}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_webhook(request)

@app.post("/api/demo")
async def demo_api(request: Request):
    body = await request.json()
    address = body.get("address","").strip()
    if len(address) < 5:
        raise HTTPException(400, "Adresse trop courte")
    return JSONResponse(await analyze_parcel(address))

@app.post("/api/key/create")
async def api_create_key(request: Request, x_admin_secret: str = Header(default="")):
    if x_admin_secret != os.getenv("ADMIN_SECRET","changeme"):
        raise HTTPException(403, "Non autorise")
    body = await request.json()
    key = await create_key(name=body.get("name",""), email=body.get("email",""), plan=body.get("plan","starter"))
    return {"api_key": key}

@app.get("/", response_class=HTMLResponse)
async def index():
    f = "static/index.html"
    return HTMLResponse(open(f).read() if os.path.exists(f) else "<h1>FoncierMCP</h1><p><a href=/health>Health OK</a></p>")

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info(f"FoncierMCP sur {host}:{port}")
    uvicorn.run(app, host=host, port=port)
