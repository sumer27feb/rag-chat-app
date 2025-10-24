import io
import os
import uuid
from asyncio import to_thread
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, List, Dict, Any
from dotenv import load_dotenv

import bleach
import fitz  # PyMuPDF
import redis.asyncio as redis
import uvicorn
import chromadb
from bson import ObjectId
from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    Request,
    status,
    Query,
    Depends, Body,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, field_validator
from pydantic.types import StringConstraints

# Local imports
from auth import router as auth_router
from rag import router as rag_router
from utils import success_response, error_response

# ---- Database ----
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# ---- File limits ----
MAX_BYTES = int(os.getenv("MAX_BYTES", 25 * 1024 * 1024))

# -------- App --------
app = FastAPI(title="RAG Chat API", version="1.0")

# -------- Prometheus Metrics --------
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app, include_in_schema=False, should_gzip=True)

# -------- CORS Middleware --------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Lifespan Events --------
@app.on_event("startup")
async def startup_event():
    """Initialize MongoDB, GridFS, and Redis connections."""
    app.mongodb_client = AsyncIOMotorClient(MONGO_URI, maxPoolSize=50)
    app.state.db = app.mongodb_client[DB_NAME]
    app.state.fs = AsyncIOMotorGridFSBucket(app.state.db)
    app.state.chroma_client = chromadb.PersistentClient(path="./chroma_store")

    redis_client = redis.from_url(
        "redis://localhost:6379", encoding="utf8", decode_responses=True
    )
    await FastAPILimiter.init(redis_client)
    logger.info("✅ MongoDB + Redis connected successfully.")


@app.on_event("shutdown")
async def shutdown_event():
    app.mongodb_client.close()
    logger.info("❌ MongoDB connection closed.")


# -------- Logging Middleware --------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log each request with timing and error capture."""
    req_id = str(uuid.uuid4())[:8]
    start_time = datetime.now()
    logger.info(f"➡️ [{req_id}] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception(f"💥 [{req_id}] {e}")
        return error_response("Internal Server Error", 500)

    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"⬅️ [{req_id}] {request.method} {request.url.path} {response.status_code} ({process_time:.2f}s)")
    return response


# -------- Schemas --------
class ChatCreate(BaseModel):
    user_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]

    class Config:
        extra = "forbid"


class MessageCreate(BaseModel):
    role: Literal["user", "bot"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    user_id: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]] = None

    @field_validator("content")
    def sanitize_content(cls, v: str) -> str:
        clean = bleach.clean(v, tags=[], attributes={}, strip=True)
        if any(tag in v.lower() for tag in ["<script", "<iframe", "<img"]):
            raise ValueError("Banned HTML tags not allowed")
        if not clean.strip():
            raise ValueError("Empty or invalid content")
        return clean


# -------- DB Helpers --------
def col_users(req: Request): return req.app.state.db["users"]
def col_chats(req: Request): return req.app.state.db["chats"]
def col_messages(req: Request): return req.app.state.db["messages"]
def col_user_chatlist(req: Request): return req.app.state.db["users_chat_list"]

