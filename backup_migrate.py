import asyncio
import logging
import time
from datetime import datetime, timezone
from database.ia_filterdb import Media, Media2
from info import MULTIPLE_DB
from backup_utils import (
    backup_new_file, get_progress, save_progress, clear_progress,
    init_eta_tracker, log_progress, db
)

# Configure logging matching system profiles
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Atomic lock references
migration_lock = db["migration_lock"]

# Performance & Concurrency Config
CONCURRENCY_LIMIT = 5    # Safe conservative starting point
BATCH_SIZE = 500         # 500 documents per MongoDB cursor pull
SAVE_INTERVAL = 1000     # Flush progress every 1,000 files

_sync_stats = {
    "processed": 0,
    "success": 0,
    "failed": 0,
    "skipped": 0,
    "start_timestamp": None
}


async def acquire_migration_lock() -> bool:
    """Acquires an atomic database execution lock to prevent parallel worker loops."""
    try:
        await migration_lock.create_index("_id")
        result = await migration_lock.find_one_and_update(
            {"_id": "lock", "running": {"$ne": True}},
            {
                "$set": {
                    "running": True,
                    "acquired_at": datetime.now(timezone.utc)
                }
            },
            upsert=True,
            return_document=True
        )
        return result is not None
    except Exception as e:
        logger.error(f"[MIGRATION LOCK] Error acquiring execution lock: {e}")
        return False


