import asyncio
import sqlite3
import json
import os
from src.database.connection import DatabaseManager
from src.database.crud import GuildCRUD

async def check_settings():
    db_path = "data/musicbot.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    # Just instantiate, execute/fetch_* will handle connection
    db = DatabaseManager(db_path)
    
    # Target Guild
    guild_id = 1434522972890202146
    
    print(f"Checking settings for guild {guild_id}...")
    
    # 1. Check ALL settings for this guild
    print("\n--- All Settings for Target Guild ---")
    guild_crud = GuildCRUD(db)
    settings = await guild_crud.get_all_settings(guild_id)
    for k, v in settings.items():
        print(f"{k}: {v} (Type: {type(v)})")

    # 2. Check settings for ALL guilds
    print("\n--- Checking ALL Guilds ---")
    rows = await db.fetch_all("SELECT DISTINCT guild_id FROM guild_settings")
    for row in rows:
        gid = row["guild_id"]
        # Try to get name
        guild_row = await db.fetch_one("SELECT name FROM guilds WHERE id = ?", (gid,))
        name = guild_row["name"] if guild_row else "Unknown"
        
        print(f"\nGuild: {name} (ID: {gid})")
        settings = await guild_crud.get_all_settings(gid)
        if "twenty_four_seven" in settings:
             print(f"  -> twenty_four_seven: {settings['twenty_four_seven']}")
        else:
             print(f"  -> twenty_four_seven: NOT SET (Defaults to False)")

    await db.close()

if __name__ == "__main__":
    asyncio.run(check_settings())
