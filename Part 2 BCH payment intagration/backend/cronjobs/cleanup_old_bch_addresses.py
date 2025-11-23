import asyncpg
from config import DB_DSN


async def cleanup_old_bch_addresses():
    print("🧹 Cleaning up BCH addresses older than 24 hours (keeping those with payments)...")
    pool = await asyncpg.create_pool(dsn=DB_DSN)
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM bch
                WHERE created_at < NOW() - INTERVAL '24 hours'
                  AND address NOT IN (SELECT address FROM bchpayment)
            """)
        print(f"✅ {result} — Old BCH addresses cleaned up.")
    except Exception as e:
        print(f"❌ Error while cleaning BCH addresses: {e}")
    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(cleanup_old_bch_addresses())


