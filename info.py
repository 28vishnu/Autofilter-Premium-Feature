import re
import os
from os import environ, getenv
from Script import script

# Utility functions
id_pattern = re.compile(r'^.\d+$')

def is_enabled(value, default):
    if not value:
        return default
    if str(value).lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif str(value).lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# ============================
# Bot Information Configuration
# ============================
SESSION = environ.get('SESSION', 'royal_search')   # Session name for the bot
API_ID = int(environ.get('API_ID', '0'))           # API ID from my.telegram.org
API_HASH = environ.get('API_HASH', '')             # API Hash from my.telegram.org
BOT_TOKEN = environ.get('BOT_TOKEN', "")           # Bot token from @BotFather

# ============================
# Bot Settings Configuration
# ============================
CACHE_TIME = int(environ.get('CACHE_TIME', 300))    # Cache time in seconds (default: 5 minutes)
USE_CAPTION_FILTER = is_enabled(environ.get('USE_CAPTION_FILTER', "True"), True)  # Use caption filter for search results
INDEX_CAPTION = is_enabled(environ.get('SAVE_CAPTION', "True"), True)             # Save caption db when indexing

PICS = (environ.get('PICS', 'https://graph.org/file/56b5deb73f3b132e2bb73.jpg https://graph.org/file/5303692652d91d52180c2.jpg https://graph.org/file/425b6f46efc7c6d64105f.jpg https://graph.org/file/876867e761c6c7a29855b.jpg')).split()  # Sample pic
NOR_IMG = environ.get("NOR_IMG", "https://graph.org/file/e20b5fdaf217252964202.jpg")
MELCOW_PHOTO = environ.get("MELCOW_PHOTO", "https://graph.org/file/56b5deb73f3b132e2bb73.jpg")
SPELL_IMG = environ.get("SPELL_IMG", "https://graph.org/file/13702ae26fb05df52667c.jpg")
SUBSCRIPTION = (environ.get('SUBSCRIPTION', 'https://graph.org/file/242b7f1b52743938d81f1.jpg'))
FSUB_PICS = (environ.get('FSUB_PICS', 'https://graph.org/file/7478ff3eac37f4329c3d8.jpg https://graph.org/file/56b5deb73f3b132e2bb73.jpg')).split()  # Fsub pic

# ============================
# Admin, Channels & Users Configuration
# ============================
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()] # Replace with the actual admin ID(s) to add
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-100').split()]  # Channel id for auto indexing (make sure bot is admin)

LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-100'))  # Log channel id (make sure bot is admin)
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-100'))  # Bin channel id (make sure bot is admin)
BACKUP_CHANNEL = int(environ.get('BACKUP_CHANNEL', '-1002233445566')) # Target backup storage channel ID
PREMIUM_LOGS = int(environ.get('PREMIUM_LOGS', '-100'))  # Premium logs channel id
DELETE_CHANNELS = [int(dch) if id_pattern.search(dch) else dch for dch in environ.get('DELETE_CHANNELS', '-100').split()] #(make sure bot is admin)
support_chat_id = environ.get('SUPPORT_CHAT_ID', '-100')  # Support group id (make sure bot is admin)
reqst_channel = environ.get('REQST_CHANNEL_ID', '-100')  # Request channel id (make sure bot is admin)
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'https://t.me/')  # Support group link (make sure bot is admin)

# FORCE_SUB 
auth_req_channels = environ.get("AUTH_REQ_CHANNELS", "-100") # request to join Channel for force sub 
auth_channels     = environ.get("AUTH_CHANNELS", "-100")     # Channels for force sub

# ============================
# Payment Configuration
# ============================
QR_CODE = environ.get('QR_CODE', 'Your_Qr_Code')    # QR code image for payments
OWNER_UPI_ID = environ.get('OWNER_UPI_ID', 'ɴᴏ ᴀᴠᴀɪʟᴀʙʟᴇ ʀɪɢʜᴛ ɴᴏᴡ')    # Owner UPI ID for payments

STAR_PREMIUM_PLANS = {
    10: "7day",
    20: "15day",    
    40: "1month", 
    55: "45day",
    75: "60day",
}  # Premium plans with their respective durations in days

# ============================
# MongoDB Configuration
# ============================
DATABASE_URI = environ.get('DATABASE_URI', "")  # MongoDB URI for the database
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0") # Database name (default: cluster)
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'royal_files') # Collection name

