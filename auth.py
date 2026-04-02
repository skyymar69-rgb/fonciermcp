"""
auth.py v2 — Gestion des cles API avec PostgreSQL Railway
Compatible avec le plan gratuit (fallback memoire si DB indisponible)
"""
import os, secrets, hashlib, logging
logger = logging.getLogger(__name__)

_pool = None
_mem_keys = {}  # fallback memoire si pas de DB

async def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
        await _init_schema()
        return _pool
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return None

async def _init_schema():
    pool = await _get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                key_prefix TEXT NOT NULL,
                name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                plan TEXT DEFAULT 'starter',
                active BOOLEAN DEFAULT true,
                stripe_customer_id TEXT DEFAULT '',
                stripe_subscription_id TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_used_at TIMESTAMPTZ,
                usage_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_key_hash ON api_keys(key_hash);
            CREATE INDEX IF NOT EXISTS idx_stripe_cust ON api_keys(stripe_customer_id);
        """)
        logger.info("DB schema OK")

def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

async def create(name: str = "", email: str = "", plan: str = "starter") -> str:
    key = "lf_" + secrets.token_urlsafe(32)
    pool = await _get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO api_keys (key_hash, key_prefix, name, email, plan) VALUES ($1,$2,$3,$4,$5)",
                _hash(key), key[:12], name, email, plan
            )
    else:
        _mem_keys[_hash(key)] = {"name":name,"email":email,"plan":plan,"active":True}
        logger.warning(f"Cle stockee en memoire: {key[:12]}")
    return key

async def verify(key: str) -> dict | None:
    if not key or not key.startswith("lf_") or len(key) < 20:
        return None
    h = _hash(key)
    pool = await _get_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name, email, plan, active FROM api_keys WHERE key_hash=$1", h)
            if not row or not row["active"]:
                return None
            await conn.execute(
                "UPDATE api_keys SET last_used_at=NOW(), usage_count=usage_count+1 WHERE key_hash=$1", h)
            return dict(row)
    else:
        entry = _mem_keys.get(h)
        if entry and entry.get("active"):
            return entry
        return None

async def store_customer(email: str, plan: str, stripe_customer_id: str,
                          stripe_subscription_id: str, api_key: str):
    pool = await _get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE api_keys SET stripe_customer_id=$1, stripe_subscription_id=$2 WHERE key_hash=$3",
            stripe_customer_id, stripe_subscription_id, _hash(api_key)
        )

async def revoke_by_customer(stripe_customer_id: str):
    pool = await _get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE api_keys SET active=false WHERE stripe_customer_id=$1", stripe_customer_id)

async def list_keys(limit: int = 50) -> list:
    pool = await _get_pool()
    if not pool:
        return [{"key_prefix":h[:12],"plan":v["plan"],"email":v["email"],"active":v["active"]}
                for h,v in list(_mem_keys.items())[:limit]]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key_prefix,name,email,plan,active,created_at,usage_count FROM api_keys ORDER BY created_at DESC LIMIT $1", limit)
        return [dict(r) for r in rows]
