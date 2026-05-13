import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    try:
        await db.connect()
        print("DATABASE_CONNECTED_SUCCESSFULLY")
        
        # Test a query
        count = await db.document.count()
        print(f"Document count: {count}")
    except Exception as e:
        print(f"DATABASE_CONNECTION_ERROR: {e}")
    finally:
        if db.is_connected():
            await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