# If MULTIPLE_DB Is True Then Fill DATABASE_URI2 Value Else You Will Get Error.
MULTIPLE_DB = is_enabled(environ.get('MULTIPLE_DB', "False"), False) # Type True For Turn On MULTIPLE DB FUNCTION 
DATABASE_URI2 = environ.get('DATABASE_URI2', "")  # MongoDB URI for the second database (if MULTIPLE_DB is True)

# ============================
# Movie Notification & Update Settings
# ============================
MOVIE_UPDATE_NOTIFICATION = is_enabled(environ.get('MOVIE_UPDATE_NOTIFICATION', 'False'), False)  # Notification On (True) / Off (False)
MOVIE_UPDATE_CHANNEL = int(environ.get('MOVIE_UPDATE_CHANNEL', '-100'))  # Notification sent to your channel
DREAMXBOTZ_IMAGE_FETCH = is_enabled(environ.get('DREAMXBOTZ_IMAGE_FETCH', 'True'), True)  # On (True) / Off (False)
LINK_PREVIEW = is_enabled(environ.get('LINK_PREVIEW', 'False'), False) # Shows link preview in notification msg instead of image
ABOVE_PREVIEW = is_enabled(environ.get('ABOVE_PREVIEW', 'True'), True) # Shows link preview above the text in notification msg
TMDB_API_KEY = environ.get('TMDB_API_KEY', '') # TMDB API Key from https://www.themoviedb.org/settings/api
TMDB_POSTER = is_enabled(environ.get('TMDB_POSTER', 'False'), False) # Shows TMDB poster in notification msg
LANDSCAPE_POSTER = is_enabled(environ.get('LANDSCAPE_POSTER', 'True'), True) # Shows landscape poster in notification msg

# ============================
# Verification Settings
# ============================
IS_VERIFY = is_enabled(environ.get('IS_VERIFY', 'False'), False)  # Verification On (True) / Off (False)
LOG_VR_CHANNEL = int(environ.get('LOG_VR_CHANNEL', '-100')) # Verification Channel Id 
LOG_API_CHANNEL = int(environ.get('LOG_API_CHANNEL', '-100')) # Dynamic Shortener Tracking Channel Details
VERIFY_IMG = environ.get("VERIFY_IMG", "https://telegra.ph/file/9ecc5d6e4df5b83424896.jpg")

TUTORIAL = environ.get("TUTORIAL", "https://t.me/technokrrish")   # Tutorial link for verification
TUTORIAL_2 = environ.get("TUTORIAL_2", "https://t.me/technokrrish")   # Second tutorial link for verification
TUTORIAL_3 = environ.get("TUTORIAL_3", "https://t.me/technokrrish")   # Third tutorial link for verification

# Verification Links APIs Configuration
SHORTENER_API = environ.get("SHORTENER_API", "2469484d258897da1dc9edaf4face6f466301f39") 
SHORTENER_WEBSITE = environ.get("SHORTENER_WEBSITE", "https://api.gplinks.com") 

SHORTENER_API2 = environ.get("SHORTENER_API2", "yei5ei5eie6id6d")  
SHORTENER_WEBSITE2 = environ.get("SHORTENER_WEBSITE2", "Shortner_Website_Url") 

SHORTENER_API3 = environ.get("SHORTENER_API3", "5353e68e866ee")  
SHORTENER_WEBSITE3 = environ.get("SHORTENER_WEBSITE3", "Shortner_Website_Url") 

TWO_VERIFY_GAP = int(environ.get('TWO_VERIFY_GAP', "1200")) # Time gap for two-step verification in seconds (default: 20 minutes)
THREE_VERIFY_GAP = int(environ.get('THREE_VERIFY_GAP', "54000"))    

# ============================
# Channel & Group Links Configuration
# ============================
GRP_LNK = environ.get('GRP_LNK', 'https://t.me/cinegrup') # Group link for the bot
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/luffydev2k') # Owner link for the bot
UPDATE_CHNL_LNK = environ.get('UPDATE_CHNL_LNK', 'https://t.me/cineofcl') # Update channel link for the bot

# ============================
# User Configuration
# ============================
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]
AUTH_USERS = (auth_users + ADMINS) if auth_users else []
PREMIUM_USER = [int(user) if id_pattern.search(user) else user for user in environ.get('PREMIUM_USER', '').split()]

