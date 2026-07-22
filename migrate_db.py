import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError

# Import configuration variables from info.py
try:
    from info import DATABASE_URI, DATABASE_URI2, DATABASE_NAME, COLLECTION_NAME
except ImportError:
    from info import DATABASE_URI, DATABASE_NAME
    DATABASE_URI2 = None
    COLLECTION_NAME = "Telegram_files"

# Logging setup to track migration progress cleanly
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AutoMigrator")

# Target threshold: 504 MB in Bytes (Data + Index)
TARGET_SIZE_BYTES = 504 * 1024 * 1024
BATCH_SIZE = 1000  # Optimized batch size (can be bumped to 2000-5000 if needed)
CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes


async def auto_migrate():
    """High-performance background worker to ensure DB1 total storage remains under 504 MB."""
    if not DATABASE_URI2:
        logger.error("❌ DATABASE_URI2 is missing in info.py! Storage auto-migrator disabled.")
        return

    logger.info("⚡ Initializing database connections for Optimized Auto-Migrator...")
    client1 = AsyncIOMotorClient(DATABASE_URI)
    client2 = AsyncIOMotorClient(DATABASE_URI2)

    db1 = client1[DATABASE_NAME]
    db2 = client2[DATABASE_NAME]

    col1 = db1[COLLECTION_NAME]
    col2 = db2[COLLECTION_NAME]

    logger.info(f"🚀 High-Speed Auto-Migrator daemon initialized (Check interval: {CHECK_INTERVAL_SECONDS // 60} mins).")

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
                    f"📈 [Quota Check] DB1 Total Storage: {total_size_mb:.2f} MB "
                    f"(Data: {data_size / (1024 * 1024):.2f} MB | Index: {index_size / (1024 * 1024):.2f} MB)"
                )

                # 2. If storage is under target threshold, sleep for 5 minutes
                if total_size_bytes <= TARGET_SIZE_BYTES:
                    logger.info(f"✅ DB1 storage is healthy (<= 504 MB). Sleeping for 5 minutes...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # 3. Fetch batch deterministically using _id index
                logger.info(f"⚠️ DB1 over 504 MB threshold! Moving batch of {BATCH_SIZE} to DB2...")
                cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
                docs = await cursor.to_list(length=BATCH_SIZE)

                if not docs:
                    logger.info("ℹ️ DB1 over quota, but zero documents were returned. Sleeping 5 minutes...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                batch_ids = [doc["_id"] for doc in docs]

                # 4. BULK COPY: Attempt bulk insert into DB2 (ignore duplicate key errors safely)
                try:
                    await col2.insert_many(docs, ordered=False)
                except BulkWriteError as bwe:
                    # Duplicate key errors (E11000) are expected if records exist in DB2; log only non-duplicate errors
                    non_dup_errors = [
                        err for err in bwe.details.get("writeErrors", []) 
                        if err.get("code") != 11000
                    ]
                    if non_dup_errors:
                        logger.warning(f"⚠️ Unexpected bulk insert warnings: {non_dup_errors[:3]}")

                # 5. BULK VERIFICATION: Query DB2 in 1 single call for all IDs in batch
                verified_cursor = col2.find({"_id": {"$in": batch_ids}}, {"_id": 1})
                verified_docs = await verified_cursor.to_list(length=len(batch_ids))
                verified_ids = [doc["_id"] for doc in verified_docs]

                if not verified_ids:
                    logger.warning("⚠️ No documents in the current batch passed DB2 verification. Skipping deletion.")
                    await asyncio.sleep(5)
                    continue

                # 6. BULK DELETE: Delete ONLY verified documents from DB1
                try:
                    delete_result = await col1.delete_many({"_id": {"$in": verified_ids}})
                    logger.info(
                        f"⚡ Batch Complete! Successfully moved {delete_result.deleted_count}/{len(docs)} documents."
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Delete failed on DB1: {e}\n"
                        "MongoDB Atlas may be blocking delete operations due to write restrictions."
                    )
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # Small 0.5-second pause between batches if DB1 is still over 504 MB
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                logger.info("🛑 Auto-migration task received cancellation signal. Stopping...")
                break
            except Exception as e:
                logger.exception(f"❌ Storage Auto-Migrator encountered an error: {e}")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    finally:
        client1.close()
        client2.close()
        logger.info("🔒 Storage Auto-Migrator connections closed cleanly.")


if __name__ == "__main__":
    asyncio.run(auto_migrate())