async def release_migration_lock():
    """Sets execution lock status to inactive upon completion."""
    try:
        await migration_lock.update_one(
            {"_id": "lock"},
            {"$set": {"running": False, "released_at": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error(f"[MIGRATION LOCK] Error releasing execution lock: {e}")


async def count_total_files():
    print("COUNT STEP 1", flush=True)

    total = 0

    print("COUNT STEP 2", flush=True)
    total += await Media.count_documents({})
    print(f"PRIMARY COUNT = {total}", flush=True)

    if MULTIPLE_DB:
        print("COUNT STEP 3", flush=True)
        total += await Media2.count_documents({})
        print(f"TOTAL COUNT = {total}", flush=True)

    print("COUNT STEP 4", flush=True)
    return total


async def process_file_worker(file_doc, semaphore: asyncio.Semaphore, partition_label: str):
    """Processes an individual file document within a controlled worker semaphore."""
    async with semaphore:
        file_id = file_doc.file_id
        file_ref = getattr(file_doc, "file_ref", None)
        file_name = getattr(file_doc, "file_name", "Unknown File")
        caption = getattr(file_doc, "caption", None)
        file_type = getattr(file_doc, "file_type", "document")

        try:
            backed_up = await backup_new_file(
                file_id=file_id,
                file_ref=file_ref,
                file_name=file_name,
                caption=caption,
                file_type=file_type,
                original_chat_id=None,
                original_msg_id=None
            )
            return file_id, backed_up, True
        except Exception as e:
            logger.error(f"[{partition_label}] Worker failed for file {file_id}: {e}")
            return file_id, False, False


async def migrate_collection_partition(collection_class, partition_label: str, start_after_id: str) -> int:
    """Streams documents in batch chunks using concurrent async worker pools."""
    query_filter = {}
    if start_after_id:
        query_filter["file_id"] = {"$gt": start_after_id}
        logger.info(f"[{partition_label}] Resuming page timeline from token: {start_after_id}")

    cursor = collection_class.find(query_filter).sort("_id", 1)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    last_processed_id = start_after_id

    logger.info(
        f"[{partition_label}] Starting concurrent backup pipeline "
        f"(Concurrency: {CONCURRENCY_LIMIT} | Batch: {BATCH_SIZE})..."
    )

    while True:
        try:
            docs = await cursor.to_list(length=BATCH_SIZE)
        except Exception as e:
            logger.exception(f"[{partition_label}] Batch query execution failed: {e}")
            raise

        if not docs:
            break

        tasks = [process_file_worker(doc, semaphore, partition_label) for doc in docs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                _sync_stats["processed"] += 1
                _sync_stats["failed"] += 1
                logger.error(f"[{partition_label}] Worker raised unexpected unhandled exception: {res}")
                continue

            file_id, backed_up, success = res
            _sync_stats["processed"] += 1
            last_processed_id = file_id

            if success:
                if backed_up:
                    _sync_stats["success"] += 1
                else:
                    _sync_stats["skipped"] += 1
            else:
                _sync_stats["failed"] += 1

            if _sync_stats["processed"] % SAVE_INTERVAL == 0:
                await log_progress(
                    current_db=partition_label,
                    current_id=file_id,
                    total_processed=_sync_stats["processed"]
                )

                logger.info(
                    f"🚀 [PROGRESS] Total: {_sync_stats['processed']:,} | "
                    f"Success: {_sync_stats['success']:,} | Skipped: {_sync_stats['skipped']:,} | "
                    f"Failed: {_sync_stats['failed']:,}"
                )

    if last_processed_id:
        await save_progress(
            last_db=partition_label,
            last_id=str(last_processed_id),
            processed_count=_sync_stats["processed"]
        )

    return _sync_stats["processed"]


async def main():
    """Main orchestrator for historical backup sync."""
    print("ENTERED backup_migrate.main()", flush=True)
    logger.info(">>> ENTERED backup_migrate.main() <<<")

    _sync_stats["start_timestamp"] = time.time()

    try:
        print("MAIN STEP A", flush=True)

        total_files = await count_total_files()

        print(f"MAIN STEP B total={total_files}", flush=True)
        logger.info(f"📊 TOTAL HISTORICAL FILES DETECTED = {total_files:,}")
        print("MAIN STEP C", flush=True)

        if total_files == 0:
            logger.warning("[MIGRATION ABORTED] Collection is empty. Exiting.")
            return

        print("BEFORE get_progress()", flush=True)
        progress_state = await get_progress()
        print(f"AFTER get_progress() -> {progress_state}", flush=True)

        print("MAIN STEP D", flush=True)

        current_stage_db = progress_state["last_db"]
        last_id = progress_state["last_id"]
        _sync_stats["processed"] = progress_state["processed"]

        init_eta_tracker(total_files, _sync_stats["processed"])
        logger.info(f"[MIGRATION POOL] Total: {total_files:,} | Resuming from: {_sync_stats['processed']:,}")

        # --- Phase I: Primary Collection ---
        if current_stage_db == "Media":
            logger.info("[MIGRATION POOL] Extracting records from Primary Partition [Media]...")
            await migrate_collection_partition(
                collection_class=Media,
                partition_label="Media",
                start_after_id=last_id
            )
            current_stage_db = "Media2"
            last_id = None

        # --- Phase II: Secondary Collection ---
        if MULTIPLE_DB and current_stage_db == "Media2":
            logger.info("[MIGRATION POOL] Extracting records from Secondary Partition [Media2]...")
            await migrate_collection_partition(
                collection_class=Media2,
                partition_label="Media2",
                start_after_id=last_id
            )

        await clear_progress()

        runtime_duration = time.time() - _sync_stats["start_timestamp"]
        hours, remainder = divmod(int(runtime_duration), 3600)
        minutes, seconds = divmod(remainder, 60)

        logger.info(
            f"\n==================================================\n"
            f"       HISTORICAL MIGRATION PASS COMPLETED        \n"
            f"==================================================\n"
            f" ⏱️ Duration        : {hours}h {minutes}m {seconds}s\n"
            f" 📂 Total Processed : {_sync_stats['processed']:,}\n"
            f" ✅ Newly Backed Up : {_sync_stats['success']:,}\n"
            f" 🔁 Skipped (Dupes) : {_sync_stats['skipped']:,}\n"
            f" ❌ Failures         : {_sync_stats['failed']:,}\n"
            f"=================================================="
        )

    except asyncio.CancelledError:
        logger.warning("[MIGRATION WARNING] Worker loop cancelled by system signal.")
        raise
    except Exception as e:
        logger.exception(f"[MIGRATION PANIC] Critical error inside primary loop: {e}")


if __name__ == "__main__":
    asyncio.run(main())
