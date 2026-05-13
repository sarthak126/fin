import asyncio
from core.database import db

async def test():
    print("Connecting db")
    await db.connect()
    print("Connected db")
    await db.disconnect()
    print("Disconnected db")

if __name__ == "__main__":
    asyncio.run(test())
