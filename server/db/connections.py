# server/db/connections.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sumerllmqa")


# Remove the global _client, _db, _fs variables here!
# They caused the problem because they are initialized once by FastAPI
# but are useless/incorrect in the Celery worker process.

def get_mongo():
    """
    Creates and returns a new MongoDB client, database, and GridFS bucket.
    This pattern is safer for use in multi-process workers like Celery.
    """
    # Create the client instance directly inside the function
    client = AsyncIOMotorClient(MONGO_URI, maxPoolSize=5)  # Reduced pool size for task client
    db = client[DB_NAME]
    fs = AsyncIOMotorGridFSBucket(db)

    # We return the db and fs instances. The client will be managed internally.
    return db, fs

# NOTE: Your FastAPI lifespan startup should now also use this function
# to ensure consistent connection settings.