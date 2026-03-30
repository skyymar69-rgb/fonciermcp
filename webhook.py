import logging, os, stripe
from starlette.requests import Request
from starlette.responses import JSONResponse
from auth import create, revoke

logger = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY","")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET","")
PLAN_MAP = {"price_starter": "starter", "price_pro": "pro", "price_cabinet": "cabinet"}

async def handle_webhook(request: Request) -> JSONResponse:
    body = await request.body()
    sig = request.headers.get("stripe-signature","")
    try:
        event = stripe.Webhook.construct_event(body, sig, WEBHOOK_SECRET)
    except Exception as e:
        return JSONResponse({"error": "invalide"}, status_code=400)
    t = event["type"]
    obj = event["data"]["object"]
    if t == "customer.subscription.created":
        cust = stripe.Customer.retrieve(obj["customer"])
        price_id = obj["items"]["data"][0]["price"]["id"]
        key = await create(name=cust.get("name", cust.get("email","")), email=cust.get("email",""), plan=PLAN_MAP.get(price_id,"starter"))
        logger.info(f"Nouveau client {cust.get('email')} - cle generee")
    elif t in ("customer.subscription.deleted","customer.subscription.paused"):
        cust = stripe.Customer.retrieve(obj["customer"])
        await revoke(cust.get("email",""))
    return JSONResponse({"status": "ok"})