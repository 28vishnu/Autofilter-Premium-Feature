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
BATCH_SIZE = 10  # Initial test batch size


async def run_migration():
    if not DATABASE_URI2:
        logger.error("❌ DATABASE_URI2 is missing in info.py! Please define it before running.")
        return

    logger.info("⚡ Connecting to Database 1 and Database 2...")
    client1 = AsyncIOMotorClient(DATABASE_URI)
    client2 = AsyncIOMotorClient(DATABASE_URI2)

    db1 = client1[DATABASE_NAME]
    db2 = client2[DATABASE_NAME]

    col1 = db1[COLLECTION_NAME]
    col2 = db2[COLLECTION_NAME]

    # Pre-migration count verification
    count1 = await col1.count_documents({})
    count2 = await col2.count_documents({})
    logger.info(f"📊 Initial Document Count - DB1: {count1:,} | DB2: {count2:,}")

    total_migrated = 0

    logger.info(f"🚀 Starting database migration (Batch Size: {BATCH_SIZE})...")

    try:
        while True:
            # 1. Calculate total size (Data + Index) matching Atlas quota logic
            stats = await db1.command("dbstats")
            data_size = stats.get("dataSize", 0)
            index_size = stats.get("indexSize", 0)
            total_size_bytes = data_size + index_size
            total_size_mb = total_size_bytes / (1024 * 1024)

            logger.info(
                f"📈 DB1 Storage: {total_size_mb:.2f} MB "
                f"(Data: {data_size / (1024 * 1024):.2f} MB, Index: {index_size / (1024 * 1024):.2f} MB)"
            )

            if total_size_bytes <= TARGET_SIZE_BYTES:
                logger.info("✅ Target reached! DB1 total size (Data + Index) is now under 504 MB. Stopping.")
                break

            # 2. Fetch the next batch deterministically using indexed _id sorting
            cursor = col1.find().sort("_id", 1).limit(BATCH_SIZE)
            docs = await cursor.to_list(length=BATCH_SIZE)

            if not docs:
                logger.info("ℹ️ No more documents found in DB1. Migration complete.")
                break

            copied_ids = []

            # 3. Copy & Verify step
            for doc in docs:
                doc_id = doc["_id"]

                # Fast check if document already exists in DB2
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

            # 4. Delete ONLY verified copied documents from DB1 (with error handling for quota blocks)
            if copied_ids:
                try:
                    delete_result = await col1.delete_many({"_id": {"$in": copied_ids}})
                    migrated_in_batch = delete_result.deleted_count
                    total_migrated += migrated_in_batch

                    logger.info(
                        f"📦 Batch Completed: {migrated_in_batch} documents moved | "
                        f"Total Migrated So Far: {total_migrated:,}"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Delete failed on DB1: {e}\n"
                        "MongoDB Atlas is blocking delete operations due to storage quota restrictions.\n"
                        "Migration paused."
                    )
                    break

            # Small pause to keep connection light
            await asyncio.sleep(0.5)

    except Exception as e:
        logger.exception(f"❌ An error occurred during migration: {e}")

    finally:
        # Final document count summary
        final_count1 = await col1.count_documents({})
        final_count2 = await col2.count_documents({})
        logger.info(f"🏁 Final Document Count - DB1: {final_count1:,} | DB2: {final_count2:,}")

        client1.close()
        client2.close()
        logger.info("🔒 Client connections closed successfully.")


if __name__ == "__main__":
    asyncio.run(run_migration())
