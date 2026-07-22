import asyncio
import logging
import time
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.errors import FloodWait, MessageIdInvalid, ChatAdminRequired, BadRequest, RPCError
from info import DATABASE_URI, DATABASE_NAME, BACKUP_CHANNEL

logger = logging.getLogger(__name__)

# --- Mongo Engine Layer Connection ---
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]

backup_files = db["backup_files"]
backup_progress = db["backup_progress"]

_migration_metrics = {
    "start_time": None,
    "processed_count": 0,
    "total_target": 0
}


async def init_backup_indexes():
    """Enforces explicit index parameters to maintain O(1) constraints on startup."""
    try:
        await backup_files.create_index("_id")
        await backup_progress.create_index("_id")
        logger.info("[BACKUP INDEX] Primary O(1) identity constraints successfully verified.")
    except Exception as e:
        logger.error(f"[BACKUP INDEX] Failed to enforce index parameters: {e}")


async def backup_new_file(file_id: str, file_ref: str, file_name: str, caption: str = None, 
                          file_type: str = "document", original_chat_id: int = None, 
                          original_msg_id: int = None) -> bool:
    """Core entry point hook for mirroring assets to the backup channel."""
    if BACKUP_CHANNEL == -100 or not BACKUP_CHANNEL:
        logger.error("[BACKUP] BACKUP_CHANNEL environment variable is missing or misconfigured.")
        return False

    if await is_duplicate(file_id):
        return False

    from dreamxbotz.Bot import dreamxbotz
    if not dreamxbotz:
        logger.error("[BACKUP] dreamxbotz client instance missing.")
        return False

    msg_id = await retry_upload(
        bot=dreamxbotz,
        file_id=file_id,
        file_name=file_name,
        caption=caption,
        file_type=file_type,
        chat_id=original_chat_id,
        msg_id=original_msg_id
    )

    if msg_id:
        await save_backup_record(file_id, msg_id, file_name, file_type)
        return True

    return False


async def is_duplicate(file_id: str) -> bool:
    doc = await backup_files.find_one({"_id": file_id}, {"_id": 1})
    return doc is not None


async def save_backup_record(file_id: str, backup_message_id: int, file_name: str, file_type: str):
    try:
        await backup_files.update_one(
            {"_id": file_id},
            {"$set": {
                "backup_message": backup_message_id, 
                "file_name": file_name,
                "file_type": file_type,
                "backup_date": datetime.now(timezone.utc)
            }},
            upsert=True
        )
    except Exception as e:
        logger.error(f"[BACKUP] Error tracking backup metadata: {e}")


async def retry_upload(bot, file_id: str, file_name: str, caption: str, file_type: str, 
                       chat_id: int = None, msg_id: int = None, max_retries: int = 5) -> int:
    for attempt in range(1, max_retries + 1):
        try:
            return await upload_cached_media(bot, file_id, file_name, caption, file_type, chat_id, msg_id)
        except FloodWait as e:
            wait_time = e.value + 3
            logger.warning(f"[BACKUP] Hit FloodWait. Sleeping for {wait_time}s (Attempt {attempt}/{max_retries}).")
            await asyncio.sleep(wait_time)
        except MessageIdInvalid:
            logger.error(f"[BACKUP] Source channel link broken for msg ID {msg_id}. Retrying with file_id.")
            chat_id = msg_id = None
        except ChatAdminRequired:
            logger.error(f"[BACKUP] Bot missing admin rights in BACKUP_CHANNEL: {BACKUP_CHANNEL}")
            return 0
        except (BadRequest, RPCError) as e:
            logger.warning(f"[BACKUP] Telegram API error: {e} (Attempt {attempt}/{max_retries}).")
            await asyncio.sleep(1.5 * attempt)
        except Exception as e:
            logger.exception(f"[BACKUP] Unexpected upload error on attempt {attempt}/{max_retries}")
            await asyncio.sleep(1.5 * attempt)
    return 0


async def upload_cached_media(bot, file_id: str, file_name: str, caption: str, file_type: str, 
                              chat_id: int = None, msg_id: int = None) -> int:
    final_caption = caption or f"<b>File Name:</b> <code>{file_name}</code>"

    if chat_id and msg_id:
        copied_msg = await bot.copy_message(
            chat_id=BACKUP_CHANNEL,
            from_chat_id=chat_id,
            message_id=msg_id,
            caption=final_caption
        )
        return copied_msg.id

    ft_lower = file_type.lower()
    if ft_lower == "video":
        sent_msg = await bot.send_video(chat_id=BACKUP_CHANNEL, video=file_id, caption=final_caption)
    elif ft_lower == "audio":
        sent_msg = await bot.send_audio(chat_id=BACKUP_CHANNEL, audio=file_id, caption=final_caption)
    elif ft_lower == "photo":
        sent_msg = await bot.send_photo(chat_id=BACKUP_CHANNEL, photo=file_id, caption=final_caption)
    else:
        sent_msg = await bot.send_document(chat_id=BACKUP_CHANNEL, document=file_id, caption=final_caption)

    return sent_msg.id


# --- Dynamic Migration Progress Trackers ---

async def get_progress() -> dict:
    doc = await backup_progress.find_one({"_id": "migration"})
    if doc:
        return {
            "last_db": doc.get("last_db", "Media"),
            "last_id": doc.get("last_id", None),
            "processed": doc.get("processed", 0)
        }
    return {"last_db": "Media", "last_id": None, "processed": 0}


async def save_progress(last_db: str, last_id: str, processed_count: int):
    await backup_progress.update_one(
        {"_id": "migration"},
        {"$set": {
            "last_db": last_db,
            "last_id": last_id,
            "processed": processed_count,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )


async def clear_progress():
    await backup_progress.delete_one({"_id": "migration"})


def init_eta_tracker(total_records: int, current_progress: int = 0):
    _migration_metrics["start_time"] = time.time()
    _migration_metrics["processed_count"] = current_progress
    _migration_metrics["total_target"] = total_records


async def log_progress(current_db: str, current_id: str, total_processed: int):
    await save_progress(current_db, current_id, total_processed)

    if not _migration_metrics["start_time"]:
        _migration_metrics["start_time"] = time.time()
        _migration_metrics["processed_count"] = total_processed
        return

    if total_processed % 500 != 0:
        return

    elapsed = time.time() - _migration_metrics["start_time"]
    delta_items = total_processed - _migration_metrics["processed_count"]

    if elapsed <= 0 or delta_items <= 0:
        return

    speed = delta_items / elapsed
    remaining = max(0, _migration_metrics["total_target"] - total_processed)
    eta_seconds = remaining / speed if speed > 0 else 0

    hours, remainder = divmod(int(eta_seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    eta_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    logger.info(
        f"🚀 [BACKUP PROGRESS] {total_processed:,}/{_migration_metrics['total_target']:,} "
        f"| Pool: {current_db} | Speed: {speed:.1f} files/sec | ETA: {eta_str}"
    )

    _migration_metrics["processed_count"] = total_processed
    _migration_metrics["start_time"] = time.time()
