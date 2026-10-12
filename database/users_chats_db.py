import re
import logging
import datetime
# pyrefly: ignore [missing-import]
import motor.motor_asyncio
from info import DATABASE_NAME, DATABASE_URI

class Database:

    def __init__(self, uri, database_name):
        if not uri:
            logging.warning("DATABASE_URI not set. Running with database disabled.")
            self._client = None
            self.db = None
            self.col = None
            self.bans = None
            self._ban_cache = set()
            self._ban_loaded = True
            return
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name or "FileToLink"]
        self.col = self.db.users
        self.bans = self.db.banned_users
        self._ban_cache = set()
        self._ban_loaded = False

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
        )
    
    async def add_user(self, id, name):
        if self.col is None:
            return
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        if self.col is None:
            return True
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        if self.col is None:
            return 0
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        if self.col is None:
            return
        return self.col.find({})

    async def delete_user(self, user_id):
        if self.col is None:
            return
        await self.col.delete_many({'id': int(user_id)})

    # ───────────── ban system ─────────────
    async def _load_bans(self):
        if self._ban_loaded:
            return
        if self.bans is not None:
            try:
                async for doc in self.bans.find({}, {"id": 1}):
                    self._ban_cache.add(int(doc["id"]))
            except Exception as e:
                logging.error(f"Failed loading ban list: {e}")
                return  # retry next call
        self._ban_loaded = True

    async def is_banned(self, user_id):
        await self._load_bans()
        return int(user_id) in self._ban_cache

    async def ban_user(self, user_id, name="", username="", reason="", by=0):
        user_id = int(user_id)
        await self._load_bans()
        self._ban_cache.add(user_id)
        if self.bans is None:
            return
        await self.bans.update_one(
            {"id": user_id},
            {"$set": {
                "id": user_id,
                "name": name,
                "username": username,
                "reason": reason,
                "banned_by": by,
                "banned_at": datetime.datetime.utcnow(),
            }},
            upsert=True,
        )

    async def unban_user(self, user_id):
        user_id = int(user_id)
        await self._load_bans()
        was = user_id in self._ban_cache
        self._ban_cache.discard(user_id)
        if self.bans is not None:
            res = await self.bans.delete_one({"id": user_id})
            was = was or res.deleted_count > 0
        return was

    async def get_ban(self, user_id):
        if self.bans is None:
            return None
        return await self.bans.find_one({"id": int(user_id)})

    async def get_banned_users(self, limit=50):
        if self.bans is None:
            return []
        return await self.bans.find({}).sort("banned_at", -1).to_list(length=limit)

    async def total_banned_count(self):
        await self._load_bans()
        return len(self._ban_cache)


db = Database(DATABASE_URI, DATABASE_NAME)
