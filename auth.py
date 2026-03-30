import hashlib, secrets, logging, os
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)
_pool = None

async def get_pool():
    global _pool
    if not _pool:
        _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL",""), min_size=1, max_size=5)
        async with _pool.acquire() as c:
            await c.execute("""CREATE TABLE IF NOT EXISTS api_keys (id SERIAL PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, plan TEXT NOT NULL DEFAULT 'starter', active BOOLEAN NOT NULL DEFAULT TRUE, requests INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")
    return _pool

def _hash(k): return hashlib.sha256(k.encode()).hexdigest()

async def verify(api_key: str):
    pool = await get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT name,email,plan,active,requests FROM api_keys WHERE key_hash=$1", _hash(api_key))
        if not row or not row["active"]: return None
        await c.execute("UPDATE api_keys SET requests=requests+1 WHERE key_hash=$1", _hash(api_key))
        return dict(row)

async def create(name: str, email: str, plan: str = "starter") -> str:
    key = f"fmcp_{secrets.token_urlsafe(32)}"
    pool = await get_pool()
    async with pool.acquire() as c:
        await c.execute("INSERT INTO api_keys (key_hash,name,email,plan) VALUES ($1,$2,$3,$4)", _hash(key), name, email, plan)
    return key

async def revoke(email: str):
    pool = await get_pool()
    async with pool.acquire() as c:
        await c.execute("UPDATE api_keys SET active=FALSE WHERE email=$1", email)