async def get_chat_or_404(chat_id: str, db) -> Dict[str, Any]:
    """Fetch a chat by ID or raise 404."""
    chat = await db.chats.find_one({"chat_id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


# -------- Routers --------
app.include_router(auth_router)
app.include_router(rag_router)


# -------- Endpoints --------
@app.post("/chatsCreate", status_code=status.HTTP_201_CREATED)
async def create_chat(data: ChatCreate, request: Request):
    """Create a new chat for a user."""
    user = await col_users(request).find_one({"user_id": data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    chat_id = str(uuid.uuid4())
    chat_doc = {
        "user_id": data.user_id,
        "chat_id": chat_id,
        "title": None,
        "pdf_file_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await col_chats(request).insert_one(chat_doc)
    await col_user_chatlist(request).update_one(
        {"user_id": data.user_id},
        {"$push": {"chat_ids": chat_id}},
        upsert=True,
    )

    logger.info(f"🆕 Chat created for user {data.user_id} | chat_id={chat_id}")
    return success_response({"chat_id": chat_id}, 201)


@app.get("/users/{user_id}/chats")
async def list_user_chats(user_id: str, request: Request):
    """List all chats of a given user (sorted by recent activity)."""
    cursor = col_chats(request).find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1)
    chats = []
    async for chat in cursor:
        for field in ["created_at", "updated_at"]:
            if isinstance(chat.get(field), datetime):
                chat[field] = chat[field].isoformat()
        if chat.get("pdf_file_id"):
            chat["pdf_file_id"] = str(chat["pdf_file_id"])
        chats.append(chat)
    return chats


@app.post("/chats/{chat_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_pdf(chat_id: str, file: UploadFile = File(...), request: Request = None):
    """Upload a PDF to associate with a chat."""
    logger.debug(f"📥 Upload request received | chat_id={chat_id}")

    chat = await get_chat_or_404(chat_id, request.app.state.db)
    if file.content_type != "application/pdf":
        return error_response("Only PDF files allowed", 400)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        return error_response("Empty PDF file", 400)
    if len(pdf_bytes) > MAX_BYTES:
        return error_response("File too large (max 25 MB)", 400)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if not any(page.get_text().strip() for page in doc):
            return error_response("PDF contains no readable text", 400)
    except Exception as e:
        logger.error(f"Invalid PDF: {e}")
        return error_response("Invalid or corrupted PDF file", 400)

    fs: AsyncIOMotorGridFSBucket = request.app.state.fs
    file_id = await fs.upload_from_stream(
        file.filename,
        io.BytesIO(pdf_bytes),
        metadata={"contentType": "application/pdf", "chat_id": chat_id},
    )

    await col_chats(request).update_one(
        {"chat_id": chat_id},
        {"$set": {
            "pdf_file_id": ObjectId(file_id),
            "updated_at": datetime.now(timezone.utc),
            "title": os.path.splitext(file.filename)[0],
        }},
    )

    logger.success(f"✅ PDF uploaded | chat_id={chat_id} | file_id={file_id}")
    return success_response({"file_id": str(file_id), "filename": file.filename}, 201)


@app.post(
    "/chats/{chat_id}/messages",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=30, seconds=60))],
)
async def add_message(chat_id: str, data: MessageCreate, request: Request):
    """Add a user or bot message to a chat."""
    await get_chat_or_404(chat_id, request.app.state.db)
    msg_doc = {
        "chat_id": chat_id,
        "role": data.role,
        "content": data.content,
        "timestamp": datetime.now(timezone.utc),
    }

    res = await col_messages(request).insert_one(msg_doc)
    logger.info(f"💾 Message added to chat {chat_id} | role={data.role}")
    return success_response({"message_id": str(res.inserted_id)}, 201)


@app.get("/chats/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    """Paginated fetch of chat messages."""
    await get_chat_or_404(chat_id, request.app.state.db)
    total = await col_messages(request).count_documents({"chat_id": chat_id})
    cursor = (
        col_messages(request)
        .find({"chat_id": chat_id}, {"_id": 0})
        .sort("timestamp", 1)
        .skip(skip)
        .limit(limit)
    )

    messages = []
    async for msg in cursor:
        if isinstance(msg.get("timestamp"), datetime):
            msg["timestamp"] = msg["timestamp"].isoformat()
        messages.append(msg)

    return success_response({"messages": messages, "pagination": {"total": total, "limit": limit, "skip": skip}})


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request,
    body: dict = Body(...)):
    """Delete a chat and all its associated data."""
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    """Delete a chat and all its associated messages and PDF."""
    chat = await get_chat_or_404(chat_id, request.app.state.db)
    await col_messages(request).delete_many({"chat_id": chat_id})

    # Delete PDF file from GridFS if exists
    if chat.get("pdf_file_id"):
        try:
            # Manual check — GridFSBucket has no .exists()
            file_exists = await request.app.state.db["fs.files"].find_one({"_id": chat["pdf_file_id"]})
            if file_exists:
                await request.app.state.fs.delete(chat["pdf_file_id"])
        except Exception as e:
            logger.warning(f"⚠️ PDF delete failed: {e}")


    await col_chats(request).delete_one({"chat_id": chat_id})

    # Remove from user's chat list
    await col_user_chatlist(request).update_one(
        {"user_id": user_id},
        {"$pull": {"chat_ids": chat_id}}
    )

    collection = request.app.state.chroma_client.get_or_create_collection("chat_embeddings")
    await to_thread(collection.delete, where={"chat_id": chat_id})

    logger.info(f"🗑️ Chat deleted | chat_id={chat_id}")
    return success_response({"message": "Chat deleted successfully"}, 200)


# -------- Root Health Route --------
@app.get("/")
async def root():
    """Simple health check."""
    return {"status": "ok", "message": "RAG Chat API running"}


# -------- Run --------
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8001)
