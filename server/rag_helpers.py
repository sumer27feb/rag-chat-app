import io
import fitz
import chromadb
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from fastapi import HTTPException
from loguru import logger
from gridfs.errors import NoFile
from langchain_huggingface import HuggingFaceEmbeddings
from chunker import semantic_token_chunker
from db.connections import get_mongo

# ---------------------------
# EMBEDDER
# ---------------------------
def get_bge_small_embedder(device: str | None = None) -> HuggingFaceEmbeddings:
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    embedder = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en",
        model_kwargs={"device": device}
    )
    return embedder


# ---------------------------
# PDF READING
# ---------------------------
async def read_pdf_from_gridfs(file_id, fs: AsyncIOMotorGridFSBucket) -> str:
    if not isinstance(file_id, ObjectId):
        file_id_obj = ObjectId(file_id)
    else:
        file_id_obj = file_id

    logger.debug(f"Attempting GridFS download for ObjectId: {file_id_obj}")
    # db = fs.database  # Get the database instance from the GridFS bucket
    #
    # # 1. CRITICAL: Check for file metadata existence first
    # file_doc = await db.fs.files.find_one({"_id": file_id_obj})
    # if not file_doc:
    #     logger.error(f"❌ GridFS Error: File {file_id_obj} metadata not found.")
    #     raise HTTPException(status_code=404, detail="File metadata not found in GridFS.")
    #
    # # 2. Open Stream and Read Bytes
    # try:
    #     # Use open_download_stream now that we know the file exists
    #     download_stream = await fs.open_download_stream(file_id_obj)
    #     pdf_bytes = await download_stream.read()
    #     await download_stream.close()
    #
    # except Exception as e:
    #     # If it fails here, it's a genuine I/O or connection error
    #     logger.error(f"❌ General GridFS Read Error for ID {file_id_obj}: {e}")
    #     raise HTTPException(status_code=500, detail=f"Failed to read file stream from GridFS: {e}")
    #
    # # 3. Process PDF bytes into text
    # # ... (rest of the processing logic with fitz remains the same)
    # # ...
    #
    # # ...
    # return text.strip()

    download_stream = await fs.open_download_stream(file_id_obj)
    pdf_bytes = await download_stream.read()
    try:
        await download_stream.close()
    except Exception:
        try:
            download_stream.close()
        except Exception:
            pass

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")

    text = ""
    with fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"

    return text.strip()


# ---------------------------
# EMBEDDING HELPER
# ---------------------------
async def embed_chat_helper(chat_id: str) -> tuple[list[list[float]], list[str]]:
    # ------------------ DEBUG MINE 1: Connection Start ------------------
    logger.info(f"💣 [EMBED HELPER] Starting for chat_id: {chat_id}")
    try:
        db, fs = get_mongo()
        # ------------------ DEBUG MINE 2: Connection Success ------------------
        logger.debug(f"💣 [EMBED HELPER] Got MongoDB clients. DB Name: {db.name}")
    except Exception as e:
        # If get_mongo() fails, this will catch it immediately
        logger.error(f"💣 [EMBED HELPER] CRITICAL: Failed to get MongoDB clients: {e}")
        # Re-raise or handle as a connection error if this happens
        raise HTTPException(status_code=500, detail="Database connection failed in worker")

    # ------------------ DEBUG MINE 3: Database Lookup Start ------------------
    logger.debug(f"💣 [EMBED HELPER] Querying 'chats' for chat_id: {chat_id}")

    chat = await db["chats"].find_one({"chat_id": chat_id})

    # ------------------ DEBUG MINE 4: Data Check ------------------
    if not chat:
        logger.error(f"💣 [EMBED HELPER] Data Fail: Chat not found for ID: {chat_id}")
        raise HTTPException(status_code=404, detail="Chat or PDF not found (Chat Missing)")

    pdf_file_id = chat.get("pdf_file_id")
    if not pdf_file_id:
        logger.error(f"💣 [EMBED HELPER] Data Fail: PDF ID missing in chat doc for ID: {chat_id}")
        logger.debug(f"💣 [EMBED HELPER] Full chat document: {chat}")
        raise HTTPException(status_code=404, detail="Chat or PDF not found (PDF ID Missing)")

    logger.debug(f"💣 [EMBED HELPER] Data Success. PDF File ID: {pdf_file_id}")

    # ------------------ DEBUG MINE 5: GridFS Read Start ------------------
    logger.debug(f"💣 [EMBED HELPER] Reading PDF from GridFS with ID: {pdf_file_id}")
    text = await read_pdf_from_gridfs(pdf_file_id, fs)

    # ------------------ DEBUG MINE 6: Text Content Check ------------------
    logger.debug(f"💣 [EMBED HELPER] Text read from PDF. Size: {len(text)} characters")
    if len(text) < 100:
        logger.warning(f"💣 [EMBED HELPER] Warning: Low text content ({len(text)} chars)")
        # You might want to skip the rest if text is too short
        # return [], [] # Optionally uncomment this

    # ------------------ DEBUG MINE 7: Chunking ------------------
    chunks = semantic_token_chunker(text, max_tokens=500)
    logger.debug(f"💣 [EMBED HELPER] Chunking complete. Generated {len(chunks)} chunks.")

    if not chunks:
        logger.warning("💣 [EMBED HELPER] Warning: No chunks generated. Returning empty.")
        return [], []

    # ------------------ DEBUG MINE 8: Embedding Start ------------------
    embedder = get_bge_small_embedder()
    logger.debug("💣 [EMBED HELPER] Got embedder. Starting run_in_executor.")

    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(None, embedder.embed_documents, chunks)

    # ------------------ DEBUG MINE 9: Final Success ------------------
    logger.info(f"💣 [EMBED HELPER] Successfully generated {len(embeddings)} embeddings.")
    return embeddings, chunks


# ---------------------------
# CHROMA STORE
# ---------------------------
chroma_client = chromadb.PersistentClient(path="./chroma_store")

def store_embeddings_in_chroma(chat_id: str, chunks: list[str], embeddings: list[list[float]]) -> dict:
    if not chunks or not embeddings or len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings must be same non-empty length")

    collection = chroma_client.get_or_create_collection(
        name="chat_embeddings",
        metadata={"hnsw:space": "cosine"}
    )

    ids = [f"{chat_id}_{i}" for i in range(len(chunks))]
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"chat_id": chat_id, "chunk_index": i} for i in range(len(chunks))]
    )

    try:
        chroma_client.persist()
    except Exception:
        pass

    return {"chat_id": chat_id, "num_chunks_stored": len(chunks)}
