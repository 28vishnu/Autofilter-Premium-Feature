from pyrogram import Client, filters, enums
from database.ia_filterdb import save_file
from info import CHANNELS
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.chat(CHANNELS))
async def auto_index(client, message):
    try:
        if not message.media:
            return

        if message.media not in [
            enums.MessageMediaType.VIDEO,
            enums.MessageMediaType.DOCUMENT,
            enums.MessageMediaType.AUDIO
        ]:
            return

        media = getattr(message, message.media.value)

        if not media:
            return

        media.file_type = message.media.value
        media.caption = message.caption

        ok, code = await save_file(media)

        if ok:
            logger.info(f"[AUTO INDEX] {media.file_name}")

    except Exception as e:
        logger.exception(e)