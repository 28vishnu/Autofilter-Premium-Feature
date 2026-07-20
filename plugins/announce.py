import re
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import RPCError

# Import configuration variables from info.py
from info import AUTH_CHANNELS

logger = logging.getLogger(__name__)


def get_human_size(size_bytes: int) -> str:
    """Formats raw byte counts into clean MB/GB strings."""
    if not size_bytes:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def parse_filename_details(file_name: str, file_size: int = 0) -> dict:
    """Extracts Title, Quality, Language, Codec, Year, and File Size from a raw media filename."""
    # 1. Clean extension
    clean_name = re.sub(r'\.(mkv|mp4|avi|mov)$', '', file_name, flags=re.IGNORECASE)

    # 2. Extract Release Year
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', clean_name)
    year = year_match.group(0) if year_match else None

    # 3. Extract Quality / Format
    quality_match = re.search(
        r'\b(480p|720p|1080p|2160p|4k|hdrip|webrip|web-dl|bluray|hdtv)\b', 
        clean_name, 
        re.IGNORECASE
    )
    quality = quality_match.group(0).upper() if quality_match else "HD Quality"

    # 4. Extract Codec / Audio
    codec_match = re.search(
        r'\b(x264|x265|hevc|h264|h265|aac|dts|dd5\.1|ac3)\b',
        clean_name,
        re.IGNORECASE
    )
    codec = codec_match.group(0).upper() if codec_match else "x264"

    # 5. Extract Common Languages
    languages_found = re.findall(
        r'\b(telugu|tamil|hindi|malayalam|kannada|english|multi|sub|dub|dubbed)\b', 
        clean_name, 
        re.IGNORECASE
    )
    language = " / ".join(dict.fromkeys([l.capitalize() for l in languages_found])) if languages_found else "Multi Audio"

    # 6. Extract Clean Movie Title (Truncate at first technical tag or resolution)
    movie_name = re.split(
        r'\b(480p|720p|1080p|2160p|4k|webrip|web-dl|bluray|hdtv|x264|x265|hevc|aac)\b', 
        clean_name, 
        flags=re.IGNORECASE
    )[0]
    
    # Remove leading tags (like @channel names), dots, underscores, and trailing symbols
    movie_name = re.sub(r'@[A-Za-z0-9_]+', '', movie_name)
    movie_name = re.sub(r'[._]', ' ', movie_name).strip(" -[]()")

    return {
        "title": movie_name if movie_name else clean_name,
        "year": year,
        "quality": quality,
        "codec": codec,
        "language": language,
        "size": get_human_size(file_size)
    }


@Client.on_message(filters.command("announce") & filters.channel)
async def announce_handler(client: Client, message: Message):
    # 1. Verify command is used in reply to a message or file
    reply_msg = message.reply_to_message
    if not reply_msg:
        return await message.reply_text(
            "<b>⚠️ Please reply to a message or file with <code>/announce</code> to broadcast it.</b>"
        )

    # 2. Target channel check using AUTH_CHANNELS[0]
    if not AUTH_CHANNELS:
        return await message.reply_text("<b>❌ AUTH_CHANNELS is not configured in info.py.</b>")

    target_chat = AUTH_CHANNELS[0]

    status_msg = await message.reply_text("<b>⏳ Processing professional announcement...</b>")

    try:
        raw_filename = "Unknown Media File"
        file_size = 0
        media_thumb = None

        # Extract media attributes and thumbnail from the replied message
        if reply_msg.media:
            for media_type in ("video", "document", "audio", "photo"):
                media_obj = getattr(reply_msg, media_type, None)
                if media_obj:
                    raw_filename = getattr(media_obj, "file_name", raw_filename)
                    file_size = getattr(media_obj, "file_size", 0)
                    
                    # Clean thumbnail resolution lookup
                    thumb_obj = getattr(media_obj, "thumbs", None)
                    if thumb_obj and len(thumb_obj) > 0:
                        media_thumb = thumb_obj[-1].file_id
                    elif media_type == "photo":
                        media_thumb = media_obj.file_id
                    break
        elif reply_msg.text:
            raw_filename = reply_msg.text.strip()

        # Parse technical parameters
        details = parse_filename_details(raw_filename, file_size)

        # Build clean hashtag string
        clean_tag = re.sub(r'[^a-zA-Z0-9]', '', details['title'])
        hashtags = f"#{clean_tag} #{details['quality']} #{details['codec']}"

        # Construct professional post layout
        announce_text = (
            f"<b>🔥 NEW FILE ADDED 🔥</b>\n\n"
            f"<b>🎬 Movie Title:</b> <code>{details['title']}</code>\n"
            f"<b>📅 Release Year:</b> <code>{details['year'] or 'N/A'}</code>\n"
            f"<b>📺 Quality & Codec:</b> <code>{details['quality']} [{details['codec']}]</code>\n"
            f"<b>🎧 Audio Language:</b> <code>{details['language']}</code>\n"
            f"<b>📂 File Size:</b> <code>{details['size']}</code>\n\n"
            f"<i>✨ Click the button below to get your file instantly in the bot!</i>\n\n"
            f"<b>{hashtags}</b>"
        )

        # Direct API call replaces temp.U_NAME dependency
        bot_info = await client.get_me()
        bot_username = bot_info.username
        search_query = details['title'].replace(' ', '-')
        
        button = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📂 GET FILES 📂",
                    url=f"https://t.me/{bot_username}?start=getfile-{search_query}"
                )
            ]
        ])

        # Send post with thumbnail/photo if available, otherwise fall back to formatted text
        if media_thumb:
            sent_announcement = await client.send_photo(
                chat_id=target_chat,
                photo=media_thumb,
                caption=announce_text,
                reply_markup=button,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            sent_announcement = await client.send_message(
                chat_id=target_chat,
                text=announce_text,
                reply_markup=button,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        await status_msg.edit_text(
            f"<b>✅ Announcement successfully posted!</b>\n\n"
            f"<b>📢 Target Channel:</b> <code>{target_chat}</code>\n"
            f"<b>🆔 Message ID:</b> <code>{sent_announcement.id}</code>"
        )

    except RPCError as e:
        logger.exception("Failed to send announcement: %s", e)
        await status_msg.edit_text(f"<b>❌ Telegram API Error:</b> <code>{e}</code>")
    except Exception as e:
        logger.exception("Unexpected error in announce command: %s", e)
        await status_msg.edit_text(f"<b>❌ Error:</b> <code>{e}</code>")
