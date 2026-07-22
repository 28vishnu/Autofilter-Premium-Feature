import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

# Import configuration variables from your project's info.py
try:
    from info import DATABASE_URI, DATABASE_URI2, DATABASE_NAME, COLLECTION_NAME
except ImportError:
    from info import DATABASE_URI, DATABASE_NAME
    DATABASE_URI2 = None
    COLLECTION_NAME = "Telegram_files"

# Logging setup to track migration progress cleanly
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DB_Migrator")

# Target threshold: 504 MB in Bytes
TARGET_SIZE_BYTES = 504 * 1024 * 1024
BATCH_SIZE = 500
CHECK_INTERVAL_SECONDS = 1800  # 30 Minutes


async def auto_migrate():
    if not DATABASE_URI2:
        logger.error("❌ DATABASE_URI2 is missing in info.py! Auto-migration worker disabled.")
        return

    logger.info("⚡ Initializing database connections for Auto-Migrator...")
    client1 = AsyncIOMotorClient(DATABASE_URI)
    client2 = AsyncIOMotorClient(DATABASE_URI2)

    db1 = client1[DATABASE_NAME]
    db2 = client2[DATABASE_NAME]

    col1 = db1[COLLECTION_NAME]
    col2 = db2[COLLECTION_NAME]

    total_migrated = 0
    logger.info("🚀 Continuous Auto-Migration daemon started.")

    try:
        while True:
            try:
                # 1. Calculate total size (Data + Index) matching Atlas quota logic
                stats = await db1.command("dbstats")
                data_size = stats.get("dataSize", 0)
                index_size = stats.get("indexSize", 0)
                total_size_bytes = data_size + index_size
                total_size_mb = total_size_bytes / (1024 * 1024)

                logger.info(
                    f"📈 [Quota Check] DB1 Storage: {total_size_mb:.2f} MB "
                    f"(Data: {data_size / (1024 * 1024):.2f} MB, Index: {index_size / (1024 * 1024):.2f} MB)"
                )

                # 2. If size is within quota, sleep for 30 minutes
                if total_size_bytes <= TARGET_SIZE_BYTES:
                    logger.info(
                        f"✅ DB1 is healthy (<= 504 MB). Sleeping for {CHECK_INTERVAL_SECONDS // 60} minutes..."
                    )
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # 3. If size > 504 MB, fetch a batch to migrate
                cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
                docs = await cursor.to_list(length=BATCH_SIZE)

                if not docs:
                    logger.info(
                        f"ℹ️ DB1 is over size threshold, but no documents were found. "
                        f"Sleeping for {CHECK_INTERVAL_SECONDS // 60} minutes..."
                    )
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                copied_ids = []

                # 4. Copy & Verify step
                for doc in docs:
                    doc_id = doc["_id"]

                    # Check if document already exists in DB2
                    exists_before = await col2.find_one({"_id": doc_id})

                    if not exists_before:
                        try:
                            await col2.insert_one(doc)
                        except DuplicateKeyError:
                            pass

                    # Fast Verification: Ensure doc exists in DB2 before marking for deletion
                    verified_in_db2 = await col2.find_one({"_id": doc_id})
                    if verified_in_db2:
                        copied_ids.append(doc_id)
                    else:
                        logger.warning(f"⚠️ Document ID {doc_id} failed verification in DB2. Skipping deletion.")

                # 5. Delete ONLY verified copied documents from DB1
                if copied_ids:
                    try:
                        delete_result = await col1.delete_many({"_id": {"$in": copied_ids}})
                        migrated_in_batch = delete_result.deleted_count
                        total_migrated += migrated_in_batch

                        logger.info(
                            f"📦 Batch Completed: {migrated_in_batch} documents moved to DB2 | "
                            f"Total Migrated Session: {total_migrated:,}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Delete failed on DB1: {e}\n"
                            "MongoDB Atlas may be blocking delete operations. Will retry next cycle."
                        )

                # Short pause between batch migrations if DB1 is still over capacity
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("🛑 Auto-migration task received cancellation signal. Stopping...")
                break
            except Exception as e:
                logger.exception(f"❌ An error occurred during migration loop: {e}")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    finally:
        client1.close()
        client2.close()
        logger.info("🔒 Auto-migrator connections closed.")


if __name__ == "__main__":
    asyncio.run(auto_migrate())