# ============================
# Miscellaneous Configuration
# ============================
ULTRA_FAST_MODE = is_enabled(environ.get('ULTRA_FAST_MODE', "False"), True) # Set to True for fast search

MAX_B_TN = environ.get("MAX_B_TN", "5") # Maximum number of buttons in a row (default: 5)
PORT = int(environ.get("PORT", "8080"))  # Port for the web server (default: 8080)
MSG_ALRT = environ.get('MSG_ALRT', 'Share & Support Us ♥️') # Alert message for users
DELETE_TIME = int(environ.get("DELETE_TIME", "300"))  # deletion time in seconds
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")   # Custom caption for files
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION) # Custom caption for batch files
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", f"{script.IMDB_TEMPLATE_TXT}")     # Custom IMDB template 
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None) # Maximum number of elements in a list
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))  # Index Request Channel ID
NO_RESULTS_MSG = is_enabled(environ.get("NO_RESULTS_MSG", "True"), True)  # Toggle no results logging
MAX_BTN = is_enabled((environ.get('MAX_BTN', "True")), True)    
P_TTI_SHOW_OFF = is_enabled((environ.get('P_TTI_SHOW_OFF', "False")), False)    
IMDB = is_enabled((environ.get('IMDB', "False")), False)    
TMDB_ON_SEARCH = is_enabled((environ.get('TMDB_ON_SEARCH', "False")), False)    
AUTO_FFILTER = is_enabled((environ.get('AUTO_FFILTER', "True")), True) 
AUTO_DELETE = is_enabled((environ.get('AUTO_DELETE', "True")), True) 
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False) 
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), True) 
MELCOW_NEW_USERS = is_enabled((environ.get('MELCOW_NEW_USERS', "False")), False) 
PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "False")), False) 
PM_SEARCH = is_enabled(environ.get('PM_SEARCH', "True"), True)  
EMOJI_MODE = is_enabled(environ.get('EMOJI_MODE', "False"), False)  
BUTTON_MODE = is_enabled((environ.get('BUTTON_MODE', "False")), False) 
STREAM_MODE = is_enabled(environ.get('STREAM_MODE', "False"), False) 
PREMIUM_STREAM_MODE = is_enabled(environ.get('PREMIUM_STREAM_MODE', "False"), False) 

# ============================
# Bot Configuration
# ============================
AUTH_REQ_CHANNELS = [int(ch) for ch in auth_req_channels.split() if ch and id_pattern.match(ch)] 
AUTH_CHANNELS = [int(ch) for ch in auth_channels.split() if ch and id_pattern.match(ch)]
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None
LANGUAGES = {"ᴍᴀʟᴀʏᴀʟᴀᴍ":"mal","ᴛᴀᴍɪʟ":"tam","ᴇɴɢʟɪsʜ":"eng","ʜɪɴᴅɪ":"hin","ᴛᴇʟᴜɢᴜ":"tel","ᴋᴀɴɴᴀᴅᴀ":"kan","ɢᴜᴊᴀʀᴀᴛɪ":"guj","ᴍᴀʀᴀᴛʜɪ":"mar","ᴘᴜɴᴊᴀʙɪ":"pun"}
QUALITIES = ["360P", "480P", "720P", "1080P", "1440P", "2160P", "4K"]

SEASON_COUNT = 12
SEASONS = [f"S{str(i).zfill(2)}" for i in range(1, SEASON_COUNT + 1)]

BAD_WORDS = {
    "PrivateMovieZ", "toonworld4all", "themoviesboss", "1tamilmv", "tamilblasters",
    "1tamilblasters", "skymovieshd", "extraflix", "hdm2", "moviesmod", "hdhub4u",
    "mkvcinemas", "primefix", "join", "www", "villa", "tg", "original"
} 

# ============================
# Server & Web Configuration
# ============================
NO_PORT = is_enabled(environ.get('NO_PORT', "False"), False)
APP_NAME = None
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = environ.get('APP_NAME')
else:
    ON_HEROKU = False
BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
FQDN = str(getenv('FQDN', BIND_ADRESS)) if not ON_HEROKU or getenv('FQDN') else APP_NAME+'.herokuapp.com'
URL = "https://{}/".format(FQDN) if ON_HEROKU or NO_PORT else "https://{}/".format(FQDN, PORT)
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
WORKERS = int(environ.get('WORKERS', '4'))
SESSION_NAME = str(environ.get('SESSION_NAME', 'dreamXBotz'))
MULTI_CLIENT = False
name = str(environ.get('name', 'DREAMXBOTZ'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
HAS_SSL = is_enabled(getenv('HAS_SSL', "True"), True)
if HAS_SSL:
    URL = "https://{}/".format(FQDN)
else:
    URL = "http://{}/".format(FQDN)

# ============================
# Reactions Configuration
# ============================
REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"]

# ============================
# Commands Bot
# ============================
Bot_cmds = {
    "start": "Sᴛᴀʀᴛ Mᴇ Bᴀʙʏ",
    "stats": "Gᴇᴛ Bᴏᴛ Sᴛᴀᴛs",
    "alive": " Cʜᴇᴄᴋ Bᴏᴛ Aʟɪᴠᴇ ᴏʀ Nᴏᴛ ",
    "settings": "ᴄʜᴀɴɢᴇ sᴇᴛᴛɪɴɢs",
    "id": "ɢᴇᴛ ɪᴅ ᴛᴇʟᴇɢʀᴀᴍ ",
    "info": "Gᴇᴛ Usᴇʀ ɪɴғᴏ ",
    "del_msg": "ʀᴇᴍᴏᴠᴇ ғɪʟᴇ ɴᴀᴍᴇ ᴄᴏʟʟᴇᴄᴛɪᴏɴ ɴᴏтɪғɪᴄᴀᴛɪᴏɴ...",
    "movie_update": "ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "pm_search": "ᴘᴍ sᴇᴀʀᴄʜ ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "trendlist": "Gᴇᴛ Tᴏᴘ Tʀᴀɴᴅɪɴɢ Sᴇᴀʀᴄʜ Lɪsᴛ",
    "broadcast": "ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜꜱᴇʀꜱ.",
    "grp_broadcast": "ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴄᴏɴɴᴇᴄᴛᴇᴅ ɢʀᴏᴜᴘs",
    "send": "ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ᴀ ᴘᴀʀᴛɪᴄᴜʟᴀʀ ᴜꜱᴇʀ.",
    "add_premium": "ᴀᴅᴅ ᴀɴʏ ᴜꜱᴇʀ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ.",
    "remove_premium": "ʀᴇᴍᴏᴠᴇ ᴀɴʏ ᴜꜱᴇʀ ꜰʀᴏᴍ ᴘʀᴇᴍɪᴜᴍ.",
    "premium_users": "ɢᴇᴛ ʟɪꜱᴛ ᴏꜰ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ.",
    "restart": "ʀᴇꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ.",
    "group_cmd": "ɢʀᴏᴜᴘ ᴄᴏᴍᴍᴀɴᴅ ʟɪsᴛ",
    "admin_cmd": "ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs ʟɪsᴛ.",
    "reset_group": "Group Setting Default",
    "trial_reset": "User Trial Reset"
}

# Core Fallback Management Strategy Setup
if not MULTIPLE_DB:
    DATABASE_URI2 = DATABASE_URI

# ============================
# Logs Configuration
# ============================
LOG_STR = "Current Customized Configurations are:-\n"
LOG_STR += ("IMDB Results are enabled, Bot will be showing imdb details for your queries.\n" if IMDB else "IMDB Results are disabled.\n")
LOG_STR += ("P_TTI_SHOW_OFF found, Users will be redirected to send /start to Bot PM instead of sending file directly.\n" if P_TTI_SHOW_OFF else "P_TTI_SHOW_OFF is disabled, files will be sent in PM instead of starting the bot.\n")
LOG_STR += ("BUTTON_MODE is found, filename and file size will be shown in a single button instead of two separate buttons.\n" if BUTTON_MODE else "BUTTON_MODE is disabled, filename and file size will be shown as different buttons.\n")
LOG_STR += (f"CUSTOM_FILE_CAPTION enabled with value {CUSTOM_FILE_CAPTION}, your files will be sent along with this customized caption.\n" if CUSTOM_FILE_CAPTION else "No CUSTOM_FILE_CAPTION Found, Default captions of file will be used.\n")
LOG_STR += ("Long IMDB storyline enabled." if LONG_IMDB_DESCRIPTION else "LONG_IMDB_DESCRIPTION is disabled, Plot will be shorter.\n")
LOG_STR += ("Spell Check Mode is enabled, bot will be suggesting related movies if movie name is misspelled.\n" if SPELL_CHECK_REPLY else "Spell Check Mode is disabled.\n")
