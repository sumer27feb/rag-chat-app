# main.py
import io
import os
from datetime import datetime, timezone
import uuid
from enum import Enum
from typing import List, Literal, Annotated

import uvicorn
from bson import ObjectId
from pymongo import ASCENDING
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, status, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, EmailStr, constr, Field
from pydantic.types import StringConstraints

from auth import router as auth_router  # <- our auth routes
from rag import router as rag_router  # <- our auth routes

from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

# -------- Config --------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sumerllmqa")

# -------- Lifespan (startup/shutdown) --------
async def lifespan(app: FastAPI):
    # Startup
    app.mongodb_client = AsyncIOMotorClient(MONGO_URI)
    app.state.db = app.mongodb_client[DB_NAME]
    app.state.fs = AsyncIOMotorGridFSBucket(app.state.db)

    # Redis for rate limiting
    redis_client = redis.from_url("redis://localhost:6379", encoding="utf8", decode_responses=True)
    await FastAPILimiter.init(redis_client)

    print("✅ Connected to MongoDB")
    yield
    # Shutdown
    app.mongodb_client.close()
    print("❌ Disconnected from MongoDB")


# -------- App --------
app = FastAPI(lifespan=lifespan)

# CORS (Vite dev server)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers

app.include_router(auth_router)
app.include_router(rag_router)


# -------- Schemas --------
class ChatCreate(BaseModel):
    user_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]

    class Config:
        extra = "forbid"


class MessageCreate(BaseModel):
    role: Literal["user", "bot"]
    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]


# -------- Helpers --------
def users_col(req: Request):
    return req.app.state.db["users"]

def chats_col(req: Request):
    return req.app.state.db["chats"]

def messages_col(req: Request):
    return req.app.state.db["messages"]

def users_chat_list_col(req: Request):
    return req.app.state.db["users_chat_list"]

async def get_chat_or_404(chat_id: str):
    chat = await app.state.db.chats.find_one({"chat_id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="chat not found")
    return chat


# -------- Endpoints (async) --------
@app.post("/chatsCreate")
async def create_chat(data: ChatCreate, request: Request):
    # Ensure user exists
    user = await users_col(request).find_one({"user_id": data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    chat_id = str(uuid.uuid4())
    chat_doc = {
        "user_id": data.user_id,
        "chat_id": chat_id,         # your external chat id (e.g., uuid from FE)
        "title": None,
        "pdf_file_id": None,             # GridFS file _id (ObjectId) once uploaded
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await chats_col(request).insert_one(chat_doc)

    # Upsert into users_chat_list
    await users_chat_list_col(request).update_one(
        {"user_id": data.user_id},
        {"$push": {"chat_ids": chat_id}},
        upsert=True,
    )
    return {"chat_id": chat_id}

@app.get("/users/{user_id}/chats")
async def list_user_chats(user_id: str, request: Request):
    cursor = chats_col(request).find({"user_id": user_id}).sort("updated_at", -1)
    chats = []
    async for c in cursor:
        # Drop Mongo's internal _id field
        c.pop("_id", None)

        # Ensure chat_id is string (since you store as UUID string, no conversion needed)
        if "chat_id" in c:
            c["chat_id"] = str(c["chat_id"])

        # Convert datetime fields to ISO
        if isinstance(c.get("created_at"), datetime):
            c["created_at"] = c["created_at"].isoformat()
        if isinstance(c.get("updated_at"), datetime):
            c["updated_at"] = c["updated_at"].isoformat()

        # Convert pdf_file_id if you also store it as ObjectId
        if c.get("pdf_file_id"):
            c["pdf_file_id"] = str(c["pdf_file_id"])

        chats.append(c)

    return chats

MAX_BYTES = 15 * 1024 * 1024  # 15 MB

@app.post("/chats/{chat_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_pdf(chat_id: str, file: UploadFile = File(...), request: Request = None):
    chats_col = request.app.state.db["chats"]

    chat = await chats_col.find_one({"chat_id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="file too large (max 15 MB)")

    # Store in GridFS (async)
    fs: AsyncIOMotorGridFSBucket = request.app.state.fs
    try:
        file_id = await fs.upload_from_stream(
            file.filename,
            io.BytesIO(pdf_bytes),
            metadata={"contentType": "application/pdf", "chat_id": chat_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store file: {e}")

    # Update chat with pdf_file_id
    print(file.filename)
    await chats_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"pdf_file_id": ObjectId(file_id), "updated_at": datetime.now(timezone.utc), "title": file.filename}},
    )

    return {"message": "PDF uploaded", "file_id": str(file_id)}


@app.post("/chats/{chat_id}/messages", status_code=status.HTTP_201_CREATED, dependencies=[Depends(RateLimiter(times=30, seconds=60))])
async def add_message(chat_id: str, data: MessageCreate, request: Request):
    if data.role not in ["user", "bot"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    chat = await get_chat_or_404(chat_id)

    msg_doc = {
        "chat_id": chat_id,
        "role": data.role,
        "content": data.content,
        "timestamp": datetime.now(timezone.utc),
    }
    res = await messages_col(request).insert_one(msg_doc)
    return {"message_id": str(res.inserted_id)}


@app.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),):
    chat = await chats_col(request).find_one({"chat_id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    cursor = messages_col(request).find({"chat_id": chat_id}).sort("timestamp", 1)
    msgs: List[dict] = []
    async for m in cursor:
        m["_id"] = str(m["_id"])
        # leave chat_id as string (already string)
        if isinstance(m.get("timestamp"), datetime):
            m["timestamp"] = m["timestamp"].isoformat()
        msgs.append(m)
    return msgs


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    chat = await chats_col(request).find_one({"chat_id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Delete messages
    await messages_col(request).delete_many({"chat_id": chat_id})

    # Delete PDF if exists
    if chat.get("pdf_file_id"):
        try:
            await request.app.fs.delete(chat["pdf_file_id"])
        except Exception:
            # File might already be gone—ignore
            pass

    # Delete chat (match by chat_id; DO NOT use _id here)
    await chats_col(request).delete_one({"chat_id": chat_id})
    return {"message": "Chat deleted successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8001)
