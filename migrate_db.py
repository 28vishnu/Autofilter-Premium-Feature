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

# Hysteresis Thresholds
START_MIGRATION_BYTES = 490 * 1024 * 1024  # Start migrating when DB1 reaches 490 MB
STOP_MIGRATION_BYTES  = 450 * 1024 * 1024  # Stop migrating when DB1 drops below 450 MB

BATCH_SIZE = 1000          # 1,000 docs per chunk
BATCHES_PER_CHECK = 10     # Process up to 10 batches (10,000 docs) per pass
CHECK_INTERVAL_SECONDS = 300  # Check storage every 5 minutes when healthy


async def auto_migrate():
    """Hysteresis-based background worker to keep DB1 comfortably between 450 MB and 490 MB."""
    if not DATABASE_URI2:
        logger.error("❌ DATABASE_URI2 is missing in info.py! Storage auto-migrator disabled.")
        return

    logger.info("⚡ Initializing database connections for Resilient Auto-Migrator...")
    client1 = AsyncIOMotorClient(DATABASE_URI)
    client2 = AsyncIOMotorClient(DATABASE_URI2)

    db1 = client1[DATABASE_NAME]
    db2 = client2[DATABASE_NAME]

    col1 = db1[COLLECTION_NAME]
    col2 = db2[COLLECTION_NAME]

    logger.info(
        f"🚀 Resilient Auto-Migrator daemon running "
        f"(Trigger: 490 MB | Target: 450 MB | Interval: {CHECK_INTERVAL_SECONDS // 60} mins)."
    )

    try:
        while True:
            try:
                # 1. Calculate current DB1 size (Data + Index)
                stats = await db1.command("dbstats")
                data_size = stats.get("dataSize", 0)
                index_size = stats.get("indexSize", 0)
                total_size_bytes = data_size + index_size
                total_size_mb = total_size_bytes / (1024 * 1024)

                logger.info(
                    f"📈 [Quota Check] DB1 Total Storage: {total_size_mb:.2f} MB "
                    f"(Data: {data_size / (1024 * 1024):.2f} MB | Index: {index_size / (1024 * 1024):.2f} MB)"
                )

                # 2. Check if DB1 is below the migration trigger threshold
                if total_size_bytes < START_MIGRATION_BYTES:
                    logger.info(
                        f"✅ DB1 storage is in healthy zone ({total_size_mb:.2f} MB < 490 MB). "
                        f"Sleeping for 5 minutes..."
                    )
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                # 3. DB1 reached or exceeded 490 MB — Enter continuous migration drain loop
                logger.info(
                    f"⚠️ DB1 reached {total_size_mb:.2f} MB (>= 490 MB trigger)! "
                    f"Draining DB1 down to 450 MB..."
                )

                while True:
                    # Re-check dbstats before each 10-batch pass
                    loop_stats = await db1.command("dbstats")
                    current_bytes = loop_stats.get("dataSize", 0) + loop_stats.get("indexSize", 0)
                    current_mb = current_bytes / (1024 * 1024)

                    # Stop condition: Storage dropped to or below 450 MB
                    if current_bytes <= STOP_MIGRATION_BYTES:
                        logger.info(
                            f"🎉 Draining complete! DB1 storage is now {current_mb:.2f} MB (<= 450 MB). "
                            f"Stopping active migration."
                        )
                        break

                    logger.info(
                        f"🔄 Draining active ({current_mb:.2f} MB) -> Moving up to "
                        f"{BATCHES_PER_CHECK * BATCH_SIZE:,} documents..."
                    )

                    for batch_num in range(1, BATCHES_PER_CHECK + 1):
                        cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
                        docs = await cursor.to_list(length=BATCH_SIZE)

                        if not docs:
                            logger.info("ℹ️ No more documents found in DB1. Exiting drain loop.")
                            break

                        batch_ids = [doc["_id"] for doc in docs]

                        # BULK COPY: Insert batch into DB2 (ignore duplicates safely)
                        try:
                            await col2.insert_many(docs, ordered=False)
                        except BulkWriteError as bwe:
                            non_dup_errors = [
                                err for err in bwe.details.get("writeErrors", [])
                                if err.get("code") != 11000
                            ]
                            if non_dup_errors:
                                logger.warning(f"⚠️ Bulk insert warnings: {non_dup_errors[:3]}")

                        # BULK VERIFICATION: Confirm existence in DB2
                        verified_cursor = col2.find({"_id": {"$in": batch_ids}}, {"_id": 1})
                        verified_docs = await verified_cursor.to_list(length=len(batch_ids))
                        verified_ids = [doc["_id"] for doc in verified_docs]

                        if not verified_ids:
                            logger.warning(
                                f"⚠️ Chunk {batch_num}/{BATCHES_PER_CHECK}: Zero docs verified in DB2. Skipping deletion."
                            )
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
                                "MongoDB Atlas write block detected. Stopping drain loop."
                            )
                            break

                        await asyncio.sleep(0.3)

                    await asyncio.sleep(1)

                # Brief pause before returning to standard monitoring mode
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

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
