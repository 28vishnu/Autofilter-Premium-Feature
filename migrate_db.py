import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

try:
    from info import DATABASE_URI, DATABASE_URI2, DATABASE_NAME, COLLECTION_NAME
except ImportError:
    from info import DATABASE_URI, DATABASE_NAME
    DATABASE_URI2 = None
    COLLECTION_NAME = "Telegram_files"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AutoMigrator")

TARGET_SIZE_BYTES = 504 * 1024 * 1024  # 504 MB threshold
BATCH_SIZE = 500
CHECK_INTERVAL_SECONDS = 300  # 5 minutes


async def auto_migrate():
    """Continuous background worker to ensure DB1 remains under 504 MB."""
    if not DATABASE_URI2:
        logger.error("❌ DATABASE_URI2 is missing in info.py! Storage auto-migrator disabled.")
        return

    logger.info("⚡ Initializing database connections for Storage Auto-Migrator...")
    client1 = AsyncIOMotorClient(DATABASE_URI)
    client2 = AsyncIOMotorClient(DATABASE_URI2)

    db1 = client1[DATABASE_NAME]
    db2 = client2[DATABASE_NAME]

    col1 = db1[COLLECTION_NAME]
    col2 = db2[COLLECTION_NAME]

    logger.info(f"🚀 Storage Auto-Migrator daemon running (Check interval: {CHECK_INTERVAL_SECONDS // 60} mins).")

    try:
        while True:
            try:
                stats = await db1.command("dbstats")
                data_size = stats.get("dataSize", 0)
                index_size = stats.get("indexSize", 0)
                total_size_bytes = data_size + index_size
                total_size_mb = total_size_bytes / (1024 * 1024)

                logger.info(
                    f"📈 [Quota Check] DB1 Total Size: {total_size_mb:.2f} MB "
                    f"(Data: {data_size / (1024 * 1024):.2f} MB | Index: {index_size / (1024 * 1024):.2f} MB)"
                )

                # Under target threshold: sleep for 5 minutes
                if total_size_bytes <= TARGET_SIZE_BYTES:
                    logger.info(f"✅ DB1 storage is healthy (<= 504 MB). Sleeping for 5 minutes...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # Over threshold: process a batch of 500 records
                logger.info("⚠️ DB1 over 504 MB threshold! Moving batch to DB2...")
                cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
                docs = await cursor.to_list(length=BATCH_SIZE)

                if not docs:
                    logger.info("ℹ️ DB1 over quota, but zero documents were returned. Sleeping 5 minutes...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                copied_ids = []

                for doc in docs:
                    doc_id = doc["_id"]
                    exists_before = await col2.find_one({"_id": doc_id})

                    if not exists_before:
                        try:
                            await col2.insert_one(doc)
                        except DuplicateKeyError:
                            pass

                    # Verify existence in DB2 prior to scheduling DB1 deletion
                    verified_in_db2 = await col2.find_one({"_id": doc_id})
                    if verified_in_db2:
                        copied_ids.append(doc_id)
                    else:
                        logger.warning(f"⚠️ Document ID {doc_id} failed verification in DB2. Skipping deletion.")

                if copied_ids:
                    try:
                        delete_result = await col1.delete_many({"_id": {"$in": copied_ids}})
                        logger.info(f"📦 Successfully moved {delete_result.deleted_count} documents from DB1 -> DB2.")
                    except Exception as e:
                        logger.error(f"❌ Delete failed on DB1 (Possible Atlas write block): {e}")

                # Brief 1-second pause before checking if another batch is needed
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("🛑 Auto-migration task received cancellation signal. Exiting.")
                break
            except Exception as e:
                logger.exception(f"❌ Storage Auto-Migrator error: {e}")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    finally:
        client1.close()
        client2.close()
        logger.info("🔒 Storage Auto-Migrator connections closed.")
