import asyncio
import logging
import time
from datetime import datetime, timezone
from database.ia_filterdb import Media, Media2
from info import MULTIPLE_DB
from pymongo.errors import DuplicateKeyError
from backup_utils import (
    backup_new_file, get_progress, save_progress, clear_progress,
    init_eta_tracker, log_progress, db
)

# Configure elegant logging formats matching system defaults
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# References for atomic processing locks
migration_lock = db["migration_lock"]

# Structural Performance Registry Matrix
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
        # Enforce tracking index on lock collection safely before atomic operation
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
        logger.error(f"[MIGRATION LOCK] Error acquiring migration lock state: {e}")
        return False


async def release_migration_lock():
    """Gently sets the execution lock status to inactive upon completion."""
    try:
        await migration_lock.update_one(
            {"_id": "lock"},
            {"$set": {"running": False, "released_at": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error(f"[MIGRATION LOCK] Error releasing execution lock string: {e}")


async def count_total_files() -> int:
    """Computes total storage record dimensions safely by accessing the uMongo counting framework directly."""
    total = 0
    try:
        total += await Media.count_documents({})
        if MULTIPLE_DB:
            total += await Media2.count_documents({})
    except Exception as e:
        logger.error(f"[MIGRATION COUNT] Error calculating collection boundaries: {e}")
    return total


async def migrate_collection_partition(collection_class, partition_label: str, start_after_id: str) -> int:
    """Streams documents sequentially using standard project array structures to protect container execution."""
    # Edit 4: Diagnostic entry checkpoint at the function gate
    print(f"ENTER migrate_collection_partition({partition_label})", flush=True)

    query_filter = {}

    # Enforce target boundary criteria using the model-mapped attribute name
    if start_after_id:
        query_filter["file_id"] = {"$gt": start_after_id}
        logger.info(f"[{partition_label}] Resuming page timeline from token slice: {start_after_id}")

    logger.info(f"[{partition_label}] Creating data cursor...")
    cursor = collection_class.find(query_filter).sort("file_id", 1)
    logger.info(f"[{partition_label}] Cursor created successfully.")

    # Convert cursor stream to a full sequence array matching the rest of the project handlers
    logger.info(f"[{partition_label}] Resolving database elements into list array...")
    docs = await cursor.to_list(length=None)
    logger.info(f"[{partition_label}] Successfully retrieved {len(docs)} array documents from collection.")

    local_loop_counter = 0
    last_processed_id = start_after_id

    logger.info(f"[{partition_label}] Beginning data processing loop...")

    # Iterate through extracted structures safely using standard sequential steps
    for file_doc in docs:
        local_loop_counter += 1
        _sync_stats["processed"] += 1

        current_id = file_doc.file_id
        last_processed_id = current_id

        try:
            # Cleanly extract fields using valid uMongo document object names
            file_id = file_doc.file_id
            file_ref = getattr(file_doc, "file_ref", None)
            file_name = getattr(file_doc, "file_name", "Unknown File")
            caption = getattr(file_doc, "caption", None)
            file_type = getattr(file_doc, "file_type", "document")

            # Dispatch transaction to backup layer utilities
            backed_up = await backup_new_file(
                file_id=file_id,
                file_ref=file_ref,
                file_name=file_name,
                caption=caption,
                file_type=file_type,
                original_chat_id=None,
                original_msg_id=None
            )

            # backup_new_file returns a boolean value (True if saved, False if skipped)
            if backed_up:
                _sync_stats["success"] += 1
            else:
                _sync_stats["skipped"] += 1

            # Flush progress snapshots systematically every 100 iterations
            if _sync_stats["processed"] % 100 == 0:
                await log_progress(
                    current_db=partition_label,
                    current_id=current_id,
                    total_processed=_sync_stats["processed"]
                )

            # High-Volume Health Progress Check (Every 1000 items)
            if _sync_stats["processed"] % 1000 == 0:
                logger.info(
                    f"[HEALTH CHECK] Progress: {_sync_stats['processed']} | "
                    f"Success: {_sync_stats['success']} | Skipped: {_sync_stats['skipped']} | "
                    f"Failed: {_sync_stats['failed']}"
                )

            # Throttling guard to preserve Telegram endpoint balance limits
            if local_loop_counter % 50 == 0:
                await asyncio.sleep(0.2)

        except Exception as e:
            _sync_stats["failed"] += 1
            logger.error(f"[{partition_label} ERROR] Processing failed for document ID {current_id}: {e}")
            continue

    # Boundary Fix: Always force-save trailing incomplete progress chunks at partition completion
    if last_processed_id:
        await save_progress(
            last_db=partition_label,
            last_id=str(last_processed_id),
            processed_count=_sync_stats["processed"]
        )

    return _sync_stats["processed"]


async def main():
    """Main application orchestrator layer handling startup validations and processing chains."""
    print(">>> ENTERED backup_migrate.main() <<<", flush=True)
    logger.info(">>> ENTERED backup_migrate.main() <<<")

    _sync_stats["start_timestamp"] = time.time()
    logger.info("[MIGRATION INITIATED] Verifying system locks and environmental layers...")

    # Enforce single-worker running constraints atomically
    if not await acquire_migration_lock():
        print("[MIGRATION ABORTED] Lock collision detected on cluster.", flush=True)
        logger.critical("[MIGRATION ABORTED] Another migration instance is currently active on the cluster.")
        return

    try:
        # Calculate baseline data scope boundaries
        total_files = await count_total_files()

        print(f"TOTAL FILES DETECTED = {total_files}", flush=True)
        logger.info(f"TOTAL FILES DETECTED = {total_files}")

        if total_files == 0:
            logger.warning("[MIGRATION ABORTED] Target indexing pools evaluate to 0 entries. Exiting loop.")
            return

        # Extract system recovery markers from prior snapshot states
        progress_state = await get_progress()
        
        # Edit 1: Step 1 Placement
        print("STEP 1: get_progress() completed", flush=True)

        current_stage_db = progress_state["last_db"]
        last_id = progress_state["last_id"]
        _sync_stats["processed"] = progress_state["processed"]

        # Synchronize interval tracking clocks
        init_eta_tracker(total_files, _sync_stats["processed"])
        
        # Edit 2: Step 2 Placement
        print("STEP 2: init_eta_tracker() completed", flush=True)

        logger.info(f"[MIGRATION MATRIX] Total Files: {total_files} | Resuming from: {_sync_stats['processed']}")

        # --- Phase I: Primary Cluster Sync Task ---
        if current_stage_db == "Media":
            logger.info("[MIGRATION POOL] Extracting records from Primary Cluster Partition [Media]...")
            
            # Edit 3: Step 3 Placement
            print("STEP 3: About to migrate Media", flush=True)

            await migrate_collection_partition(
                collection_class=Media,
                partition_label="Media",
                start_after_id=last_id
            )
            # Progress Tracking State Machine Transition Pass
            current_stage_db = "Media2"
            last_id = None

        # --- Phase II: Secondary Cluster Sync Task ---
        if MULTIPLE_DB and current_stage_db == "Media2":
            logger.info("[MIGRATION POOL] Extracting records from Secondary Cluster Partition [Media2]...")
            await migrate_collection_partition(
                collection_class=Media2,
                partition_label="Media2",
                start_after_id=last_id
            )

        # Drop state sync tracking documents once full sync targets are achieved
        await clear_progress()

        # Calculate process completion duration metrics
        runtime_duration = time.time() - _sync_stats["start_timestamp"]
        hours, remainder = divmod(int(runtime_duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

        logger.info(
            f"\n"
            f"==================================================\n"
            f"       HISTORICAL MIGRATION PASS COMPLETED        \n"
            f"==================================================\n"
            f" 🗓️ Duration : {duration_str}\n"
            f" 📂 Total Evaluated : {_sync_stats['processed']}\n"
            f" ✅ Saved Backups  : {_sync_stats['success']}\n"
            f" 🔁 Skipped (Dupe) : {_sync_stats['skipped']}\n"
            f" ❌ Fault Failures : {_sync_stats['failed']}\n"
            f"=================================================="
        )

    except asyncio.CancelledError:
        logger.warning("[MIGRATION WARNING] Execution loop cancelled by system signal (SIGTERM/SIGINT). Progress saved.")
        raise
    except Exception as e:
        logger.exception(f"[MIGRATION PANIC] Critical error encountered inside primary execution loop: {e}")
    finally:
        # Ensure the processing lock is safely flipped to False regardless of completion status
        await release_migration_lock()


if __name__ == "__main__":
    asyncio.run(main())
