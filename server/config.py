import os

class Settings:
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "sumerllmqa")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MAX_BYTES: int = 25 * 1024 * 1024

settings = Settings()