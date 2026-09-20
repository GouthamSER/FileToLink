import re
import logging
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
            return
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name or "FileToLink"]
        self.col = self.db.users

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

db = Database(DATABASE_URI, DATABASE_NAME)
