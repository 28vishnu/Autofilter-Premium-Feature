import sys
import glob
import importlib
from pathlib import Path
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
import time
from pyrogram.errors import FloodWait
import asyncio
from datetime import date, datetime
import pytz
from aiohttp import web
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server, check_expired_premium, keep_alive
from dreamxbotz.Bot import dreamxbotz
from dreamxbotz.util.keepalive import ping_server
from dreamxbotz.Bot.clients import initialize_clients
from PIL import Image

# Core backup core validation and migration hooks integration layers
from backup_utils import init_backup_indexes
from backup_migrate import main as migrate_main

Image.MAX_IMAGE_PIXELS = 500_000_000

import logging
import logging.config

# Enforce logging profiles
try:
    logging.config.fileConfig('logging.conf')
except Exception:
    pass
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.WARNING)

botStartTime = time.time()
ppath = "plugins/*.py"
files = glob.glob(ppath)

# Background Worker: Runs migration periodically without blocking bot execution
async def migration_worker_loop(interval_seconds: int = 600):
    """
    Continuous background task for database migration and capacity checks.
    Runs every `interval_seconds` (default: 10 minutes).
    """
    logger = logging.getLogger("MigrationWorker")
    logger.info("⚡ Background migration worker initialized.")
    
    while True:
        try:
            logger.info("🔍 Running scheduled backup migration check...")
            await migrate_main()
            logger.info("✅ Scheduled migration cycle completed.")
        except asyncio.CancelledError:
            logger.info("🛑 Background migration worker stopping...")
            break
        except Exception:
            logger.exception("❌ Background migration worker encountered an error.")
        
        # Wait for the next scheduled interval
        await asyncio.sleep(interval_seconds)


async def dreamxbotz_start():
    # 1. Added explicit flush on baseline launch string
    print('\n\nInitalizing DreamxBotz', flush=True)

    print("STEP A", flush=True)
    await dreamxbotz.start()
    print("STEP B", flush=True)

    bot_info = await dreamxbotz.get_me()
    print("STEP C", flush=True)

    dreamxbotz.username = bot_info.username
    await initialize_clients()

    print("STEP D", flush=True)
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print("DreamxBotz Imported => " + plugin_name, flush=True)

    print("STEP E", flush=True)
    if ON_HEROKU:
        asyncio.create_task(ping_server()) 

    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats

    # 5. Primary collections indexing evaluation wrap points
    print("STEP F", flush=True)
    await Media.ensure_indexes()
    print("STEP G", flush=True)

    # Verify backup O(1) matching parameters safely on the cluster
    await init_backup_indexes()

    if MULTIPLE_DB:
        await Media2.ensure_indexes()
        print("Multiple Database Mode On. Now Files Will Be Save In Second DB If First DB Is Full", flush=True)
    else:
        print("Single DB Mode On ! Files Will Be Save In First Database", flush=True)

    me = await dreamxbotz.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention
    dreamxbotz.username = '@' + me.username

    dreamxbotz.loop.create_task(check_expired_premium(dreamxbotz))

    logging.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    logging.info(LOG_STR)
    logging.info(script.LOGO)

    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M:%S %p")

    await dreamxbotz.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(temp.B_LINK, today, time_str))

    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()

    dreamxbotz.loop.create_task(keep_alive())

    # 6. Non-blocking background worker loop scheduled on asyncio loop
    print("STEP H", flush=True)
    dreamxbotz.loop.create_task(migration_worker_loop(interval_seconds=600))
    print("STEP I", flush=True)

    await idle()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    while True:
        try:
            loop.run_until_complete(dreamxbotz_start())
            break  
        except FloodWait as e:
            print(f"FloodWait! Sleeping for {e.value} seconds.", flush=True)
            time.sleep(e.value) 
        except KeyboardInterrupt:
            logging.info('Service Stopped Bye 👋')
            break
        except Exception as e:
            # 7. Enhanced Trace Catcher: Print clean explicit exception state stacks to stdout
            import traceback
            traceback.print_exc()
            logging.exception("Fatal startup error")
            break
