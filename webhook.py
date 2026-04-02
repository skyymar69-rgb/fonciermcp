"""
webhook.py v2 — Stripe integration pour Lex Foncier
Plans: Starter 49euro, Pro 149euro, Cabinet 490euro/mois
"""
import os, logging, json
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

STRIPE_PLANS = {
    "starter":  os.getenv("STRIPE_PRICE_STARTER",  ""),
    "pro":      os.getenv("STRIPE_PRICE_PRO",       ""),
    "cabinet":  os.getenv("STRIPE_PRICE_CABINET",   ""),
}
STRIPE_SECRET  = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK = os.getenv("STRIPE_WEBHOOK_SECRET", "")
APP_URL = os.getenv("APP_URL", "https://app-production-71c1.up.railway.app")

async def handle_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if STRIPE_WEBHOOK and STRIPE_SECRET:
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK)
        except Exception as e:
            logger.error(f"Stripe webhook invalid: {e}")
            return JSONResponse({"error": str(e)}, status_code=400)
    else:
        try:
            event = json.loads(payload)
        except Exception:
            return JSONResponse({"error": "invalid payload"}, status_code=400)
    etype = event.get("type", "")
    data  = event.get("data", {}).get("object", {})
    logger.info(f"Stripe event: {etype}")
    if etype == "checkout.session.completed":
        await _on_checkout_completed(data)
    elif etype == "customer.subscription.deleted":
        await _on_subscription_cancelled(data)
    elif etype == "invoice.payment_failed":
        logger.warning(f"Paiement echoue: {data.get('customer_email','?')}")
    return JSONResponse({"received": True})

async def _on_checkout_completed(session: dict):
    email   = session.get("customer_email", "")
    plan    = session.get("metadata", {}).get("plan", "starter")
    cust_id = session.get("customer", "")
    sub_id  = session.get("subscription", "")
    if not email:
        return
    from auth import create as create_key, store_customer
    api_key = await create_key(name=email, email=email, plan=plan)
    await store_customer(email=email, plan=plan,
        stripe_customer_id=cust_id,
        stripe_subscription_id=sub_id,
        api_key=api_key)
    await _send_welcome_email(email, api_key, plan)
    logger.info(f"Nouveau client {email} ({plan})")

async def _on_subscription_cancelled(subscription: dict):
    cust_id = subscription.get("customer", "")
    from auth import revoke_by_customer
    await revoke_by_customer(cust_id)
    logger.info(f"Abonnement annule: {cust_id}")

async def _send_welcome_email(email: str, api_key: str, plan: str):
    resend_key = os.getenv("RESEND_API_KEY", "")
    if not resend_key:
        logger.info(f"Email non envoye (RESEND_API_KEY manquant) cle={api_key[:12]}...")
        return
    try:
        async with httpx.AsyncClient() as client:
            config_json = (
                '{\n'
                '  "mcpServers": {\n'
                '    "lex-foncier": {\n'
                '      "url": "' + APP_URL + '/mcp",\n'
                '      "headers": { "X-API-Key": "' + api_key + '" }\n'
                '    }\n'
                '  }\n'
                '}'
            )
            html_body = (
                "<h2>Bienvenue sur Lex Foncier</h2>"
                "<p>Votre abonnement <strong>" + plan.capitalize() + "</strong> est actif.</p>"
                "<p><strong>Votre cle API :</strong></p>"
                "<pre style='background:#f5f5f5;padding:1rem;border-radius:6px;font-size:1.1rem'>"
                + api_key +
                "</pre>"
                "<h3>Integration Claude Desktop</h3>"
                "<p>Ajoutez dans votre <code>claude_desktop_config.json</code> :</p>"
                "<pre style='background:#f5f5f5;padding:1rem;border-radius:6px'>" + config_json + "</pre>"
                "<p>Documentation : <a href='" + APP_URL + "/api.html'>api.html</a></p>"
            )
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}"},
                json={
                    "from": "Lex Foncier <contact@lexfoncier.fr>",
                    "to": [email],
                    "subject": f"Votre cle API Lex Foncier — Plan {plan.capitalize()}",
                    "html": html_body
                }
            )
            logger.info(f"Email envoye a {email}")
    except Exception as e:
        logger.error(f"Email error: {e}")

async def create_checkout_session(plan: str, email: str = "") -> dict:
    if not STRIPE_SECRET:
        return {"error": "STRIPE_SECRET_KEY non configure"}
    price_id = STRIPE_PLANS.get(plan, "")
    if not price_id:
        return {"error": f"Prix Stripe non configure pour le plan '{plan}'"}
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=email or None,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"plan": plan},
            success_url=APP_URL + "/merci?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=APP_URL + "/tarifs.html",
            locale="fr",
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e)}
