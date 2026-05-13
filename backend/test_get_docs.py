import asyncio
import sys
import traceback
from core.database import db
from services.document_service import get_documents

async def main():
    try:
        await db.connect()
        docs = await get_documents(db, 'dev-org')
        print("Success:", len(docs), "documents")
    except Exception as e:
        print("Prisma Error:", e)
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
