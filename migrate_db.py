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

# Target recovery threshold: 504 MB in Bytes (Fast recovery target)
TARGET_SIZE_BYTES = 504 * 1024 * 1024
BATCH_SIZE = 1000  # 1,000 docs per chunk
BATCHES_PER_CHECK = 10  # Check dbstats once every 10 batches (10,000 docs)
CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes when healthy


async def auto_migrate():
    """High-performance background worker to ensure DB1 total storage remains under 504 MB."""
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

    logger.info(f"🚀 High-Speed Auto-Migrator daemon initialized (Target: 504 MB | Check Interval: {CHECK_INTERVAL_SECONDS // 60} mins).")

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

                # 2. If storage is under 504 MB, sleep for 5 minutes
                if total_size_bytes <= TARGET_SIZE_BYTES:
                    logger.info(f"✅ DB1 storage is healthy (<= 504 MB). Sleeping for 5 minutes...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # 3. Process up to 10 batches (10,000 docs) before re-checking dbstats
                logger.info(f"⚠️ DB1 over 504 MB threshold ({total_size_mb:.2f} MB). Moving up to {BATCHES_PER_CHECK * BATCH_SIZE:,} documents in 10 chunks...")

                for batch_num in range(1, BATCHES_PER_CHECK + 1):
                    cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
                    docs = await cursor.to_list(length=BATCH_SIZE)

                    if not docs:
                        logger.info("ℹ️ No more documents found in DB1. Ending current migration pass.")
                        break

                    batch_ids = [doc["_id"] for doc in docs]

                    # BULK COPY: Insert batch into DB2 (ignore duplicate key errors safely)
                    try:
                        await col2.insert_many(docs, ordered=False)
                    except BulkWriteError as bwe:
                        non_dup_errors = [
                            err for err in bwe.details.get("writeErrors", []) 
                            if err.get("code") != 11000
                        ]
                        if non_dup_errors:
                            logger.warning(f"⚠️ Unexpected bulk insert warnings: {non_dup_errors[:3]}")

                    # BULK VERIFICATION: Confirm existence in DB2 with 1 query
                    verified_cursor = col2.find({"_id": {"$in": batch_ids}}, {"_id": 1})
                    verified_docs = await verified_cursor.to_list(length=len(batch_ids))
                    verified_ids = [doc["_id"] for doc in verified_docs]

                    if not verified_ids:
                        logger.warning(f"⚠️ Chunk {batch_num}/{BATCHES_PER_CHECK}: Zero documents verified in DB2. Skipping deletion.")
                        await asyncio.sleep(2)
                        continue

                    # BULK DELETE: Delete ONLY verified documents from DB1
                    try:
                        delete_result = await col1.delete_many({"_id": {"$in": verified_ids}})
                        logger.info(
                            f"⚡ Chunk {batch_num}/{BATCHES_PER_CHECK}: Moved {delete_result.deleted_count}/{len(docs)} docs to DB2."
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Delete failed on DB1: {e}\n"
                            "MongoDB Atlas may be blocking delete operations due to write restrictions."
                        )
                        break

                    # Small 0.3s pause between chunks to keep IO smooth
                    await asyncio.sleep(0.3)

                # Brief 1-second pause before checking dbstats again
                await asyncio.sleep(1)

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
